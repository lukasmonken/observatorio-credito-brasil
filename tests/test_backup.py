import json
from pathlib import Path
from shutil import copytree
from zipfile import ZipFile

import pytest

from scripts.backup_data import create_backup

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "project"
    pointer = json.loads((ROOT / "data/processed/latest.json").read_text())
    copytree(ROOT / pointer["path"], root / pointer["path"])
    (root / "data/processed/latest.json").write_text(json.dumps(pointer))
    (root / ".env").write_text("SECRET=never-export")
    return root


def test_backup_preserves_history_excludes_secrets_and_refuses_overwrite(source, tmp_path):
    output = tmp_path / "backup.zip"
    assert len(create_backup(source, output)) == 64
    with ZipFile(output) as archive:
        names = archive.namelist()
        assert "data/processed/latest.json" in names
        assert not any(".env" in name for name in names)
        pointer = json.loads((source / "data/processed/latest.json").read_text())
        for file in (source / pointer["path"]).glob("revision_history.*"):
            assert archive.read(f'{pointer["path"]}/{file.name}') == file.read_bytes()
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        create_backup(source, output)
    assert output.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_corruption_does_not_publish_backup(source, tmp_path):
    pointer = json.loads((source / "data/processed/latest.json").read_text())
    (source / pointer["path"] / "analytics.csv").write_text("invalid")
    output = tmp_path / "backup.zip"
    with pytest.raises(ValueError, match="Checksum"):
        create_backup(source, output)
    assert not output.exists()


def test_destination_must_be_external(source):
    with pytest.raises(ValueError, match="fora do projeto"):
        create_backup(source, source / "backup.zip")
