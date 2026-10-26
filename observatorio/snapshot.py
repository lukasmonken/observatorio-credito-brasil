import json
from pathlib import Path
import pandas as pd
from .config import ROOT

def load_snapshot(root=ROOT):
    pointer=json.loads((root/'data/processed/latest.json').read_text())
    directory=root/pointer['path']
    manifest=json.loads((directory/'manifest.json').read_text())
    df=pd.read_csv(directory/'analytics.csv',parse_dates=['date'])
    catalog=json.loads((directory/'catalog.json').read_text())
    quality=pd.read_csv(directory/'quality.csv')
    return df,catalog,quality,manifest
