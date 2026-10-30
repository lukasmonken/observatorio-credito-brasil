"""Recupera um backup validado em diretório novo, sem alterar a base publicada."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.snapshot import load_snapshot
from scripts.backup_data import ALLOWED

MAX_BYTES = 256 * 1024 * 1024


def restore_backup(archive_path: Path, destination: Path, expected_sha256: str):
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise ValueError("SHA256 inválido")
    if archive_path.stat().st_size > MAX_BYTES:
        raise ValueError("Backup excede o limite de 256 MiB")
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != expected_sha256.lower():
        raise ValueError("SHA256 do backup divergente")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Escolha um diretório novo para recuperação")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as temporary:
        stage = Path(temporary) / "restored"
        stage.mkdir()
        with ZipFile(archive_path) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            if len(names) != len(set(names)) or len(names) > len(ALLOWED) + 1:
                raise ValueError("Arquivos duplicados ou quantidade inesperada")
            if sum(item.file_size for item in entries) > MAX_BYTES:
                raise ValueError("Conteúdo descompactado excede 256 MiB")
            pointer_name = "data/processed/latest.json"
            if pointer_name not in names:
                raise ValueError("Ponteiro ausente")
            pointer = json.loads(archive.read(pointer_name))
            snapshot_id = pointer["snapshot_id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", snapshot_id):
                raise ValueError("Identificador de snapshot inválido")
            prefix = f"data/processed/{snapshot_id}"
            if pointer["path"] != prefix:
                raise ValueError("Caminho do snapshot inválido")
            allowed = {pointer_name} | {f"{prefix}/{name}" for name in ALLOWED}
            for item in entries:
                if (item.filename not in allowed or item.is_dir()
                        or stat.S_ISLNK(item.external_attr >> 16)):
                    raise ValueError("Arquivo não autorizado no backup")
                target = stage.joinpath(*PurePosixPath(item.filename).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
        _, _, _, manifest = load_snapshot(stage)
        # Reserva o destino exclusivamente; não substitui nem um diretório vazio.
        destination.mkdir()
        try:
            shutil.copytree(stage / "data", destination / "data")
            load_snapshot(destination)
        except Exception:
            shutil.rmtree(destination)
            raise
    return {"snapshot_id": manifest["snapshot_id"], "rows": manifest["rows"],
            "series": manifest["series"], "sha256": expected_sha256.lower()}


def check_dashboard(restored_root: Path):
    from streamlit.testing.v1 import AppTest

    # A aplicação atual usa exclusivamente a base recuperada neste teste.
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        shutil.copytree(restored_root / "data", root / "data")
        shutil.copytree(ROOT / "docs", root / "docs")
        with patch("observatorio.config.ROOT", root):
            app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=60).run()
            if app.exception or app.error or not app.sidebar.radio:
                raise ValueError("Dashboard não carregou a base recuperada")
            pages = list(app.sidebar.radio[0].options)
            for page in pages:
                app.sidebar.radio[0].set_value(page).run()
                if app.exception or app.error:
                    raise ValueError(f"Falha na página recuperada: {page}")
    return len(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--check-dashboard", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = restore_backup(args.archive, args.destination, args.sha256)
    if args.check_dashboard:
        result["dashboard_pages_checked"] = check_dashboard(args.destination)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
