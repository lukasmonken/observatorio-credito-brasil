import numpy as np
import pandas as pd
import pytest
from observatorio.transform import compare_base100


def sample():
    return pd.DataFrame({'code': [1, 1, 1, 2, 2, 2], 'date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01'] * 2), 'original': [10, 20, 0, np.nan, 4, 8]})


def test_common_month_and_missing_history_do_not_get_independent_bases():
    source = sample()
    result, base = compare_base100(source, [1, 2])
    assert base == pd.Timestamp('2020-02-01')
    assert result.base100.tolist() == [100, 100, 0, 200]
    assert 'base100' not in source


@pytest.mark.parametrize('value', [0, np.nan, np.inf])
def test_invalid_denominator_skips_month(value):
    source = sample()
    source.loc[4, 'original'] = value
    result, base = compare_base100(source, [1, 2])
    assert base is None and result.empty


def test_no_overlap_empty_and_unknown_series():
    for source, codes in [(sample().iloc[:0], [1, 2]), (sample(), []), (sample(), [1, 9])]:
        result, base = compare_base100(source, codes)
        assert base is None and result.empty


def test_period_rebases_and_preserves_later_missing_values():
    source = sample()
    source.loc[2, 'original'] = np.nan
    result, base = compare_base100(source.loc[source.date >= '2020-02-01'], [1, 2])
    assert base == pd.Timestamp('2020-02-01')
    assert pd.isna(result.loc[result.code.eq(1)].iloc[-1].base100)


def test_negative_base_and_out_of_order_dates():
    source = sample().iloc[::-1].copy()
    source.loc[4, 'original'] = -4
    result, _ = compare_base100(source, [1, 2])
    assert result.loc[result.code.eq(2)].base100.tolist() == [100, -200]


def test_streamlit_comparison_renders_and_exports():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file('dashboard/app.py', default_timeout=20).run()
    app.sidebar.radio[0].set_value('Comparação em base 100').run()
    assert not app.exception
    assert len(app.get('plotly_chart')) == 1
    assert any('Mês-base comum:' in caption.value for caption in app.caption)
    app.multiselect[0].set_value([20539]).run()
    assert not app.exception
    assert any('Selecione de dois' in item.value for item in app.info)
