"""Gera Markdown/JSON da coleta validada e o resumo do GitHub Actions."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from observatorio.bulletin import load_bulletin


def write_bulletin(root, output, summary=None):
    report = load_bulletin(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stem = 'boletim-' + report['snapshot_id']
    (output / (stem + '.md')).write_text(report['markdown'], encoding='utf-8')
    (output / (stem + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    if summary:
        with Path(summary).open('a', encoding='utf-8') as stream:
            stream.write(report['markdown'])
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/bulletin')
    args = parser.parse_args()
    result = write_bulletin(ROOT, args.output, os.environ.get('GITHUB_STEP_SUMMARY'))
    print('Boletim gerado para a coleta ' + result['snapshot_id'])
