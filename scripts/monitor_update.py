"""Registra a execução e verifica o job diário sem dependências externas."""

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.monitoring import (
    MAX_AGE_HOURS,
    collection_health,
    read_status,
    timestamp,
    write_status,
)


def manifest(root):
    pointer = json.loads((root / "data/processed/latest.json").read_text())
    directory = (root / pointer["path"]).resolve()
    directory.relative_to((root / "data/processed").resolve())
    return json.loads((directory / "manifest.json").read_text())


def start(root, now):
    previous = read_status(root) or {}
    write_status(
        root,
        {
            "status": "running",
            "started_at": now.isoformat(),
            "ended_at": None,
            "last_success_at": previous.get("last_success_at")
            or manifest(root)["created_at"],
            "duration_seconds": None,
            "failed_series": [],
            "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
        },
    )


def finish(root, now, status, stage):
    state = read_status(root)
    if state is None:
        start(root, now)
        state = read_status(root)
    attempts = sorted(
        (root / "work").glob("collection-*/data/processed/last_attempt.json"),
        key=lambda p: p.stat().st_mtime,
    )
    failed = []
    if attempts:
        attempt = json.loads(attempts[-1].read_text())
        # Public metadata contains codes only; exception details stay in artifacts.
        failed = [
            int(item["code"])
            for item in attempt.get("results", [])
            if item.get("status") == "failed"
        ]
    state.update(
        status=status,
        ended_at=now.isoformat(),
        duration_seconds=max(
            0, round((now - timestamp(state["started_at"])).total_seconds())
        ),
        failed_series=failed,
        stage=stage,
    )
    if status == "success":
        state["last_success_at"] = now.isoformat()
        state["snapshot_id"] = manifest(root)["snapshot_id"]
    write_status(root, state)
    return state


def check_runs(runs, now):
    if not runs:
        return ["Nenhuma execução do job diário encontrada."]
    latest = runs[0]
    errors = []
    if (now - timestamp(latest["created_at"])).total_seconds() > MAX_AGE_HOURS * 3600:
        errors.append(f"Job diário sem execução nas últimas {MAX_AGE_HOURS} horas.")
    if latest["status"] == "completed" and latest.get("conclusion") != "success":
        errors.append(f"Último job terminou com estado: {latest.get('conclusion')}.")
    if (
        latest["status"] != "completed"
        and (now - timestamp(latest["created_at"])).total_seconds() > 3600
    ):
        errors.append("Job pendente ou em execução há mais de uma hora.")
    return errors


def check(root, now):
    health, message = collection_health(read_status(root), manifest(root), now)
    errors = [message] if health in ("stale", "failed", "unknown") else []
    repo = os.environ["GITHUB_REPOSITORY"]
    if (
        any(
            c
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._/"
            for c in repo
        )
        or repo.count("/") != 1
    ):
        raise ValueError("Repositório inválido")
    request = Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/update-data.yml/runs?branch=main&per_page=5",
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 — HTTPS fixo, repositório validado
        runs = json.load(response)["workflow_runs"]
    errors.extend(check_runs(runs, now))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("start", "finish", "check"))
    parser.add_argument(
        "--status", choices=("success", "failed", "cancelled"), default="failed"
    )
    parser.add_argument("--stage", default="workflow")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.command == "start":
        start(ROOT, now)
        return
    if args.command == "finish":
        state = finish(ROOT, now, args.status, args.stage)
        lines = [
            f"Estado: {state['status']}",
            f"Etapa: {state['stage']}",
            f"Duração: {state['duration_seconds']} s",
            f"Séries com falha: {state['failed_series']}",
        ]
        code = 0
    else:
        errors = check(ROOT, now)
        lines = errors or ["Coleta e publicação dentro dos limites operacionais."]
        code = int(bool(errors))
    report = "## Monitoramento da atualização\n\n" + "\n\n".join(lines) + "\n"
    print(report)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
            output.write(report)
    sys.exit(code)


if __name__ == "__main__":
    main()
