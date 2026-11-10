"""Empacota apenas dados públicos validados para a interface estática."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.bulletin import build_bulletin
from observatorio.excel import METRIC_FORMULAS, METRIC_LABELS
from observatorio.monitoring import read_status
from observatorio.revisions import read_history
from observatorio.snapshot import load_snapshot
from observatorio.inflation_detail import TABLES, load_detail


def build_data(root, output):
    frame, catalog, quality, manifest = load_snapshot(root)
    pointer = json.loads((root / "data/processed/latest.json").read_text())
    history, meta = read_history(root / pointer["path"], manifest)
    bulletin = build_bulletin(frame, catalog, manifest, history, meta)
    numeric_columns = sorted(set().union(*(s["allowed_transforms"] for s in catalog)))
    frame = frame[["code", "date", *[m for m in numeric_columns if m in frame]]].copy()
    quarterly_codes = {s["code"] for s in catalog if s["frequency"] == "Q"}
    frame["reference_period"] = [f"{r.date.quarter}º tri/{r.date.year}" if r.code in quarterly_codes else r.date.strftime("%m/%Y") for r in frame.itertuples()]
    frame["date"] = frame.date.dt.strftime("%Y-%m-%d")
    monitoring_error = None
    try:
        monitoring = read_status(root)
        if monitoring is not None:
            monitoring = {key: monitoring[key] for key in ("status", "started_at", "ended_at", "last_success_at", "duration_seconds", "failed_series", "stage") if key in monitoring}
    except (ValueError, OSError):
        monitoring = None
        monitoring_error = "Estado operacional indisponível; os dados publicados foram validados."
    payload = {
        "schema_version": 1,
        "bulletin": bulletin,
        "manifest": {key: manifest[key] for key in ("snapshot_id", "created_at", "as_of", "rows", "series", "summary", "price_base_month")},
        "catalog": catalog,
        "rows": json.loads(frame.to_json(orient="records", double_precision=15)),
        "quality": json.loads(quality.to_json(orient="records")),
        "history": history.to_dict("records"), "history_meta": meta,
        "monitoring": monitoring, "monitoring_error": monitoring_error,
        "labels": METRIC_LABELS, "formulas": METRIC_FORMULAS,
        "methodology": (root / "docs/metodologia.md").read_text(),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    inflation_files = {}
    output.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        if not (root / "data/inflation" / f"{table}.json").exists():
            continue
        details = load_detail(root, table)
        encoded = json.dumps(details, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        name = f"inflation-{digest[:16]}.json"
        (output / name).write_bytes(encoded)
        inflation_files[table] = {"file": name, "sha256": digest, "name": details["name"]}
    payload["inflation_files"] = inflation_files
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    output.mkdir(parents=True, exist_ok=True)
    filename = f"data-{hashlib.sha256(content).hexdigest()[:16]}.json"
    (output / filename).write_bytes(content)
    (output / "site.json").write_text(json.dumps({"schema_version": 1, "data": filename, "inflation": list(inflation_files.values()), "sha256": hashlib.sha256(content).hexdigest(), "snapshot_id": manifest["snapshot_id"]}))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "web/generated")
    args = parser.parse_args()
    result = build_data(ROOT, args.output)
    print(f"Dados validados: {result['manifest']['rows']} observações, {result['manifest']['series']} séries.")
