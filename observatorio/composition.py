"""Participação de modalidades no saldo total do mesmo segmento e mês."""
import pandas as pd


def composition_rows(frame, specs, segment):
    if segment not in ("PF", "PJ"):
        raise ValueError("Segmento inválido")
    selected = [s for s in specs if s.get("credit_composition") and s["segment"] == segment]
    denominator = 20541 if segment == "PF" else 20540
    dates = sorted(frame.loc[frame.code.isin([denominator, *[s["code"] for s in selected]]), "date"].unique())
    if frame.duplicated(["code", "date"]).any():
        raise ValueError("Observações duplicadas")
    indexed = frame.set_index(["code", "date"])
    def value(code, date):
        return indexed.at[(code, date), "original"] if (code, date) in indexed.index else float("nan")
    result = []
    for date in dates:
        total = value(denominator, date)
        for spec in selected:
            amount = value(spec["code"], date)
            valid = pd.notna(amount) and pd.notna(total) and 0 <= amount <= total and total > 0
            result.append(dict(date=date, code=spec["code"], modality=spec["modality"],
                               segment=segment, resources=spec["resources"], original=amount,
                               denominator_code=denominator, total=total,
                               share=100 * amount / total if valid else float("nan"),
                               source=spec["source"], source_url=spec["source_url"]))
    return pd.DataFrame(result, columns=["date", "code", "modality", "segment", "resources", "original", "denominator_code", "total", "share", "source", "source_url"])
