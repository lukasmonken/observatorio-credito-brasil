from datetime import date

import numpy as np
import pandas as pd
import pytest

from observatorio.config import catalog
from observatorio.quality import validate_monthly
from observatorio.transform import indicators


def spec(code=433):
    return next(s for s in catalog() if s['code'] == code)


def series(values, start='2025-01-01'):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq='MS'), dtype=float)


def test_year_and_twelve_months_compound_and_reset_in_january():
    result = indicators(series([1] * 14), spec())
    assert np.isnan(result.inflation12.iloc[10])
    assert result.inflation12.iloc[11] == pytest.approx((1.01**12 - 1) * 100)
    assert result.inflation_ytd.iloc[11] == pytest.approx(result.inflation12.iloc[11])
    assert result.inflation_ytd.iloc[12] == pytest.approx(1)
    assert result.inflation_ytd.iloc[13] == pytest.approx(2.01)


def test_negative_and_zero_rates_are_preserved():
    result = indicators(series([0, -1, 1]), spec(189))
    assert result.inflation_ytd.iloc[0] == 0
    assert result.inflation_ytd.iloc[2] == pytest.approx(-0.01)


def test_missing_january_never_claims_full_year():
    result = indicators(series([1] * 13, start='2025-03-01'), spec())
    assert result.inflation_ytd.iloc[:10].isna().all()
    assert result.inflation_ytd.iloc[10] == pytest.approx(1)


@pytest.mark.parametrize('omit_row', [False, True])
def test_gap_invalidates_year_and_rolling_until_complete_again(omit_row):
    x = series([1] * 26)
    if omit_row:
        x = x.drop(x.index[1])
    else:
        x.iloc[1] = np.nan
    result = indicators(x, spec())
    assert pd.isna(result.loc['2025-12-01', 'inflation_ytd'])
    assert pd.isna(result.loc['2026-01-01', 'inflation12'])
    assert result.loc['2026-02-01', 'inflation12'] == pytest.approx((1.01**12 - 1) * 100)
    assert result.loc['2026-01-01', 'inflation_ytd'] == pytest.approx(1)


@pytest.mark.parametrize('invalid', [-100, -101])
def test_impossible_month_blocks_collection(invalid):
    x = series([invalid])
    assert any(level == 'error' for _, level, _ in validate_monthly(x, spec(), date(2025, 2, 1)))
    with pytest.raises(ValueError, match='Inflação impossível'):
        indicators(x, spec())


def test_inflation_catalog_has_sources_and_no_percent_change_of_rates():
    specs = [s for s in catalog() if s['classification'] == 'Inflação']
    assert len(specs) == 14
    assert len([s for s in specs if s['inflation_group'] == 'Grupos do IPCA']) == 9
    assert spec(7456)['short_name'] == 'INCC-M'
    for s in specs:
        assert s['frequency'] == 'M' and s['measure_type'] == 'variation'
        assert s['allowed_transforms'] == ['original', 'inflation_ytd', 'inflation12']
        assert ('IBGE' in s['source']) or ('FGV' in s['source'])
