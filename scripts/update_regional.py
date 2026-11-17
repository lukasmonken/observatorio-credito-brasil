"""Refresh eight calendar quarters from the IBGE quarterly PNAD."""
import json
import re
from pathlib import Path

import requests

URL = "https://servicodados.ibge.gov.br/api/v3/agregados/4099/periodos/-8/variaveis/4099"
TARGET = Path(__file__).resolve().parents[1] / "data/regional/desocupacao.json"
IDS = {
    "N1": {"1"},
    "N2": set("1 2 3 4 5".split()),
    "N3": set("11 12 13 14 15 16 17 21 22 23 24 25 26 27 28 29 31 32 33 35 41 42 43 50 51 52 53".split()),
}


def normalize(payload):
    variable, = payload
    result, = variable["resultados"]
    if str(variable["id"]) != "4099" or variable["unidade"] != "%" or result["classificacoes"]:
        raise ValueError("Indicador inesperado")
    records = {}
    periods = None
    for item in result["series"]:
        loc = item["localidade"]
        key = loc["nivel"]["id"], str(loc["id"])
        rates = {q: float(v) for q, v in sorted(item["serie"].items())}
        if key in records or any(not 0 <= v <= 100 for v in rates.values()):
            raise ValueError("Localidade duplicada ou taxa inválida")
        if len(rates) != 8 or any(not re.fullmatch(r"\d{4}0[1-4]", q) for q in rates):
            raise ValueError("Janela trimestral inválida")
        quarters = [int(q[:4]) * 4 + int(q[-1]) for q in rates]
        if quarters[-1] - quarters[0] != 7 or (periods is not None and rates.keys() != periods):
            raise ValueError("Trimestres incompatíveis")
        periods = rates.keys()
        records[key] = {"level": key[0], "name": loc["nome"], "rates": rates}
    if records.keys() != {(level, code) for level, codes in IDS.items() for code in codes}:
        raise ValueError("Cobertura territorial incompleta")
    return [records[k] for k in sorted(records)]


def main():
    response = requests.get(URL, params={"localidades": "N1[all]|N2[all]|N3[all]"}, timeout=90)
    response.raise_for_status()
    records = normalize(response.json())
    if TARGET.exists():
        previous = json.loads(TARGET.read_text(encoding="utf-8"))
        if max(records[0]["rates"]) < max(previous[0]["rates"]):
            raise ValueError("A consulta retornou uma janela anterior à publicada")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    tmp = TARGET.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(TARGET)


if __name__ == "__main__":
    main()
