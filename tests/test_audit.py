"""Regressões da auditoria: falhas de publicação, integridade e entradas externas."""

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
import requests
from filelock import Timeout

from observatorio.client import APIError, ReplayClient, SGSClient
from observatorio.config import ROOT
from observatorio.db import engine_for, pipeline_lock
from observatorio.snapshot import load_snapshot
from observatorio.transform import correlations, parse_rows
from scripts.update_data import publish_snapshot, validate_candidate


@pytest.fixture
def snapshot_root(tmp_path):
    pointer = json.loads((ROOT / "data/processed/latest.json").read_text())
    source = ROOT / pointer["path"]
    destination = tmp_path / pointer["path"]
    shutil.copytree(source, destination)
    (tmp_path / "data/processed/latest.json").write_text(json.dumps(pointer))
    return tmp_path, destination


def update_manifest(directory):
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    for name in manifest["files"]:
        manifest["files"][name] = hashlib.sha256(
            (directory / name).read_bytes()
        ).hexdigest()
    path.write_text(json.dumps(manifest))


def test_snapshot_corruption_rejected(snapshot_root):
    root, directory = snapshot_root
    load_snapshot(root)
    with (directory / "analytics.csv").open("a") as f:
        f.write("\ncorrupted")
    with pytest.raises(ValueError, match="Checksum"):
        load_snapshot(root)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "future", "infinite", "wrong_run", "invalid_date"]
)
def test_snapshot_schema_rejected_even_with_updated_checksum(snapshot_root, mutation):
    root, directory = snapshot_root
    path = directory / "analytics.csv"
    df = pd.read_csv(path)
    if mutation == "duplicate":
        df.loc[1] = df.iloc[0]
    elif mutation == "future":
        df.loc[0, "date"] = "2099-01-01"
    elif mutation == "infinite":
        df.loc[0, "original"] = np.inf
    elif mutation == "wrong_run":
        df.loc[0, "snapshot_id"] = "different"
    else:
        df.loc[0, "date"] = "invalid"
    df.to_csv(path, index=False)
    update_manifest(directory)
    with pytest.raises(ValueError):
        load_snapshot(root)


def test_snapshot_path_traversal(snapshot_root):
    root, _ = snapshot_root
    with pytest.raises(ValueError, match="diretório permitido"):
        load_snapshot(
            root, pointer=json.dumps({"path": "../outside", "snapshot_id": "x"})
        )


def test_publication_copy_failure_preserves_live_snapshot(snapshot_root, monkeypatch):
    root, source = snapshot_root
    before = (root / "data/processed/latest.json").read_bytes()
    original = (source / "analytics.csv").read_bytes()

    def failed_copy(src, destination):
        destination.mkdir()
        (destination / "analytics.csv").write_text("partial")
        raise OSError("disco cheio")

    monkeypatch.setattr(shutil, "copytree", failed_copy)
    with pytest.raises(OSError, match="disco cheio"):
        publish_snapshot(source, root, "new-run")
    assert (root / "data/processed/latest.json").read_bytes() == before
    assert (source / "analytics.csv").read_bytes() == original
    load_snapshot(root)


def test_publication_invalid_candidate_preserves_pointer(snapshot_root):
    root, source = snapshot_root
    before = (root / "data/processed/latest.json").read_bytes()
    with pytest.raises(ValueError, match="snapshots diferentes"):
        publish_snapshot(source, root, "wrong-run")
    assert (root / "data/processed/latest.json").read_bytes() == before
    load_snapshot(root)


def test_publication_switches_only_after_validation(snapshot_root, tmp_path):
    root, source = snapshot_root
    published = tmp_path / "published"
    (published / "data/processed").mkdir(parents=True)
    run_id = json.loads((source / "manifest.json").read_text())["snapshot_id"]
    publish_snapshot(source, published, run_id)
    df, _, _, manifest = load_snapshot(published)
    assert len(df) == manifest["rows"]
    with pytest.raises(FileExistsError):
        publish_snapshot(source, published, run_id)
    load_snapshot(published)


