from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest
import requests

from scripts import monitor_pages as monitor

NOW = datetime(2026, 11, 4, 15, tzinfo=timezone.utc)


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def iter_content(self, size):
        yield self.body


class Session:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        assert kwargs['timeout'] == (10, 30)
        assert kwargs['allow_redirects'] is False
        return self.responses[url.removeprefix(monitor.SITE)]


@pytest.fixture
def site(tmp_path):
    manifest = dict(snapshot_id='current', created_at=(NOW - timedelta(hours=2)).isoformat(), rows=1, series=1, as_of='2026-11-04')
    directory = tmp_path / 'data/processed/current'
    directory.mkdir(parents=True)
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    (directory.parent / 'latest.json').write_text(json.dumps({'path': 'data/processed/current'}))
    payload = dict(schema_version=1, manifest=manifest, rows=[dict(code=1, date='2026-01-01', original=0)], catalog=[dict(code=1)])
    raw = json.dumps(payload).encode()
    sha = hashlib.sha256(raw).hexdigest()
    filename = f'data-{sha[:16]}.json'
    config = dict(schema_version=1, data=filename, sha256=sha, snapshot_id='current')
    responses = {'': Response(b'<main id="content"></main><script type="module" src="assets/app-123.js"></script><link rel="stylesheet" href="assets/app-123.css">'),
                 'assets/app-123.js': Response(b'let app=1;'), 'assets/app-123.css': Response(b'body{}'),
                 'site.json': Response(json.dumps(config).encode()), filename: Response(raw)}
    return tmp_path, Session(responses), config, manifest


def test_healthy_publication_and_assets(site):
    root, session, _, _ = site
    result = monitor.check(root, session, NOW)
    assert result['status'] == 'ok'
    assert result['rows'] == 1 and result['errors'] == []
    assert len(session.urls) == 5


@pytest.mark.parametrize('resource,status', [('', 404), ('site.json', 503), ('assets/app-123.js', 404), ('assets/app-123.css', 302)])
def test_unavailable_page_data_or_asset_alerts(site, resource, status):
    root, session, _, _ = site
    session.responses[resource].status_code = status
    result = monitor.check(root, session, NOW)
    assert result['status'] == 'alert'
    assert str(status) in result['errors'][0]


def test_timeout_is_visible_without_technical_secrets(site):
    root, session, _, _ = site
    def fail(*args, **kwargs):
        raise requests.Timeout('private diagnostic')
    session.get = fail
    result = monitor.check(root, session, NOW)
    assert result['status'] == 'alert'
    assert 'private diagnostic' not in str(result)


def test_corrupted_payload_alerts(site):
    root, session, config, _ = site
    session.responses[config['data']].body = b'{}'
    assert 'Checksum' in monitor.check(root, session, NOW)['errors'][0]


@pytest.mark.parametrize('body', [b'[]', b'{invalid', b'{"schema_version": NaN}', b''])
def test_invalid_or_empty_config_alerts(site, body):
    root, session, _, _ = site
    session.responses['site.json'].body = body
    assert monitor.check(root, session, NOW)['status'] == 'alert'


@pytest.mark.parametrize('path', ['https://example.com/private', '../secret', '//example.com/x', 'assets/../../secret'])
def test_external_or_traversal_asset_not_requested(site, path):
    root, session, _, _ = site
    session.responses[''].body = f'<main id="content"></main><script type="module" src="{path}"></script><link rel="stylesheet" href="assets/app-123.css">'.encode()
    assert monitor.check(root, session, NOW)['status'] == 'alert'
    assert all(url.startswith(monitor.SITE) for url in session.urls)


@pytest.mark.parametrize('minutes,status', [(15, 'pending'), (60, 'pending'), (61, 'alert')])
def test_new_snapshot_grace_is_bounded(site, minutes, status):
    _, session, _, manifest = site
    expected = {**manifest, 'snapshot_id': 'new', 'created_at': (NOW - timedelta(minutes=minutes)).isoformat()}
    if status == 'alert':
        with pytest.raises(monitor.CheckError, match='última base'):
            monitor.inspect_site(session, expected, NOW)
    else:
        assert monitor.inspect_site(session, expected, NOW)['status'] == status


def test_snapshot_metadata_mismatch_alerts(site):
    _, session, _, manifest = site
    with pytest.raises(monitor.CheckError, match='Metadados'):
        monitor.inspect_site(session, {**manifest, 'rows': 2}, NOW)


def test_oversized_response_is_bounded(site, monkeypatch):
    root, session, _, _ = site
    monkeypatch.setattr(monitor, 'MAX_BYTES', 5)
    assert 'limite' in monitor.check(root, session, NOW)['errors'][0]


def test_data_schema_is_checked_even_with_valid_checksum(site):
    root, session, config, _ = site
    payload = json.loads(session.responses[config['data']].body)
    payload['rows'] = []
    raw = json.dumps(payload).encode()
    sha = hashlib.sha256(raw).hexdigest()
    filename = f'data-{sha[:16]}.json'
    session.responses[filename] = Response(raw)
    session.responses['site.json'].body = json.dumps({**config, 'data': filename, 'sha256': sha}).encode()
    assert 'incompletos' in monitor.check(root, session, NOW)['errors'][0]


def test_future_timestamp_is_not_healthy(site):
    _, session, _, manifest = site
    with pytest.raises(monitor.CheckError, match='futuro'):
        monitor.inspect_site(session, {**manifest, 'created_at': (NOW + timedelta(hours=2)).isoformat()}, NOW)


def test_missing_html_shell_alerts(site):
    root, session, _, _ = site
    session.responses[''].body = b'<html>Not the dashboard</html>'
    assert 'estrutura' in monitor.check(root, session, NOW)['errors'][0]
