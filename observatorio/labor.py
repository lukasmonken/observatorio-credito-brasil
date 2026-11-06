"""Rótulos e exportação da PNAD Contínua, preservando os trimestres móveis."""

import pandas as pd


def labor_period(value):
    end = pd.Timestamp(value)
    start = end - pd.DateOffset(months=2)
    return f"{start:%m/%Y}–{end:%m/%Y}"


def labor_export(frame, specs, manifest, income_base):
    records = []
    for spec in specs:
        for _, row in frame[frame.code == spec['code']].iterrows():
            rate = spec['measure_type'] == 'rate'
            records.append({
                'reference_end': row.date.strftime('%Y-%m-%d'),
                'reference_period': labor_period(row.date),
                'code': spec['code'], 'indicator': spec.get('short_name', spec['name']),
                'value': row.original, 'unit': spec['unit'],
                'change12': row.get('diff12_pp' if rate else 'yoy_pct'),
                'change_unit': 'p.p.' if rate else '%',
                'income_price_base': income_base if spec['measure_type'] == 'income_real' else None,
                'region': 'Brasil', 'source': spec['source'], 'source_url': spec['source_url'],
                'snapshot_id': manifest['snapshot_id'],
            })
    return pd.DataFrame(records)
