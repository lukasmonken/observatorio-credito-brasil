"""CSV para planilhas em português ou ferramentas analíticas, sem arredondamento."""
import csv
from datetime import date, datetime
from io import StringIO
import json
import math
from numbers import Number
from pathlib import Path
import re

import pandas as pd

COLUMN_LABELS = json.loads(Path(__file__).with_name("export_columns.json").read_text())


def build_csv(frame, profile="analysis"):
    if profile not in {"excel", "analysis"}:
        raise ValueError("Perfil CSV inválido")
    localized = profile == "excel"

    def cell(value, key=None):
        if pd.isna(value):
            return ""
        if isinstance(value, (date, datetime)):
            return value.isoformat() if not isinstance(value, datetime) or value.time().isoformat() != "00:00:00" else value.date().isoformat()
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, Number):
            if not math.isfinite(float(str(value))):
                raise ValueError("Número não finito na exportação")
            return str(value).replace(".", ",") if localized else str(value)
        text = str(value)
        if key in {"old_value", "new_value", "difference"} and re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return text.replace(".", ",") if localized else text
        # Textos nunca são fórmulas; números negativos continuam numéricos.
        if re.match(r"^[\s]*[=+@-]", text) or text.startswith(("\t", "\r", "\n")):
            text = "'" + text
        return text

    output = StringIO(newline="")
    writer = csv.writer(output, delimiter=";" if localized else ",", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([cell(COLUMN_LABELS.get(key, key) if localized else key) for key in frame.columns])
    writer.writerows([cell(value, key) for key, value in zip(frame.columns, row, strict=True)] for row in frame.itertuples(index=False, name=None))
    return output.getvalue().encode("utf-8-sig")
