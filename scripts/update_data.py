"""Collect in isolation; publish only a complete, non-regressing snapshot."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
import shutil
import sys
from zoneinfo import ZoneInfo
import tempfile
from filelock import FileLock
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.config import catalog
from observatorio.pipeline import run_pipeline


def validate_candidate(result, previous, candidate, expected):
    if (
        result["status"] != "success"
        or result["failures"]
        or result["successes"] != len(expected)
    ):
        raise ValueError("Coleta incompleta: a base publicada será preservada")
    if set(candidate.code.unique()) != set(expected):
        raise ValueError("Snapshot não contém todas as séries")
    previous, candidate = previous.copy(), candidate.copy()
    for frame in (previous, candidate):
        if frame.empty or frame[["code", "date"]].isna().any().any():
            raise ValueError("Snapshot vazio ou chave ausente")
        dates = pd.to_datetime(frame.date, format="%Y-%m-%d", errors="raise")
        frame["date"] = dates
        if (dates.dt.day != 1).any():
            raise ValueError("Referência não mensal")
        frame["original"] = pd.to_numeric(frame.original, errors="raise")
        if np.isinf(frame.original).any():
            raise ValueError("Valor infinito no snapshot")
    if set(candidate.loc[candidate.original.notna(), "code"]) != set(expected):
        raise ValueError("Perda de cobertura: série sem valores numéricos")
    old = previous.set_index(["code", "date"]).original.dropna()
    new = candidate.set_index(["code", "date"]).original
    if new.index.has_duplicates or not old.index.isin(new.dropna().index).all():
        raise ValueError("Perda de cobertura ou duplicidade: publicação bloqueada")
    for code in expected:
        old_dates = previous.loc[previous.code == code, "date"]
        if (
            not old_dates.empty
            and candidate[candidate.code == code].date.max() < old_dates.max()
        ):
            raise ValueError(f"Regressão de referência: {code}")


def publish_snapshot(source, root, run_id):
    """Diretório imutável antes do commit atômico do ponteiro."""
    from observatorio.snapshot import load_snapshot

    destination = root / "data/processed" / run_id
    shutil.copytree(source, destination)
    pointer = json.dumps(
        {"snapshot_id": run_id, "path": str(destination.relative_to(root))}
    )
    load_snapshot(root, pointer=pointer)
    pointer_path = root / "data/processed/latest.json"
    temporary = pointer_path.with_suffix(".tmp")
    temporary.write_text(pointer)
    os.replace(temporary, pointer_path)


def main():
    logging.basicConfig(level=logging.INFO)
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="collection-", dir=work))
    db = work / "collection.db"
    pointer_path = ROOT / "data/processed/latest.json"
    previous_pointer = json.loads(pointer_path.read_text())
    previous = pd.read_csv(ROOT / previous_pointer["path"] / "analytics.csv")
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    result = run_pipeline(
        end=today, full=True, url="sqlite:///" + str(db), output_root=work
    )
    if not result.get("snapshot"):
        raise RuntimeError(
            "Nenhum snapshot válido; consulte work/collection-*/reports/runs"
        )
    source = work / "data/processed" / result["run_id"]
    candidate = pd.read_csv(source / "analytics.csv")
    validate_candidate(result, previous, candidate, [s["code"] for s in catalog()])
    with FileLock(ROOT / ".publish.lock", timeout=0):
        if json.loads(pointer_path.read_text()) != previous_pointer:
            raise RuntimeError("A base mudou durante a coleta; execute novamente")
        publish_snapshot(source, ROOT, result["run_id"])
    print(
        f"VALIDADO: {len(candidate)} linhas, {candidate.code.nunique()} séries; coleta {today}"
    )


if __name__ == "__main__":
    main()
