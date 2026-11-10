"""Resumo macroeconômico sem misturar referências nem preencher ausências."""
import json
from pathlib import Path
import pandas as pd

INDICATORS = json.loads(Path(__file__).with_name("panorama.json").read_text())


def panorama_rows(df, specs):
    catalog = {s["code"]: s for s in specs}
    records = []
    for item in INDICATORS:
        available = df[(df.code == item["code"]) & df.original.notna()].sort_values("date")
        latest = available.iloc[-1] if not available.empty else None
        value = latest.get(item["metric"]) if latest is not None else None
        records.append({**item, "date": latest.date if latest is not None else None,
                        "value": float(value) if value is not None and pd.notna(value) else None,
                        "source_url": catalog.get(item["code"], {}).get("source_url", "")})
    return records


def reference_label(date, kind):
    if date is None or pd.isna(date):
        return "Sem referência disponível"
    date = pd.Timestamp(date)
    if kind == "quarter":
        return f"{date.quarter}º trimestre de {date.year}"
    if kind == "rolling":
        start = date - pd.DateOffset(months=2)
        return f"Trimestre móvel: {start:%m/%Y}–{date:%m/%Y}"
    return date.strftime("%m/%Y")
