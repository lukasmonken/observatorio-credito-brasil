"""Gera referências Python para testar os cálculos executados no navegador."""
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from observatorio.revisions import compare_collections
from observatorio.transform import lag_pairs

config = json.loads((ROOT / "web/generated/site.json").read_text())
data = json.loads((ROOT / "web/generated" / config["data"]).read_text())
frame = pd.DataFrame(data["rows"])
frame["date"] = pd.to_datetime(frame.date)
cases = []
for xc, yc, metric in [(432, 21084, "diff_pp"), (20539, 20631, "yoy_pct")]:
    x = frame.loc[frame.code == xc].set_index("date")[metric].dropna()
    y = frame.loc[frame.code == yc].set_index("date")[metric].dropna()
    for lag in [0, 6, 12, 24]:
        pairs = lag_pairs(x, y, lag).loc["2015-01-01":"2025-06-01"]
        records = pairs.rename_axis("date").reset_index()
        records["date"] = records.date.dt.strftime("%Y-%m-%d")
        r = pairs.x.corr(pairs.y) if len(pairs) >= 12 and pairs.x.std() > 0 and pairs.y.std() > 0 else None
        cases.append(dict(xc=xc, yc=yc, metric=metric, lag=lag, start="2015-01-01", end="2025-06-01", pairs=records.to_dict("records"), r=r))
comparisons = []
meta = data["history_meta"]
if meta:
    ids = [meta["baseline_snapshot_id"], *[c["snapshot_id"] for c in meta["comparisons"]]]
    for earlier, later in [(ids[0], ids[-1]), (ids[-2], ids[-1])]:
        result = compare_collections(pd.DataFrame(data["history"]), meta, earlier, later)
        comparisons.append(dict(earlier=earlier, later=later, expected=result.to_dict("records")))
(ROOT / "web/generated/parity.json").write_text(json.dumps(dict(correlations=cases, comparisons=comparisons), allow_nan=False))
