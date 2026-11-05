import json
from pathlib import Path

import pandas as pd
import pytest

from observatorio.bulletin import build_bulletin, load_bulletin
from observatorio.revisions import COLUMNS
from scripts.build_bulletin import write_bulletin

ROOT = Path(__file__).resolve().parents[1]


def fixture(kind='new_observation', before=100, current='110', transforms=None, previous_month='2026-09-01'):
    frame = pd.DataFrame({'code': [1, 1], 'date': pd.to_datetime([previous_month, '2026-10-01']), 'original': [before, float(current)]})
    specs = [{'code': 1, 'name': 'Saldo', 'unit': 'R$ milhões', 'source_url': 'https://www.bcb.gov.br/', 'measure_type': 'level', 'allowed_transforms': transforms or ['mom_pct']}]
    manifest = {'snapshot_id': 'b', 'created_at': '2026-11-04T12:00:00+00:00', 'as_of': '2026-11-04'}
    event = {'code': '1', 'name': 'Saldo', 'event_type': kind, 'reference_date': '2026-10-01', 'old_value': '109', 'new_value': current, 'difference': '1', 'unit': 'R$ milhões', 'difference_unit': 'R$ milhões', 'snapshot_id': 'b'}
    history = pd.DataFrame([event], columns=COLUMNS)
    meta = {'comparisons': [{'snapshot_id': 'b', 'previous_snapshot_id': 'a', 'detected_at': manifest['created_at']}]}
    return frame, specs, manifest, history, meta


def test_monthly_change_and_source_are_distinct_from_revision():
    report = build_bulletin(*fixture())
    assert '10,00 %' in report['highlights'][0]['text']
    assert '09/2026' in report['highlights'][0]['text']
    assert report['revisions'] == []
    assert 'https://www.bcb.gov.br/' in report['markdown']
    assert '09:00 (Brasília)' in report['markdown']
    assert report['previous_snapshot_id'] == 'a'
    json.dumps(report, allow_nan=False)


def test_rate_uses_percentage_points_and_preserves_zero():
    report = build_bulletin(*fixture(before=1, current='0', transforms=['diff_pp']))
    assert '-1,00 p.p.' in report['highlights'][0]['text']
    assert ': 0 R$' in report['highlights'][0]['text']


@pytest.mark.parametrize('before,month', [(0, '2026-09-01'), (-1, '2026-09-01'), (None, '2026-09-01'), (100, '2026-08-01')])
def test_missing_nonpositive_or_nonconsecutive_base_not_used(before, month):
    report = build_bulletin(*fixture(before=before, previous_month=month))
    assert 'Variação mensal não calculada' in report['highlights'][0]['text']


def test_revision_keeps_exact_decimal_and_does_not_become_monthly_news():
    args = list(fixture(kind='revision', current='110.123456789123456789'))
    report = build_bulletin(*args)
    assert not report['highlights']
    assert '110,123456789123456789' in report['revisions'][0]['text']


@pytest.mark.parametrize('kind', ['historical_fill', 'new_series'])
def test_other_additions_count_without_becoming_new_reference(kind):
    report = build_bulletin(*fixture(kind=kind))
    assert report['counts'][kind] == 1
    assert report['highlights'] == []


def test_unchanged_does_not_repeat_prior_news_and_baseline_is_explicit():
    args = list(fixture())
    args[3]['snapshot_id'] = 'a'
    report = build_bulletin(*args)
    assert 'Nenhuma mudança' in report['paragraphs'][0]
    assert report['highlights'] == []
    args[4] = None
    report = build_bulletin(*args)
    assert report['counts'] is None
    assert 'ainda não há comparação' in report['paragraphs'][0]


def test_mismatched_snapshot_rejected():
    args = list(fixture())
    args[2]['snapshot_id'] = 'wrong'
    with pytest.raises(ValueError, match='coletas diferentes'):
        build_bulletin(*args)


def test_artifacts_and_actions_summary_equal_published_bulletin(tmp_path):
    report = write_bulletin(ROOT, tmp_path / 'output', tmp_path / 'summary.md')
    assert report == load_bulletin(ROOT)
    assert (tmp_path / 'summary.md').read_text() == report['markdown']
    files = list((tmp_path / 'output').glob('*.json'))
    assert len(files) == 1 and json.loads(files[0].read_text()) == report
