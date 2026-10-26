import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)

def catalog():
    return json.loads((ROOT / 'catalog.json').read_text())

def database_url():
    url = os.getenv('DATABASE_URL', 'sqlite:///data/observatorio.db')
    if url.startswith('sqlite:///') and not url.startswith('sqlite:////') and url != 'sqlite:///:memory:':
        url = 'sqlite:///' + str(ROOT / url.removeprefix('sqlite:///'))
    return url
