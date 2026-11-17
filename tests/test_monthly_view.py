from datetime import date

import pandas as pd
from sqlalchemy import text

from observatorio.config import catalog
from observatorio.db import engine_for, initialize, persist_series, register_catalog
from observatorio.pipeline import build_snapshot


def test_monthly_view_matches_catalog_and_python_for_all_series(tmp_path):
    specs = catalog()
    engine = engine_for('sqlite://')
    initialize(engine)
    register_catalog(engine, specs)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO runs VALUES ('r','2022-01-01',NULL,'running','test','{}')"))
    for spec in specs:
        freq = 'QS' if spec['frequency'] == 'Q' else 'MS'
        dates = pd.date_range('2020-01-01', '2021-12-01', freq=freq)
        values = [float(i + 1) for i in range(len(dates))]
        if spec['code'] == 20539:
            values[0] = 0.0
        values[3] = float('nan')
        persist_series(engine, spec['code'], pd.DataFrame({'date': dates, 'value': values}), 'r')
    build_snapshot(engine, specs, 'r', date(2021, 12, 31), {}, tmp_path)
    analytics = pd.read_csv(tmp_path / 'data/processed/r/analytics.csv')
    monthly_codes = {s['code'] for s in specs if s['frequency'] != 'Q'}
    expected = analytics[analytics.code.isin(monthly_codes)].set_index(['code', 'date']).sort_index()
    with engine.connect() as conn:
        actual = pd.read_sql(text('SELECT * FROM v_monthly_changes'), conn).set_index(['code', 'date']).sort_index()
    metrics = ['mom_pct', 'yoy_pct', 'diff_pp', 'ma3']
    pd.testing.assert_frame_equal(actual[metrics], expected[metrics], check_exact=False)
    assert actual.loc[3698, 'mom_pct'].notna().any()
    assert actual.loc[433, 'ma3'].isna().all()
    assert pd.isna(actual.loc[(20539, '2020-02-01'), 'mom_pct'])
