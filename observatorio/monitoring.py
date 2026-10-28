"""Estado operacional separado da referência econômica das séries."""

import json
import os
import math
from datetime import datetime, timezone

MAX_AGE_HOURS = 30


def timestamp(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Timestamp sem fuso horário")
    return dt


def read_status(root):
    path = root / "data/processed/monitoring.json"
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or state.get("status") not in (
        "running",
        "success",
        "failed",
        "cancelled",
    ):
        raise ValueError("Estado operacional inválido")
    for key in ("started_at", "ended_at", "last_success_at"):
        if state.get(key) is not None:
            timestamp(state[key])
    duration = state.get("duration_seconds")
    if duration is not None and (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    ):
        raise ValueError("Duração inválida")
    failed = state.get("failed_series", [])
    if not isinstance(failed, list) or any(
        type(code) is not int or code <= 0 for code in failed
    ):
        raise ValueError("Códigos de séries inválidos")
    if "stage" in state and not isinstance(state["stage"], str):
        raise ValueError("Etapa inválida")
    return state


def write_status(root, state):
    path = root / "data/processed/monitoring.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    os.replace(temporary, path)


def collection_health(state, manifest, now=None):
    now = now or datetime.now(timezone.utc)
    last_success = (state or {}).get("last_success_at") or manifest["created_at"]
    age = (now - timestamp(last_success)).total_seconds() / 3600
    if age < -1:
        return (
            "unknown",
            "Horário de atualização inconsistente; confira o monitoramento.",
        )
    if age > MAX_AGE_HOURS:
        return (
            "stale",
            f"Sem atualização validada há mais de {MAX_AGE_HOURS} horas. A última base válida continua disponível.",
        )
    if state and state["status"] in ("failed", "cancelled"):
        return (
            "failed",
            "A última tentativa de atualização falhou ou foi interrompida. A última base válida foi preservada.",
        )
    if state and state["status"] == "running":
        return (
            "running",
            "Atualização em andamento. Os dados exibidos são da última base válida.",
        )
    if not state:
        return (
            "unknown",
            "Detalhes operacionais ainda não registrados; referência obtida do snapshot publicado.",
        )
    return "ok", "Última coleta concluída com sucesso."


def source_freshness(df, specs, today):
    rows = []
    for spec in specs:
        valid = df.loc[(df.code == spec["code"]) & df.original.notna(), "date"]
        latest = valid.max() if not valid.empty else None
        lag = (today - latest.date()).days if latest is not None else None
        limit = spec["max_lag_days"]
        rows.append(
            {
                "SGS": spec["code"],
                "Indicador": spec["name"],
                "Última referência": latest.strftime("%m/%Y")
                if latest is not None
                else "Sem dados",
                "Dias desde a referência": lag,
                "Limite operacional (dias)": limit,
                "Situação": "Sem dados"
                if lag is None
                else "Acima do limite"
                if lag > limit
                else "Dentro do limite",
            }
        )
    return rows
