"""Collect in isolation; publish only a complete, non-regressing snapshot."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
import shutil
import sys
from zoneinfo import ZoneInfo
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.config import catalog
from observatorio.pipeline import run_pipeline


def validate_candidate(result, previous, candidate, expected):
    if result['status'] != 'success' or result['failures'] or result['successes'] != len(expected):
        raise ValueError('Coleta incompleta: a base publicada será preservada')
    if set(candidate.code.unique()) != set(expected):
        raise ValueError('Snapshot não contém todas as séries')
    old = previous.set_index(['code', 'date']).original.dropna()
    new = candidate.set_index(['code', 'date']).original
    if new.index.has_duplicates or not old.index.isin(new.dropna().index).all():
        raise ValueError('Perda de cobertura ou duplicidade: publicação bloqueada')
    for code in expected:
        if candidate[candidate.code == code].date.max() < previous[previous.code == code].date.max():
            raise ValueError(f'Regressão de referência: {code}')


def main():
    logging.basicConfig(level=logging.INFO)
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    # A fresh database makes the run independent of caches and rechecks revisions
    # over the entire historical period. It is never sent to the public repo.
    db = work / 'collection.db'
    if db.exists():
        db.unlink()
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    result = run_pipeline(end=today, full=True, url='sqlite:///' + str(db), output_root=work)
    if not result.get('snapshot'):
        raise RuntimeError('Nenhum snapshot válido; consulte work/reports/runs')
    pointer_path = ROOT / 'data/processed/latest.json'
    previous_pointer = json.loads(pointer_path.read_text())
    previous = pd.read_csv(ROOT / previous_pointer['path'] / 'analytics.csv')
    source = work / 'data/processed' / result['run_id']
    candidate = pd.read_csv(source / 'analytics.csv')
    validate_candidate(result, previous, candidate, [s['code'] for s in catalog()])
    destination = ROOT / 'data/processed/current'
    destination.mkdir(exist_ok=True)
    for item in source.iterdir():
        shutil.copy2(item, destination / item.name)
    temporary = pointer_path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'snapshot_id': result['run_id'], 'path': 'data/processed/current'}))
    os.replace(temporary, pointer_path)
    print(f'VALIDADO: {len(candidate)} linhas, {candidate.code.nunique()} séries; coleta {today}')


if __name__ == '__main__':
    main()
