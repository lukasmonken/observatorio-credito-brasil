import json

import pandas as pd
import pytest
from sqlalchemy import text

from observatorio.config import catalog
from observatorio.db import engine_for, initialize, register_catalog


def test_catalog_refresh_updates_columns_json_and_view():
    engine = engine_for('sqlite://')
    initialize(engine)
    original = catalog()[0]
    register_catalog(engine, [original])
    changed = {**original, 'name': 'Nome revisado', 'measure_type': 'index',
               'segment': 'PF revisado', 'classification': 'Categoria revisada'}
    register_catalog(engine, [changed])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO runs VALUES ('r','2025-01-01',NULL,'running','test','{}')"))
        conn.execute(text("INSERT INTO monthly_observations VALUES (:code,'2025-01-01',1,'r')"), changed)
        row = conn.execute(text("SELECT * FROM series")).mappings().one()
        for key in ('name', 'measure_type', 'segment', 'classification', 'unit', 'frequency'):
            assert row[key] == json.loads(row['metadata_json'])[key] == changed[key]
        assert conn.execute(text("SELECT name,segment FROM v_latest")).one() == (changed['name'], changed['segment'])
    for key, value in [('frequency', 'Q'), ('unit', 'nova unidade')]:
        with pytest.raises(ValueError, match='migração explícita'):
            register_catalog(engine, [{**changed, key: value}])
    with engine.connect() as conn:
        assert json.loads(conn.execute(text("SELECT metadata_json FROM series")).scalar_one()) == changed


def test_coverage_counts_periods_by_published_frequency():
    specs = catalog()
    engine = engine_for('sqlite://')
    initialize(engine)
    chosen = [next(s for s in specs if s['frequency'] == freq) for freq in ('M', 'D', 'Q')]
    register_catalog(engine, chosen)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO runs VALUES ('r','2025-01-01',NULL,'running','test','{}')"))
        for spec in chosen:
            dates = ['2025-01-01', '2025-04-01' if spec['frequency'] == 'Q' else '2025-02-01']
            for date, value in zip(dates, [0, None]):
                conn.execute(text("INSERT INTO monthly_observations VALUES (:code,:date,:value,'r')"),
                             {'code': spec['code'], 'date': date, 'value': value})
        coverage = pd.read_sql(text("SELECT * FROM v_coverage"), conn).set_index('code')
    for spec in chosen:
        row = coverage.loc[spec['code']]
        assert (row.observed_periods, row.missing_periods) == (1, 1)
        if spec['frequency'] == 'Q':
            assert row.period_unit == 'trimestre'
            assert pd.isna(row.observed_months) and pd.isna(row.missing_months)
        else:
            assert (row.period_unit, row.observed_months, row.missing_months) == ('mês', 1, 1)
