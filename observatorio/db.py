"""SQL versionado, transações por série e upserts SQLite/PostgreSQL."""

import json
import uuid
from pathlib import Path
import pandas as pd
from contextlib import contextmanager
from filelock import FileLock
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from .config import ROOT


def engine_for(url):
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (
        None,
        "",
        ":memory:",
    ):
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_fk(dbapi, _):
            dbapi.execute("PRAGMA foreign_keys=ON")

    return engine


def initialize(engine):
    with engine.begin() as conn:
        for filename in ("schema.sql", "views.sql"):
            for statement in (ROOT / "sql" / filename).read_text().split(";"):
                if statement.strip():
                    conn.execute(text(statement))


def register_catalog(engine, specs):
    with engine.begin() as conn:
        for s in specs:
            previous = (
                conn.execute(
                    text("SELECT unit,frequency FROM series WHERE code=:code"), s
                )
                .mappings()
                .first()
            )
            if previous and (
                previous["unit"] != s["unit"] or previous["frequency"] != s["frequency"]
            ):
                raise ValueError(
                    f"Mudança de unidade/frequência na série {s['code']}: migração explícita necessária"
                )
            conn.execute(
                text("""INSERT INTO series(code,name,unit,frequency,measure_type,segment,classification,metadata_json)
              VALUES(:code,:name,:unit,:frequency,:measure_type,:segment,:classification,:metadata_json)
              ON CONFLICT(code) DO UPDATE SET name=excluded.name,metadata_json=excluded.metadata_json"""),
                {**s, "metadata_json": json.dumps(s, ensure_ascii=False)},
            )


def numeric(v):
    return None if pd.isna(v) else float(v)


def persist_series(engine, code, df, run_id):
    """Original dates retained; null is a real revision, never changed to zero."""
    revised = 0
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:code)"), {"code": code})
        old = dict(
            conn.execute(
                text("SELECT date,value FROM observations WHERE code=:code"),
                {"code": code},
            ).all()
        )
        rows = []
        for row in df.itertuples():
            dt, value = str(row.date.date()), numeric(row.value)
            if dt in old and old[dt] != value:
                conn.execute(
                    text(
                        "INSERT INTO revisions VALUES(:id,:code,:date,:old,:new,:run)"
                    ),
                    dict(
                        id=str(uuid.uuid4()),
                        code=code,
                        date=dt,
                        old=old[dt],
                        new=value,
                        run=run_id,
                    ),
                )
                revised += 1
            rows.append(dict(code=code, date=dt, value=value, run_id=run_id))
        if rows:
            conn.execute(
                text("""INSERT INTO observations(code,date,value,run_id) VALUES(:code,:date,:value,:run_id)
            ON CONFLICT(code,date) DO UPDATE SET value=excluded.value,run_id=excluded.run_id"""),
                rows,
            )
    return revised


def read_observations(engine, code):
    with engine.connect() as conn:
        return pd.read_sql(
            text("SELECT date,value FROM observations WHERE code=:code ORDER BY date"),
            conn,
            params={"code": code},
            parse_dates=["date"],
        )


def check(engine, run_id, code, name, severity, message):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO quality VALUES(:id,:run,:code,:name,:severity,:message)"),
            dict(
                id=str(uuid.uuid4()),
                run=run_id,
                code=code,
                name=name,
                severity=severity,
                message=message,
            ),
        )


@contextmanager
def pipeline_lock(engine):
    """Serializa a coleta completa, inclusive reconstrução das tabelas derivadas."""
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            locked = conn.execute(
                text("SELECT pg_try_advisory_lock(703254019)")
            ).scalar()
            if not locked:
                raise RuntimeError("Já existe uma coleta neste banco")
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(703254019)"))
    elif engine.url.database not in (None, "", ":memory:"):
        with FileLock(
            str(Path(engine.url.database).resolve()) + ".pipeline.lock", timeout=0
        ):
            yield
    else:
        yield
