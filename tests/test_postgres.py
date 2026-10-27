"""Opcional: TEST_DATABASE_URL deve apontar para banco de testes autorizado."""

import os
import uuid
import pytest
from sqlalchemy import create_engine, event, text
from observatorio.db import initialize, register_catalog, persist_series, pipeline_lock
from observatorio.config import catalog
from observatorio.transform import parse_rows


@pytest.mark.integration
def test_postgresql_schema_upsert_views():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL de testes não configurado")
    schema = "test_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def search_path(dbapi, _):
        cur = dbapi.cursor()
        cur.execute(f"SET search_path TO {schema}")
        cur.close()
        dbapi.commit()

    try:
        initialize(engine)
        register_catalog(engine, catalog())
        with pipeline_lock(engine):
            with pytest.raises(RuntimeError, match="Já existe"):
                with pipeline_lock(engine):
                    pytest.fail("Duas coletas adquiriram o mesmo bloqueio PostgreSQL")
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO runs VALUES('test','2020-01-01',NULL,'running','test','{}')"
                )
            )
        df = parse_rows([{"data": "01/01/2020", "valor": "10"}])
        persist_series(engine, 432, df, "test")
        persist_series(engine, 432, df, "test")
        with engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM observations")).scalar() == 1
            assert c.execute(text("SELECT count(*) FROM v_latest")).scalar() == 0
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