def test_replay_does_not_read_outside_directory(tmp_path):
    outside = tmp_path / "outside.body"
    outside.write_text("[]")
    raw = tmp_path / "raw"
    raw.mkdir()
    envelope = dict(
        code=433,
        status=200,
        start="2020-01-01",
        end="2020-12-31",
        extracted_at="2021-01-01",
        body_file="../outside.body",
        sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
    )
    (raw / "response.json").write_text(json.dumps(envelope))
    with pytest.raises(APIError, match="fora do diretório"):
        ReplayClient(raw).fetch(433, date(2020, 1, 1), date(2020, 12, 31))


@pytest.mark.parametrize("data", [None, "", "NaT", "31/02/2020", 20200101])
def test_invalid_dates_are_rejected(data):
    with pytest.raises(ValueError):
        parse_rows([{"data": data, "valor": "1"}])


def test_empty_correlations_are_defined():
    empty = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    result = correlations(empty, empty)
    assert result.n.eq(0).all() and result.correlation.isna().all()


def test_sqlite_parent_created_and_concurrent_pipeline_rejected(tmp_path):
    engine = engine_for("sqlite:///" + str(tmp_path / "nested/database.sqlite"))
    try:
        with pipeline_lock(engine):
            with pytest.raises(Timeout):
                with pipeline_lock(engine):
                    pytest.fail("Segunda coleta entrou no bloqueio")
        with pipeline_lock(engine):
            with engine.connect() as conn:
                assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    finally:
        engine.dispose()


def test_daily_gate_rejects_new_empty_series_and_infinity():
    previous = pd.DataFrame({"code": [1], "date": ["2020-01-01"], "original": [1.0]})
    candidate = pd.DataFrame(
        {"code": [1, 2], "date": ["2020-01-01"] * 2, "original": [1.0, np.nan]}
    )
    result = dict(status="success", failures=0, successes=2)
    with pytest.raises(ValueError, match="cobertura"):
        validate_candidate(result, previous, candidate, [1, 2])
    candidate.loc[1, "original"] = np.inf
    with pytest.raises(ValueError, match="infinito"):
        validate_candidate(result, previous, candidate, [1, 2])


def test_monthly_malformed_response_has_explicit_error(tmp_path):
    response = Mock(
        status_code=200, ok=True, content=b"[{}]", url="https://api.bcb.gov.br/"
    )
    response.json.return_value = [{}]
    session = Mock()
    session.get.return_value = response
    with pytest.raises(APIError, match="Campos"):
        SGSClient(tmp_path, "run", session=session, monthly_codes=[433]).fetch(
            433, date(2020, 1, 1), date(2020, 2, 1)
        )
    assert session.get.call_count == 1


def test_retry_after_does_not_leak_into_later_timeout(tmp_path):
    response = Mock(
        status_code=429,
        content=b"[]",
        url="https://api.bcb.gov.br/",
        headers={"Retry-After": "60"},
    )
    session = Mock()
    session.get.side_effect = [response, requests.Timeout(), requests.Timeout()]
    sleep = Mock()
    with pytest.raises(APIError):
        SGSClient(tmp_path, "run", session=session, sleeper=sleep).fetch(
            432, date(2020, 1, 1), date(2020, 1, 2)
        )
    assert [call.args[0] for call in sleep.call_args_list] == [60, 2]


def test_new_snapshot_hashes_catalog_json(tmp_path):
    from observatorio.pipeline import run_pipeline
    from tests.test_pipeline import evidence

    raw = tmp_path / "raw"
    evidence(raw, 433, [{"data": "01/01/2020", "valor": "1"}])
    result = run_pipeline(
        start=date(2020, 1, 1),
        end=date(2021, 12, 31),
        codes=[433],
        full=True,
        replay=raw,
        url="sqlite:///" + str(tmp_path / "db.sqlite"),
        output_root=tmp_path,
    )
    assert result["status"] == "success"
    assert "catalog.json" in result["snapshot"]["files"]
    load_snapshot(tmp_path)


