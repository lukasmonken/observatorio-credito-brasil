"""Leitura validada do snapshot apontado; nenhum arquivo fora de data/processed."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from .config import ROOT


def load_snapshot(root=ROOT, pointer=None):
    root = Path(root)
    pointer = json.loads(
        pointer
        if pointer is not None
        else (root / "data/processed/latest.json").read_text()
    )
    directory = (root / pointer["path"]).resolve()
    if not directory.is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Snapshot fora do diretório permitido")
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["snapshot_id"] != pointer["snapshot_id"]:
        raise ValueError("Ponteiro e manifesto identificam snapshots diferentes")
    required = {
        "analytics.csv",
        "latest.csv",
        "quality.csv",
        "coverage.csv",
        "catalog.csv",
    }
    if not required <= manifest["files"].keys():
        raise ValueError("Manifesto incompleto")
    for name, expected in manifest["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Arquivo fora do snapshot")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Checksum divergente: {name}")
    df = pd.read_csv(directory / "analytics.csv")
    catalog = json.loads((directory / "catalog.json").read_text())
    quality = pd.read_csv(directory / "quality.csv")
    required_columns = {"code", "date", "original", "snapshot_id", "name", "unit"}
    if df.empty or not required_columns <= set(df.columns):
        raise ValueError("Snapshot vazio ou colunas obrigatórias ausentes")
    df["date"] = pd.to_datetime(df.date, format="%Y-%m-%d", errors="raise")
    if (
        df.date.isna().any()
        or (df.date.dt.day != 1).any()
        or df.duplicated(["code", "date"]).any()
    ):
        raise ValueError("Calendário mensal inválido ou duplicado")
    if (df.date > pd.Timestamp(manifest["as_of"])).any():
        raise ValueError("Referência posterior ao corte do snapshot")
    if not df.snapshot_id.eq(manifest["snapshot_id"]).all():
        raise ValueError("Dados pertencem a outra execução")
    spec_fields = {
        "code",
        "name",
        "unit",
        "frequency",
        "segment",
        "classification",
        "allowed_transforms",
        "coverage_observed",
        "source_url",
    }
    if not isinstance(catalog, list) or any(
        not isinstance(s, dict) or not spec_fields <= s.keys() for s in catalog
    ):
        raise ValueError("Catálogo incompleto")
    if manifest["summary"]["status"] not in ("success", "partial"):
        raise ValueError("Execução não publicável")
    for key in ("successes", "failures"):
        if (
            not isinstance(manifest["summary"][key], int)
            or manifest["summary"][key] < 0
        ):
            raise ValueError("Resumo de execução inválido")
    codes = [s["code"] for s in catalog]
    if len(set(codes)) != len(codes) or set(df.code) != set(codes):
        raise ValueError("Catálogo não corresponde às séries do snapshot")
    if len(df) != manifest["rows"] or len(codes) != manifest["series"]:
        raise ValueError("Contagens divergentes no manifesto")
    for spec in catalog:
        metrics = spec["allowed_transforms"]
        if not set(metrics) <= set(df.columns):
            raise ValueError("Transformação declarada ausente")
        values = df.loc[df.code == spec["code"], metrics].apply(
            pd.to_numeric, errors="raise"
        )
        if np.isinf(values.to_numpy(dtype=float)).any():
            raise ValueError("Valor infinito no snapshot")
        if values.original.dropna().empty:
            raise ValueError("Série sem observações numéricas")
    return df.sort_values(["code", "date"]), catalog, quality, manifest
