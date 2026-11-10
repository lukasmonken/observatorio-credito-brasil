from copy import deepcopy
import json
import pytest
from observatorio.inflation_detail import normalize, number, category_level, publish, load_detail


def response():
    header = {'D1N':'Município, Região Metropolitana e Brasil', 'D2N':'Variável', 'D3N':'Mês', 'D4N':'Geral, grupo, subgrupo, item e subitem'}
    items = [header]
    for year in (2025, 2026):
        for month in range(1, 13):
            for loc, cat, name in [('1','7169','Índice geral'), ('1','7173','1101002.Arroz'), ('3501','7169','Índice geral')]:
                for var, value in [('63','-'), ('69','-0.50'), ('2265','...'), ('66','100' if cat == '7169' else '0.8')]:
                    items.append({'NC':'1' if loc == '1' else '7', 'MN':'%', 'V':value, 'D1C':loc, 'D1N':'Brasil' if loc=='1' else 'São Paulo', 'D2C':var, 'D3C':f'{year}{month:02}', 'D4C':cat,'D4N':name})
    return items


def test_official_values_and_hierarchy_are_preserved():
    result = normalize('7060', [response()])
    assert result['rows'][0][3:] == [0.0, -0.5, None, 100.0]
    assert result['categories']['7173']['level'] == 4
    assert result['locations']['3501']['level'] == '7'
    assert len(result['rows']) == 72


@pytest.mark.parametrize('value', ['...', '..', 'X', 'x', ''])
def test_missing_is_not_zero(value):
    assert number(value) is None


@pytest.mark.parametrize('value', ['NaN','inf','unexpected'])
def test_invalid_value_rejected(value):
    with pytest.raises(ValueError):
        number(value)


def test_partial_collection_is_rejected():
    raw = response()
    raw.pop()
    with pytest.raises(ValueError, match='faltam medidas'):
        normalize('7060', [raw])


def test_conflicting_duplicates_rejected():
    raw = response()
    duplicate = dict(raw[1], V='9.9')
    with pytest.raises(ValueError, match='divergentes'):
        normalize('7060', [raw + [duplicate]])


def test_unknown_hierarchy_rejected():
    with pytest.raises(ValueError):
        category_level('999.Sem hierarquia')


def test_failed_validation_preserves_published_data(tmp_path):
    valid = normalize('7060', [response()])
    publish(tmp_path, {'7060':valid})
    previous = (tmp_path / 'data/inflation/7060.json').read_bytes()
    broken = deepcopy(valid)
    broken['rows'][0][-1] = 101
    with pytest.raises(ValueError):
        publish(tmp_path, {'7060':broken})
    assert (tmp_path / 'data/inflation/7060.json').read_bytes() == previous
    assert load_detail(tmp_path, '7060') == valid
    assert json.loads(previous)['name'] == 'IPCA'
