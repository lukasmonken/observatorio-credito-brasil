"""Official SIDRA inflation observations, separate from SGS series identifiers."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TABLES = {
    "7060": {"name": "IPCA", "variables": ["63", "69", "2265", "66"]},
    "7063": {"name": "INPC", "variables": ["44", "68", "2292", "45"]},
    "7062": {"name": "IPCA-15", "variables": ["355", "356", "1120", "357"]},
}
GROUPS = "7169,7170,7445,7486,7558,7625,7660,7712,7766,7786"
COLUMNS = ["date", "location", "category", "monthly", "ytd", "annual", "weight"]
MISSING = {"...", "..", "-", "X", ""}


def number(value):
    if value in MISSING:
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Valor não finito recebido do IBGE")
    return result


def category_level(name):
    if name == "Índice geral":
        return 0
    match = re.match(r"^(\d+)\.", name)
    levels = {1: 1, 2: 2, 4: 3, 7: 4}
    if not match or len(match[1]) not in levels:
        raise ValueError(f"Categoria IBGE sem hierarquia reconhecida: {name}")
    return levels[len(match[1])]


def normalize(table, responses):
    variables = TABLES[table]["variables"]
    cells, categories, locations = {}, {}, {}
    for response in responses:
        if not isinstance(response, list) or len(response) < 2:
            raise ValueError("Resposta SIDRA vazia ou inválida")
        header = response[0]
        def dimension(label):
            matches = [k[:-1] for k, v in header.items() if k.endswith("N") and v == label]
            if len(matches) != 1:
                raise ValueError(f"Dimensão ausente: {label}")
            return matches[0]
        variable, period = dimension("Variável"), dimension("Mês")
        category = dimension("Geral, grupo, subgrupo, item e subitem")
        geographic = [k[:-1] for k in header if re.fullmatch(r"D\d+N", k) and k[:-1] not in {variable, period, category}]
        if len(geographic) != 1:
            raise ValueError("Dimensão geográfica ambígua")
        locality = geographic[0]
        for item in response[1:]:
            var = item[variable + "C"]
            if var not in variables or item["MN"] != "%":
                raise ValueError("Variável ou unidade inesperada")
            ref = item[period + "C"]
            if not re.fullmatch(r"\d{4}(0[1-9]|1[0-2])", ref):
                raise ValueError("Referência inválida")
            loc, cat = item[locality + "C"], item[category + "C"]
            name = item[category + "N"]
            categories[cat] = {"name": name, "level": category_level(name)}
            locations[loc] = {"name": item[locality + "N"], "level": item["NC"]}
            key = (f"{ref[:4]}-{ref[4:]}-01", loc, cat)
            values = cells.setdefault(key, {})
            value = number(item["V"])
            if var in values and values[var] != value:
                raise ValueError("Observação duplicada com valores divergentes")
            values[var] = value
    rows = []
    for key, values in sorted(cells.items()):
        if set(values) != set(variables):
            raise ValueError("Coleta parcial: faltam medidas")
        rows.append([*key, *[values[v] for v in variables]])
    result = {"schema_version": 1, "table": table, "name": TABLES[table]["name"],
              "source_url": f"https://sidra.ibge.gov.br/tabela/{table}", "columns": COLUMNS,
              "categories": categories, "locations": locations, "rows": rows,
              "created_at": datetime.now(timezone.utc).isoformat()}
    validate(result)
    return result


def validate(data):
    if data.get("schema_version") != 1 or data.get("columns") != COLUMNS or data.get("table") not in TABLES:
        raise ValueError("Formato do detalhamento de inflação inválido")
    rows = data["rows"]
    if not rows or not any(c["level"] == 4 for c in data["categories"].values()) or len(data["locations"]) < 2:
        raise ValueError("Cobertura de inflação incompleta")
    keys = set()
    for row in rows:
        if len(row) != 7 or row[1] not in data["locations"] or row[2] not in data["categories"]:
            raise ValueError("Observação inválida")
        key = tuple(row[:3])
        if key in keys:
            raise ValueError("Observação duplicada")
        keys.add(key)
        if any(v is not None and (not isinstance(v, (float, int)) or not math.isfinite(v)) for v in row[3:]):
            raise ValueError("Valor inválido")
        if row[6] is not None and not 0 <= row[6] <= 100:
            raise ValueError("Peso fora do intervalo")
    general = [r for r in rows if r[1:3] == ["1", "7169"] and r[3] is not None]
    if len(general) < 12:
        raise ValueError("Histórico nacional insuficiente")
    latest = max(r[0] for r in general)
    for loc in data["locations"]:
        if not any(r[0] == latest and r[1] == loc and r[2] == "7169" and r[3] is not None for r in rows):
            raise ValueError("Localidade sem referência mais recente")
    return data


def collect(table, session=None):
    session = session or requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    responses = []
    variables = ",".join(TABLES[table]["variables"])
    for territory, categories in [("n1/1", "all"), ("n6/all/n7/all", GROUPS)]:
        url = f"https://apisidra.ibge.gov.br/values/t/{table}/{territory}/v/{variables}/p/last%2024/c315/{categories}"
        response = session.get(url, timeout=(15, 90))
        response.raise_for_status()
        raw = response.json()
        responses.append(raw)
    return normalize(table, responses)


def load_detail(root: Path, table):
    data = json.loads((root / "data/inflation" / f"{table}.json").read_text())
    return validate(data)


def publish(root: Path, datasets):
    """Stage all tables before replacement; a failed collection leaves existing files intact."""
    directory = root / "data/inflation"
    prepared = {}
    for table, data in datasets.items():
        validate(data)
        old = directory / f"{table}.json"
        if old.exists():
            previous = load_detail(root, table)
            if max(r[0] for r in data["rows"]) < max(r[0] for r in previous["rows"]):
                raise ValueError("A fonte regrediu a referência publicada")
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        prepared[table] = encoded
    directory.mkdir(parents=True, exist_ok=True)
    for table, encoded in prepared.items():
        temporary = directory / f"{table}.tmp"
        temporary.write_bytes(encoded)
        temporary.replace(directory / f"{table}.json")
    return {table: hashlib.sha256(content).hexdigest() for table, content in prepared.items()}
