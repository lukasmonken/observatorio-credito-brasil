import hashlib
import json
from zipfile import ZipFile

import pytest

from observatorio.config import ROOT
from observatorio.snapshot import load_snapshot
from scripts.backup_data import create_backup
from scripts.restore_backup import check_dashboard, restore_backup


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "backup.zip"
    digest = create_backup(ROOT, path)
    return path, digest


def test_restore_loads_real_snapshot_and_dashboard_without_changing_source(archive, tmp_path):
    pointer = (ROOT / "data/processed/latest.json").read_bytes()
    destination = tmp_path / "recovery"
    result = restore_backup(archive[0], destination, archive[1])
    assert result["snapshot_id"] == json.loads(pointer)["snapshot_id"]
    assert len(load_snapshot(destination)[0]) == result["rows"]
    assert check_dashboard(destination) == 8
    assert (ROOT / "data/processed/latest.json").read_bytes() == pointer


def test_checksum_and_existing_destination_are_rejected(archive, tmp_path):
    destination = tmp_path / "recovery"
    with pytest.raises(ValueError, match="SHA256"):
        restore_backup(archive[0], destination, "0" * 64)
    assert not destination.exists()
    destination.mkdir()
    with pytest.raises(FileExistsError):
        restore_backup(archive[0], destination, archive[1])


@pytest.mark.parametrize("name", ["../outside", "/outside", "data/processed/.env", "data/processed/latest.json"])
def test_unsafe_or_duplicate_members_are_rejected(archive, tmp_path, name):
    with ZipFile(archive[0], "a") as output:
        output.writestr(name, "invalid")
    digest = hashlib.sha256(archive[0].read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        restore_backup(archive[0], tmp_path / "recovery", digest)
    assert not (tmp_path / "recovery").exists()


def test_corrupt_snapshot_is_rejected_even_with_valid_zip_checksum(archive, tmp_path):
    path = tmp_path / "corrupt.zip"
    with ZipFile(archive[0]) as source, ZipFile(path, "w") as output:
        for name in source.namelist():
            output.writestr(name, b"invalid" if name.endswith("analytics.csv") else source.read(name))
    with pytest.raises(ValueError, match="Checksum"):
        restore_backup(path, tmp_path / "recovery", hashlib.sha256(path.read_bytes()).hexdigest())
    assert not (tmp_path / "recovery").exists()
