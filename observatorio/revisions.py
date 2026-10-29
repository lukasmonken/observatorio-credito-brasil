"""Mudanças observadas entre snapshots publicados, sem inferir datas de divulgação."""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import pandas as pd

HISTORY_FILES = {"revision_history.csv", "revision_history.json"}
EVENT_LABELS = {
    "revision": "Revisão de valor",
    "new_observation": "Nova referência",
    "historical_fill": "Preenchimento histórico",
    "new_series": "Série incluída",
}
COLUMNS = [
    "event_id",
    "event_type",
    "code",
    "name",
    "reference_date",
    "unit",
    "old_value",
    "new_value",
    "difference",
    "difference_unit",
    "detected_at",
    "previous_snapshot_id",
    "snapshot_id",
]


def decimal_value(value):
    if pd.isna(value) or str(value).strip() == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Valor inválido na comparação") from exc
    if not number.is_finite():
        raise ValueError("Valor não finito na comparação")
    return number


def event_id(previous_id, current_id, code, reference):
    key = json.dumps([previous_id, current_id, int(code), reference])
    return hashlib.sha256(key.encode()).hexdigest()


def observations(frame):
    records = {}
    for row in frame.itertuples(index=False):
        code = int(row.code)
        reference = str(row.date)[:10]
        parsed = datetime.strptime(reference, "%Y-%m-%d")
        if parsed.day != 1 or code <= 0:
            raise ValueError("Chave mensal inválida")
        key = (code, reference)
        if key in records:
            raise ValueError("Observação duplicada na comparação")
        records[key] = decimal_value(row.original)
    return records


def compare_snapshots(previous, current, specs, previous_id, current_id, detected_at):
    if previous_id == current_id:
        raise ValueError("A comparação exige snapshots distintos")
    if datetime.fromisoformat(detected_at).tzinfo is None:
        raise ValueError("Detecção sem fuso horário")
    old, new = observations(previous), observations(current)
    metadata = {int(s["code"]): s for s in specs}
    last: dict[int, str] = {}
    for (code, reference), value in old.items():
        if value is not None:
            last[code] = max(reference, last.get(code, reference))
    for key, value in old.items():
        if value is not None and new.get(key) is None:
            raise ValueError("Perda de observação: comparação não publicável")
    events = []
    for (code, reference), value in sorted(new.items()):
        before = old.get((code, reference))
        if value is None or before == value:
            continue
        kind = (
            "revision"
            if before is not None
            else (
                "new_series"
                if code not in last
                else "new_observation"
                if reference > last[code]
                else "historical_fill"
            )
        )
        spec = metadata[code]
        events.append(
            {
                "event_id": event_id(previous_id, current_id, code, reference),
                "event_type": kind,
                "code": str(code),
                "name": spec["name"],
                "reference_date": reference,
                "unit": spec["unit"],
                "old_value": format(before, "f") if before is not None else "",
                "new_value": format(value, "f"),
                "difference": format(value - before, "f") if before is not None else "",
                "difference_unit": "p.p."
                if spec["measure_type"] == "rate"
                else spec["unit"],
                "detected_at": detected_at,
                "previous_snapshot_id": previous_id,
                "snapshot_id": current_id,
            }
        )
    return events


