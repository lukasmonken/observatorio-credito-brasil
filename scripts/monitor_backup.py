"""Verifica backups pelo histórico do Actions, sem acesso às credenciais do Drive."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

MAX_AGE_HOURS = 30
MAX_RUNNING_HOURS = 1
RUN_LIMIT = 20
VERIFICATION_STEP = "Enviar e verificar cópia externa"


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Horário sem fuso")
    return parsed


def summarize_run(run, jobs):
    if not isinstance(jobs, list) or len(jobs) != 1:
        raise ValueError("Estrutura inesperada de jobs do backup")
    job = jobs[0]
    status = job["status"]
    conclusion = job.get("conclusion")
    if status not in {"queued", "in_progress", "completed", "waiting", "pending", "requested"}:
        raise ValueError("Estado inesperado do job")
    if status == "completed" and conclusion not in {"success", "failure", "cancelled", "timed_out", "action_required", "neutral", "skipped", "stale", "startup_failure"}:
        raise ValueError("Conclusão inesperada do job")
    start = timestamp(job.get("started_at") or run["run_started_at"])
    end = timestamp(job["completed_at"]) if job.get("completed_at") else None
    if end is not None and end < start:
        raise ValueError("Duração negativa")
    steps = job.get("steps", [])
    verified = any(s["name"] == VERIFICATION_STEP and s.get("conclusion") == "success" for s in steps)
    return {
        "run_id": int(run["id"]),
        "run_attempt": int(run["run_attempt"]),
        "started_at": start.isoformat(),
        "ended_at": end.isoformat() if end else None,
        "duration_seconds": round((end - start).total_seconds()) if end else None,
        "status": status,
        "conclusion": conclusion,
        "skipped": conclusion == "skipped",
        # Exige término do job inteiro, inclusive artefatos e retenção.
        "verified": status == "completed" and conclusion == "success" and verified and end is not None,
    }


def evaluate(records, now):
    ordered = sorted(records, key=lambda r: timestamp(r["started_at"]), reverse=True)
    attempts = [r for r in ordered if not r["skipped"]]
    latest = attempts[0] if attempts else None
    successes = [r for r in attempts if r["verified"]]
    success = max(successes, key=lambda r: timestamp(r["ended_at"])) if successes else None
    errors = []
    if not latest:
        errors.append("Nenhuma tentativa efetiva de backup encontrada na janela consultada.")
    else:
        age = (now - timestamp(latest["started_at"])).total_seconds() / 3600
        if age > MAX_AGE_HOURS:
            errors.append(f"Backup sem tentativa nas últimas {MAX_AGE_HOURS} horas.")
        if latest["status"] == "completed" and not latest["verified"]:
            errors.append("Última tentativa de backup falhou, foi cancelada ou não concluiu todas as verificações.")
        elif latest["status"] != "completed" and age > MAX_RUNNING_HOURS:
            errors.append("Backup pendente ou em execução há mais de uma hora.")
    if success is None:
        errors.append("Nenhum backup validado encontrado na janela consultada.")
    elif (now - timestamp(success["ended_at"])).total_seconds() > MAX_AGE_HOURS * 3600:
        errors.append(f"Sem backup validado há mais de {MAX_AGE_HOURS} horas.")
    if any(timestamp(r[field]) > now for r in records for field in ("started_at", "ended_at") if r[field]):
        errors.append("Horários do backup estão no futuro; estado não confiável.")
    blocked = bool(ordered and ordered[0]["skipped"])
    if blocked:
        errors.append("Último backup não executou: job pulado. Confira a coleta que o acionou.")
    return {
        "checked_at": now.isoformat(),
        "status": "alert" if errors else "running" if latest and latest["status"] != "completed" else "ok",
        "last_attempt": latest,
        "last_success": success,
        "latest_execution_skipped": blocked,
        "runs_checked": len(records),
        "errors": errors,
    }


def api_get(repo, token, path):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Repositório inválido")
    request = Request(
        f"https://api.github.com/repos/{repo}/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 — domínio fixo e repositório validado
        return json.load(response)


def check(repo, token, now=None):
    payload = api_get(repo, token, f"actions/workflows/backup-data.yml/runs?branch=main&per_page={RUN_LIMIT}")
    runs = payload["workflow_runs"]
    if not isinstance(runs, list):
        raise ValueError("Lista de execuções inválida")
    records = []
    for run in runs[:RUN_LIMIT]:
        run_id, attempt = int(run["id"]), int(run["run_attempt"])
        if run_id <= 0 or attempt <= 0:
            raise ValueError("Identificador inválido")
        jobs = api_get(repo, token, f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")["jobs"]
        # Antes da alocação do runner pode ainda não existir job.
        if not jobs and run["status"] != "completed":
            jobs = [{"status": run["status"], "conclusion": None, "started_at": run["run_started_at"], "steps": []}]
        records.append(summarize_run(run, jobs))
    return evaluate(records, now or datetime.now(timezone.utc))


def render_report(report, repo):
    lines = ["## Monitoramento dos backups", "", f"Estado: {report['status']}",
             f"Verificado em (UTC): {report['checked_at']}"]
    for key, label in (("last_attempt", "Última tentativa"), ("last_success", "Último sucesso completo")):
        item = report.get(key)
        if item is None:
            lines.append(f"{label}: não identificado.")
        else:
            link = f"https://github.com/{repo}/actions/runs/{item['run_id']}/attempts/{item['run_attempt']}"
            lines.append(f"{label}: [{item['started_at']}]({link}); término: {item['ended_at'] or 'pendente'}; duração: {item['duration_seconds']} s.")
    lines.extend(report["errors"] or ["Backup dentro dos limites operacionais."])
    lines.append(f"Janela: até {RUN_LIMIT} execuções recentes. Estado consultado no GitHub; o monitor não testa novamente o Drive.")
    return "\n\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    try:
        report = check(repo, os.environ["GITHUB_TOKEN"])
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        # Erro de consulta é desconhecido, nunca um sinal de backup saudável.
        report = {"checked_at": now.isoformat(), "status": "unknown", "errors": [
            "Não foi possível validar o histórico do backup. Confira a API do GitHub, permissões e formato da resposta."
        ]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    text = render_report(report, repo)
    print(text)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write(text)
    if report["errors"]:
        print("::error::Monitoramento do backup requer atenção. Consulte o resumo desta execução.")
    sys.exit(int(bool(report["errors"])))


if __name__ == "__main__":
    main()
