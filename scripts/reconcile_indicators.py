"""Confere a última observação publicada de quatro séries com uma consulta nova ao SGS."""

from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.monitor_pages import fetch

# O endpoint de valores não devolve unidades. Estas referências são independentes do catálogo publicado.
REFERENCES = {
    20539: ("Saldo da carteira de crédito", "R$ milhões", "M"),
    20631: ("Concessões de crédito", "R$ milhões", "M"),
    3698: ("Dólar de venda, média mensal", "R$/US$", "M"),
    22099: ("PIB observado, índice de volume", "índice", "Q"),
}


def period(day, frequency):
    quarter = (day.month - 1) // 3
    first = day.replace(month=3 * quarter + 1 if frequency == "Q" else day.month, day=1)
    month = first.month + (2 if frequency == "Q" else 0)
    last = day.replace(month=month, day=monthrange(day.year, month)[1])
    label = f"{quarter + 1}º tri/{day.year}" if frequency == "Q" else day.strftime("%m/%Y")
    return first, last, label


def reconcile(session, data, code):
    name, unit, frequency = REFERENCES[code]
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    result = dict(code=code, name=name, source=url, expected_unit=unit, expected_frequency=frequency)
    try:
        meta, = [item for item in data["catalog"] if item["code"] == code]
        rows = [row for row in data["rows"] if row["code"] == code]
        latest = max(row["date"] for row in rows)
        row, = [r for r in rows if r["date"] == latest]
        first, last, label = period(date.fromisoformat(latest), frequency)
        result.update(published_value=row["original"], published_unit=meta["unit"],
                      published_period=row["reference_period"], published_frequency=meta["frequency"],
                      expected_period=label)
    except (KeyError, ValueError, TypeError):
        return dict(result, status="divergência", detail="Série ou referência publicada ausente, duplicada ou inválida.")
    try:
        response = session.get(url, params={"formato": "json", "dataInicial": first.strftime("%d/%m/%Y"),
                               "dataFinal": last.strftime("%d/%m/%Y")}, timeout=(8, 20))
        result["source"] = response.url
        response.raise_for_status()
        observations = response.json()
        if not isinstance(observations, list):
            raise ValueError
        if len(observations) != 1:
            return dict(result, status="inconclusivo", detail=f"Fonte retornou {len(observations)} observações.")
        official = observations[0]
        source_date = datetime.strptime(official["data"], "%d/%m/%Y").date()
        value = Decimal(str(official["valor"]).replace(",", "."))
        if not value.is_finite():
            raise ValueError
        result.update(source_value=str(value), source_date=source_date.isoformat(),
                      source_period=period(source_date, frequency)[2])
    except (requests.RequestException, KeyError, ValueError, TypeError, InvalidOperation):
        return dict(result, status="inconclusivo", detail="Fonte indisponível ou resposta inválida.")
    try:
        matches = Decimal(str(row["original"])) == value
    except InvalidOperation:
        matches = False
    errors = [field for field, ok in (
        ("valor", matches), ("unidade", meta["unit"] == unit), ("frequência", meta["frequency"] == frequency),
        ("período", row["reference_period"] == label == result["source_period"] and latest == first.isoformat())
    ) if not ok]
    return dict(result, status="divergência" if errors else "confere", detail=", ".join(errors))


def main():
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": []}
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1,
                      status_forcelist=[429, 502, 503, 504], respect_retry_after_header=False)))
        try:
            config = json.loads(fetch(session, "site.json"))
            raw = fetch(session, config["data"])
            if hashlib.sha256(raw).hexdigest() != config["sha256"]:
                raise ValueError("Checksum inválido")
            data = json.loads(raw)
            report["snapshot"] = data["manifest"]["snapshot_id"]
            report["results"] = [reconcile(session, data, code) for code in REFERENCES]
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            report["error"] = f"Publicação indisponível ou inválida: {error}"
    output = Path("work/reconciliation.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    lines = ["## Conferência dos indicadores", "", f"Coleta: {report.get('snapshot', 'indisponível')}", ""]
    for item in report["results"]:
        lines.append(f"- **{item['name']}** — {item['status']}. "
                     f"Publicado: {item.get('published_value', '—')} {item.get('published_unit', '')} "
                     f"({item.get('published_period', '—')}). "
                     f"[SGS {item['code']}]({item['source']}): {item.get('source_value', '—')} "
                     f"{item['expected_unit']} ({item.get('source_period', '—')}). {item['detail']}")
    if "error" in report:
        lines.append(report["error"])
    summary = "\n".join(lines) + "\n"
    print(summary)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(summary)
    return int("error" in report or any(r["status"] != "confere" for r in report["results"]))


if __name__ == "__main__":
    raise SystemExit(main())