def read_history(directory, manifest):
    declared = HISTORY_FILES.intersection(manifest["files"])
    if not declared and "revision_history_version" not in manifest:
        return pd.DataFrame(columns=COLUMNS), None
    if declared != HISTORY_FILES or manifest.get("revision_history_version") != 1:
        raise ValueError("Histórico incompleto ou versão desconhecida")
    for name in HISTORY_FILES:
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != manifest["files"][name]
        ):
            raise ValueError("Checksum divergente no histórico")
    meta = json.loads((directory / "revision_history.json").read_text())
    events = pd.read_csv(
        directory / "revision_history.csv", dtype=str, keep_default_na=False
    )
    if list(events.columns) != COLUMNS or events.event_id.duplicated().any():
        raise ValueError("Esquema ou unicidade inválidos no histórico")
    if meta["schema_version"] != 1 or meta["snapshot_id"] != manifest["snapshot_id"]:
        raise ValueError("Histórico pertence a outro snapshot")
    comparisons = meta["comparisons"]
    previous_id = meta["baseline_snapshot_id"]
    seen = {previous_id}
    for comparison in comparisons:
        current_id = comparison["snapshot_id"]
        if comparison["previous_snapshot_id"] != previous_id or current_id in seen:
            raise ValueError("Cadeia de comparações inconsistente")
        if datetime.fromisoformat(comparison["detected_at"]).tzinfo is None:
            raise ValueError("Detecção sem fuso horário")
        subset = events[events.snapshot_id == current_id]
        if (
            not subset.previous_snapshot_id.eq(previous_id).all()
            or not subset.detected_at.eq(comparison["detected_at"]).all()
        ):
            raise ValueError("Eventos fora da comparação declarada")
        counts = {kind: int(subset.event_type.eq(kind).sum()) for kind in EVENT_LABELS}
        if counts != comparison["counts"] or sum(counts.values()) != len(subset):
            raise ValueError("Contagens divergentes no histórico")
        seen.add(current_id)
        previous_id = current_id
    if (
        not comparisons
        or previous_id != manifest["snapshot_id"]
        or not set(events.snapshot_id) <= (seen - {meta["baseline_snapshot_id"]})
    ):
        raise ValueError("Histórico desconectado da base publicada")
    for event in events.to_dict("records"):
        expected = event_id(
            event["previous_snapshot_id"],
            event["snapshot_id"],
            event["code"],
            event["reference_date"],
        )
        if (
            event["event_id"] != expected
            or datetime.strptime(event["reference_date"], "%Y-%m-%d").day != 1
        ):
            raise ValueError("Identidade de evento inválida")
        before, after, difference = (
            decimal_value(event[key])
            for key in ("old_value", "new_value", "difference")
        )
        if after is None:
            raise ValueError("Evento sem valor novo")
        if event["event_type"] == "revision":
            if before is None or before == after or difference != after - before:
                raise ValueError("Diferença de revisão inválida")
        elif before is not None or difference is not None:
            raise ValueError("Nova observação não tem valor anterior")
    return events, meta


def attach_history(destination, previous_directory, previous_manifest, manifest):
    """Histórico acumulado dentro do snapshot, antes da promoção do ponteiro."""
    previous_events, previous_meta = read_history(previous_directory, previous_manifest)
    # Decimal sobre o texto do CSV evita falsos eventos por parsing binário de floats.
    old = pd.read_csv(
        previous_directory / "analytics.csv", dtype=str, keep_default_na=False
    )
    new = pd.read_csv(destination / "analytics.csv", dtype=str, keep_default_na=False)
    old_specs = {
        s["code"]: s
        for s in json.loads((previous_directory / "catalog.json").read_text())
    }
    specs = json.loads((destination / "catalog.json").read_text())
    for spec in specs:
        if spec["code"] in old_specs and any(
            spec[key] != old_specs[spec["code"]][key]
            for key in ("unit", "frequency", "measure_type")
        ):
            raise ValueError(
                "Mudança de unidade/frequência/tipo exige migração do histórico"
            )
    detected_at = datetime.now(timezone.utc).isoformat()
    added = compare_snapshots(
        old,
        new,
        specs,
        previous_manifest["snapshot_id"],
        manifest["snapshot_id"],
        detected_at,
    )
    meta = previous_meta or {
        "schema_version": 1,
        "baseline_snapshot_id": previous_manifest["snapshot_id"],
        "baseline_created_at": previous_manifest["created_at"],
        "comparisons": [],
    }
    meta["snapshot_id"] = manifest["snapshot_id"]
    meta["comparisons"].append(
        {
            "previous_snapshot_id": previous_manifest["snapshot_id"],
            "snapshot_id": manifest["snapshot_id"],
            "detected_at": detected_at,
            "counts": {
                kind: sum(e["event_type"] == kind for e in added)
                for kind in EVENT_LABELS
            },
        }
    )
    combined = pd.DataFrame(previous_events.to_dict("records") + added, columns=COLUMNS)
    combined.to_csv(destination / "revision_history.csv", index=False)
    (destination / "revision_history.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)
    )
    manifest["revision_history_version"] = 1
    for name in HISTORY_FILES:
        manifest["files"][name] = hashlib.sha256(
            (destination / name).read_bytes()
        ).hexdigest()
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    read_history(destination, manifest)
