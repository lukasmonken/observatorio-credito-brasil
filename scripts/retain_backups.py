"""Retenção restrita aos arquivos conhecidos do backup no Google Drive."""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from zoneinfo import ZoneInfo

REMOTE = "backup:Observatorio-Credito-Brasil"


def plan_retention(entries, now, current):
    if now.tzinfo is None:
        raise ValueError("Data da avaliação sem fuso horário")
    groups = defaultdict(list)
    for entry in entries:
        groups[entry["Path"].split("/")[0]].append(entry)
    valid = {}
    ignored = []
    for folder, items in groups.items():
        expected = {f"{folder}/credito-{folder}.zip", f"{folder}/SHA256SUMS", f"{folder}/source-commit.txt"}
        files = [item for item in items if not item["IsDir"]]
        paths = [item["Path"] for item in files]
        if (not re.fullmatch(r"[0-9]+-[0-9]+", folder)
                or set(paths) != expected or len(paths) != 3
                or any(item["IsDir"] and item["Path"] != folder for item in items)):
            ignored.append(folder)
            continue
        archive = next(item for item in files if item["Path"].endswith(".zip"))
        try:
            created = datetime.fromisoformat(archive["ModTime"].replace("Z", "+00:00"))
            if created.tzinfo is None or created > now or any(item["Size"] <= 0 for item in files):
                raise ValueError("Metadados inválidos")
        except (ValueError, KeyError, TypeError):
            ignored.append(folder)
            continue
        valid[folder] = created
    if current not in valid:
        raise ValueError("Backup atual ausente ou incompleto; limpeza bloqueada")
    ordered = sorted(valid, key=lambda folder: (valid[folder], folder), reverse=True)
    keep = {current, ordered[0]}
    local_now = now.astimezone(ZoneInfo("America/Sao_Paulo"))
    month_now = local_now.year * 12 + local_now.month
    monthly = set()
    for folder in ordered:
        created = valid[folder]
        if created >= now - timedelta(days=30):
            keep.add(folder)
        local_date = created.astimezone(ZoneInfo("America/Sao_Paulo"))
        month = local_date.year * 12 + local_date.month
        if 0 <= month_now - month < 12 and month not in monthly:
            keep.add(folder)
            monthly.add(month)
    return {"keep": sorted(keep), "delete": sorted(set(valid) - keep), "ignored": sorted(ignored)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--verified-local", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+-[0-9]+", args.current):
        raise ValueError("Identificador de backup inválido")
    binary = shutil.which("rclone")
    if binary is None:
        raise RuntimeError("rclone não instalado")

    def run(*arguments):
        # Sem shell; destino fixo e nomes de pastas restritos a números e hífen.
        return subprocess.run(  # noqa: S603
            [binary, *arguments, "--config", args.config, "--drive-use-trash=true",
             "--contimeout", "30s", "--timeout", "2m", "--retries", "3"],
            check=True, capture_output=True, text=True, timeout=300,
        ).stdout

    expected = {f"credito-{args.current}.zip", "SHA256SUMS", "source-commit.txt"}
    if {p.name for p in args.verified_local.iterdir()} != expected:
        raise ValueError("Cópia local incompleta; limpeza bloqueada")
    run("check", str(args.verified_local), f"{REMOTE}/{args.current}", "--download")
    entries = json.loads(run("lsjson", REMOTE, "--recursive"))
    plan = plan_retention(entries, datetime.now(timezone.utc), args.current)
    plan["mode"] = "apply" if args.apply else "simulation"
    plan["removed_files"] = []
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(plan, indent=2))
    if args.apply:
        for folder in plan["delete"]:
            before = [e for e in entries if e["Path"].startswith(folder + "/")]
            fresh = json.loads(run("lsjson", f"{REMOTE}/{folder}", "--recursive"))
            for item in fresh:
                item["Path"] = folder + "/" + item["Path"]
            if sorted(before, key=lambda e: e["Path"]) != sorted(fresh, key=lambda e: e["Path"]):
                raise ValueError("Backup mudou durante a limpeza; execução interrompida")
            # Remove somente os três arquivos reconhecidos; não percorre outras pastas.
            for item in fresh:
                run("deletefile", f"{REMOTE}/{item['Path']}")
                plan["removed_files"].append(item["Path"])
                args.report.write_text(json.dumps(plan, indent=2))
            run("rmdir", f"{REMOTE}/{folder}")
    print(f"Retenção: {len(plan['keep'])} preservados; {len(plan['delete'])} elegíveis; {len(plan['ignored'])} ignorados; {len(plan['removed_files'])} arquivos enviados à lixeira.")


if __name__ == "__main__":
    main()
