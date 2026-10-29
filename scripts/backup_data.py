"""Exporta somente o snapshot validado, sem arquivos de ambiente."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.snapshot import load_snapshot

ALLOWED = {
    "analytics.csv", "catalog.csv", "catalog.json", "coverage.csv",
    "latest.csv", "quality.csv", "manifest.json",
    "revision_history.csv", "revision_history.json",
}


def create_backup(root: Path, destination: Path) -> str:
    root = root.resolve()
    destination = destination.resolve()
    if destination.is_relative_to(root):
        raise ValueError("O destino deve ficar fora do projeto")
    pointer_text = (root / "data/processed/latest.json").read_text()
    pointer = json.loads(pointer_text)
    _, _, _, manifest = load_snapshot(root, pointer_text)
    directory = (root / pointer["path"]).resolve()
    names = set(manifest["files"]) | {"manifest.json", "catalog.json"}
    if not names <= ALLOWED:
        raise ValueError("Snapshot contém arquivos não autorizados para backup")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as staging:
        stage = Path(staging)
        snapshot_path = Path("data/processed") / directory.name
        target = stage / snapshot_path
        target.mkdir(parents=True)
        for name in sorted(names):
            source = directory / name
            if source.is_symlink():
                raise ValueError("Links simbólicos não são permitidos no backup")
            (target / name).write_bytes(source.read_bytes())
        pointer["path"] = snapshot_path.as_posix()
        (stage / "data/processed/latest.json").write_text(json.dumps(pointer))
        # Valida os bytes copiados, inclusive a cadeia de revisões.
        load_snapshot(stage)
        with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
                for path in sorted(stage.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(stage).as_posix())
            with ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise ValueError("Falha de integridade do ZIP")
                for name in archive.namelist():
                    if archive.read(name) != (stage / name).read_bytes():
                        raise ValueError("Conteúdo do ZIP diverge do snapshot validado")
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            # Publicação sem sobrescrever backups existentes, mesmo entre processos.
            os.link(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = create_backup(args.root, args.output)
    print(f"Backup validado: {args.output}\nSHA256: {digest}")


if __name__ == "__main__":
    main()