def test_daily_main_publishes_validated_run(snapshot_root, monkeypatch):
    import scripts.update_data as daily

    root, old_directory = snapshot_root
    previous_pointer = (root / "data/processed/latest.json").read_text()
    run_id = "audit-new-run"

    def collect(**kwargs):
        dest = kwargs["output_root"] / "data/processed" / run_id
        shutil.copytree(old_directory, dest)
        data = pd.read_csv(dest / "analytics.csv")
        data["snapshot_id"] = run_id
        data.to_csv(dest / "analytics.csv", index=False)
        manifest_path = dest / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["snapshot_id"] = run_id
        manifest_path.write_text(json.dumps(manifest))
        update_manifest(dest)
        return dict(
            run_id=run_id, status="success", failures=0, successes=24, snapshot=manifest
        )

    monkeypatch.setattr(daily, "ROOT", root)
    monkeypatch.setattr(daily, "run_pipeline", collect)
    daily.main()
    assert (root / "data/processed/latest.json").read_text() != previous_pointer
    assert old_directory.exists()
    assert load_snapshot(root)[3]["snapshot_id"] == run_id


def test_daily_main_rejects_concurrent_publication(snapshot_root, monkeypatch):
    import scripts.update_data as daily

    root, old_directory = snapshot_root
    path = root / "data/processed/latest.json"

    def collect(**kwargs):
        destination = kwargs["output_root"] / "data/processed/new-run"
        shutil.copytree(old_directory, destination)
        pointer = json.loads(path.read_text())
        pointer["snapshot_id"] = "another-publisher"
        path.write_text(json.dumps(pointer))
        return dict(
            run_id="new-run",
            status="success",
            failures=0,
            successes=24,
            snapshot={"ok": True},
        )

    monkeypatch.setattr(daily, "ROOT", root)
    monkeypatch.setattr(daily, "run_pipeline", collect)
    with pytest.raises(RuntimeError, match="mudou durante"):
        daily.main()
    assert json.loads(path.read_text())["snapshot_id"] == "another-publisher"


def test_analysis_uses_observed_snapshot(snapshot_root):
    from observatorio.analysis import analyze

    root, directory = snapshot_root
    result = Path(analyze(root)).read_text()
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["snapshot_id"] in result
    correlations = pd.read_csv(root / "reports/correlations.csv")
    assert set(correlations.study) == {
        "selic_inadimplencia",
        "concessoes_inadimplencia",
        "atividade_credito",
    }
    assert correlations.n.ge(12).all()


def test_invalid_json_retries_then_recovers_with_evidence(tmp_path):
    invalid = Mock(
        status_code=200,
        ok=True,
        content=b"<html>unavailable</html>",
        url="https://api.bcb.gov.br/",
        headers={},
    )
    invalid.json.side_effect = ValueError("invalid JSON")
    rows = [{"data": "01/01/2020", "valor": "1"}]
    valid = Mock(
        status_code=200,
        ok=True,
        content=json.dumps(rows).encode(),
        url="https://api.bcb.gov.br/",
        headers={},
    )
    valid.json.return_value = rows
    session = Mock()
    session.get.side_effect = [invalid, valid]
    sleep = Mock()
    client = SGSClient(tmp_path, "recover", session=session, sleeper=sleep)
    assert client.fetch(433, date(2020, 1, 1), date(2020, 2, 1)) == rows
    assert session.get.call_count == 2 and sleep.call_count == 1
    assert len(list((tmp_path / "recover").glob("*.body"))) == 2


def test_invalid_json_never_retries_indefinitely(tmp_path):
    invalid = Mock(
        status_code=200,
        ok=True,
        content=b"not JSON",
        url="https://api.bcb.gov.br/",
        headers={},
    )
    invalid.json.side_effect = ValueError("invalid JSON")
    session = Mock()
    session.get.return_value = invalid
    sleep = Mock()
    with pytest.raises(APIError, match="3 tentativas: JSON inválido"):
        SGSClient(tmp_path, "invalid", session=session, sleeper=sleep).fetch(
            433, date(2020, 1, 1), date(2020, 2, 1)
        )
    assert session.get.call_count == 3 and sleep.call_count == 2
