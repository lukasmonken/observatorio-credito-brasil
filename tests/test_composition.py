import pandas as pd
import pytest
from observatorio.composition import composition_rows
from observatorio.config import catalog


def test_composition_uses_same_month_segment_total_and_preserves_missing():
    specs = catalog()
    frame = pd.DataFrame([(20541,'2025-01-01',100),(20579,'2025-01-01',25),
                          (20541,'2025-02-01',200),(20581,'2025-02-01',0)], columns=['code','date','original'])
    result = composition_rows(frame,specs,'PF').set_index(['code','date'])
    assert result.loc[(20579,'2025-01-01'),'share'] == 25
    assert pd.isna(result.loc[(20579,'2025-02-01'),'share'])
    assert result.loc[(20581,'2025-02-01'),'share'] == 0
    assert result.loc[(20579,'2025-01-01'),'denominator_code'] == 20541


@pytest.mark.parametrize('total,amount', [(0,0),(-1,1),(None,1),(100,101),(100,-1)])
def test_invalid_denominators_and_amounts_never_produce_share(total,amount):
    frame=pd.DataFrame([(20540,'2025-01-01',total),(20550,'2025-01-01',amount)],columns=['code','date','original'])
    result=composition_rows(frame,catalog(),'PJ')
    assert result.share.isna().all()


def test_modalities_are_disjoint_selected_stock_series():
    specs=[s for s in catalog() if s.get('credit_composition')]
    assert {s['code'] for s in specs} == {20579,20581,20612,20609,20550,20553,20544}
    assert all(s['measure_type']=='stock' and s['unit']=='R$ milhões' and s['frequency']=='M' for s in specs)
    assert all(s['source_url'].startswith('https://dadosabertos.bcb.gov.br/') for s in specs)


def test_duplicate_rows_rejected():
    frame=pd.DataFrame([(20541,'2025-01-01',100)]*2,columns=['code','date','original'])
    with pytest.raises(ValueError,match='duplicadas'):
        composition_rows(frame,catalog(),'PF')
