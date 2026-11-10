import hashlib
import json
from pathlib import Path
import shutil

import pytest

from scripts.build_pages_data import build_data

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source(tmp_path):
    pointer = json.loads((ROOT / 'data/processed/latest.json').read_text())
    shutil.copytree(ROOT / pointer['path'], tmp_path / pointer['path'])
    (tmp_path / 'data/processed/latest.json').write_text(json.dumps(pointer))
    (tmp_path / 'docs').mkdir()
    shutil.copyfile(ROOT / 'docs/metodologia.md', tmp_path / 'docs/metodologia.md')
    return tmp_path


def test_public_package_preserves_values_and_integrity(source):
    result = build_data(source, source / 'output')
    config = json.loads((source / 'output/site.json').read_text())
    content = (source / 'output' / config['data']).read_bytes()
    assert hashlib.sha256(content).hexdigest() == config['sha256']
    assert result['manifest']['rows'] == len(result['rows'])
    assert len(result['catalog']) == result['manifest']['series']
    assert all(set(row) <= {'code', 'date', 'reference_period', *result['labels']} for row in result['rows'])
    assert any(row['original'] == 0 for row in result['rows'])
    assert any(row.get('diff_pp') is None for row in result['rows'])
    assert 'NaN' not in content.decode()
    assert set(p.name for p in (source / 'output').iterdir()) == {'site.json', config['data']}


def test_corrupt_snapshot_cannot_be_published(source):
    pointer = json.loads((source / 'data/processed/latest.json').read_text())
    (source / pointer['path'] / 'analytics.csv').write_text('corrompido')
    with pytest.raises(ValueError):
        build_data(source, source / 'output')
    assert not (source / 'output/site.json').exists()


def test_invalid_monitoring_keeps_valid_data_with_warning(source):
    (source / 'data/processed/monitoring.json').write_text('{invalid')
    result = build_data(source, source / 'output')
    assert result['monitoring'] is None
    assert result['monitoring_error']
    assert result['rows']


def test_monitoring_exports_only_operational_fields(source):
    (source / 'data/processed/monitoring.json').write_text(json.dumps({
        'status': 'success', 'stage': 'snapshot_validado', 'private_diagnostic': 'not-public',
    }))
    result = build_data(source, source / 'output')
    assert result['monitoring'] == {'status': 'success', 'stage': 'snapshot_validado'}


def test_ibge_package_is_separate_and_hash_verified(source):
    from tests.test_inflation_detail import response
    from observatorio.inflation_detail import normalize, publish
    publish(source, {'7060': normalize('7060', [response()])})
    result = build_data(source, source / 'output')
    descriptor = result['inflation_files']['7060']
    content = (source / 'output' / descriptor['file']).read_bytes()
    assert hashlib.sha256(content).hexdigest() == descriptor['sha256']
    assert json.loads(content)['table'] == '7060'
    config = json.loads((source / 'output/site.json').read_text())
    assert config['inflation'] == [descriptor]
    assert all('location' not in row for row in result['rows'])
