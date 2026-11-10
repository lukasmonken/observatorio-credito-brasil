"""Collect IBGE inflation details without changing the validated SGS snapshot."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.inflation_detail import TABLES, collect, publish

if __name__ == "__main__":
    datasets = {}
    for table in TABLES:
        print(f"Coletando {TABLES[table]['name']}", flush=True)
        datasets[table] = collect(table)
        print(f"Validado: {len(datasets[table]['rows'])} observações", flush=True)
    print(publish(ROOT, datasets))
