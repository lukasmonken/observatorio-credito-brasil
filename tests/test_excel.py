from datetime import date
from io import BytesIO
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from observatorio.excel import build_excel

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SPEC = {"code": 1, "name": "Indicador", "unit": "%", "source_url": "https://www.bcb.gov.br/",
        "frequency": "M", "classification": "Taxa", "segment": "Total",
        "allowed_transforms": ["original", "ma3", "base100"]}
MANIFEST = {"snapshot_id": "test-snapshot", "created_at": "2026-11-03T12:00:00+00:00", "as_of": "2026-11-03", "price_base_month": "2026-09-01"}
PERIOD = (date(2026, 1, 1), date(2026, 2, 28))


def data():
    return pd.DataFrame({"code": [1, 1], "date": pd.to_datetime(["2026-01-01", "2026-02-01"]),
                         "name": ["Indicador", "Indicador"], "original": [0.0, np.nan],
                         "ma3": [1.25, 2.5], "snapshot_id": ["test-snapshot"] * 2})


def export(frame=None, spec=None, metric="original", period=PERIOD):
    return build_excel(data() if frame is None else frame, spec or SPEC, MANIFEST, metric, "%", period, "# Metodologia\n\nExemplo de metodologia.")


def read_workbook(content):
    with ZipFile(BytesIO(content)) as archive:
        assert archive.testzip() is None
        # XML produzido pelo exportador sob teste, sem arquivo externo.
        xml = {name: ET.fromstring(archive.read(name)) for name in archive.namelist() if name.endswith(".xml")}  # noqa: S314
        strings = ["".join(node.itertext()) for node in xml["xl/sharedStrings.xml"].findall("x:si", NS)]
        sheets = {}
        for index, sheet in enumerate(xml["xl/workbook.xml"].findall("x:sheets/x:sheet", NS), 1):
            rows = []
            root = xml[f"xl/worksheets/sheet{index}.xml"]
            for row in root.findall("x:sheetData/x:row", NS):
                cells = {}
                for cell in row.findall("x:c", NS):
                    value = cell.find("x:v", NS)
                    if value is not None:
                        cells[cell.attrib["r"]] = strings[int(value.text)] if cell.get("t") == "s" else float(value.text)
                rows.append(cells)
            sheets[sheet.attrib["name"]] = rows
        return sheets, xml


def test_workbook_has_numeric_zero_missing_blank_dates_and_provenance():
    sheets, xml = read_workbook(export())
    assert list(sheets) == ["Dados", "Indicador", "Metodologia", "Coleta"]
    assert sheets["Dados"][1]["D2"] == 0.0
    assert "D3" not in sheets["Dados"][2]
    assert sheets["Dados"][1]["B2"] == (date(2026, 1, 1) - date(1899, 12, 30)).days
    fields = {list(row.values())[0]: list(row.values())[1] for row in sheets["Coleta"][1:]}
    assert fields["Snapshot"] == "test-snapshot"
    assert fields["Início solicitado"] == "2026-01-01"
    assert fields["Observações exportadas"] == 2
    assert xml["xl/worksheets/sheet1.xml"].find("x:autoFilter", NS) is not None
    assert xml["xl/worksheets/sheet1.xml"].find("x:sheetViews/x:sheetView/x:pane", NS).get("state") == "frozen"


def test_selected_transformation_is_exported_without_recalculation_or_mutation():
    frame = data()
    original = frame.copy(deep=True)
    sheets, _ = read_workbook(export(frame=frame, metric="ma3"))
    assert sheets["Dados"][1]["F2"] == 1.25
    assert sheets["Dados"][2]["F3"] == 2.5
    pd.testing.assert_frame_equal(frame, original)


def test_text_never_becomes_formula_or_external_link():
    frame = data()
    frame["name"] = ["=HYPERLINK(\"https://example.com\",\"click\")", "+1+1"]
    spec = {**SPEC, "description": "=1+1", "limitations": ["@SUM(A1:A2)"]}
    sheets, xml = read_workbook(export(frame=frame, spec=spec))
    assert sheets["Dados"][1]["C2"].startswith("=HYPERLINK")
    assert any("=1+1" in row.values() for row in sheets["Indicador"])
    assert all(not root.findall(".//x:f", NS) for root in xml.values())
    assert all(not root.findall(".//x:hyperlink", NS) for root in xml.values())


@pytest.mark.parametrize("case", ["empty", "infinity", "wrong_snapshot", "wrong_series", "duplicate", "bad_date", "outside_period"])
def test_invalid_exports_are_rejected(case):
    frame = data()
    if case == "empty":
        frame = frame.iloc[:0]
    elif case == "infinity":
        frame.loc[0, "original"] = float("inf")
    elif case == "wrong_snapshot":
        frame["snapshot_id"] = "other"
    elif case == "wrong_series":
        frame["code"] = 2
    elif case == "duplicate":
        frame.loc[1, "date"] = frame.loc[0, "date"]
    elif case == "bad_date":
        frame.loc[1, "date"] = pd.NaT
    else:
        frame.loc[1, "date"] = pd.Timestamp("2026-03-01")
    with pytest.raises(ValueError):
        export(frame=frame)


def test_forbidden_transform_rejected():
    with pytest.raises(ValueError, match="Transformação"):
        export(metric="yoy_pct")


def test_explorer_excel_respects_period_and_rebased_index(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from observatorio.config import ROOT
    import observatorio.excel

    captured = []
    real_export = observatorio.excel.build_excel
    def capture(*args):
        result = real_export(*args)
        captured.append((args, result))
        return result
    monkeypatch.setattr(observatorio.excel, "build_excel", capture)
    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value("Explorador de indicadores").run()
    app.selectbox(key="explorer_code").set_value(20539).run()
    app.selectbox[1].set_value("base100").run()
    app.date_input(key="explorer_dates").set_value((date(2020, 1, 1), date(2020, 12, 31))).run()
    assert not app.exception
    args, content = captured[-1]
    assert args[3] == "base100"
    assert args[0].date.min() == pd.Timestamp("2020-01-01")
    assert args[0].date.max() == pd.Timestamp("2020-12-01")
    sheets, _ = read_workbook(content)
    assert sheets["Dados"][1]["F2"] == 100
    assert len(sheets["Dados"]) == 13
    assert any(button.proto.label == "Baixar dados filtrados · Excel" for button in app.get("download_button"))
