"""Verifica a publicação pública sem alterar dados ou depender do servidor Streamlit."""

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://lukasmonken.github.io/observatorio-credito-brasil/'
GRACE_SECONDS = 3600
MAX_BYTES = 20 * 1024 * 1024


class CheckError(ValueError):
    pass


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.styles = []
        self.main = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'main' and attrs.get('id') == 'content':
            self.main = True
        if tag == 'script' and attrs.get('type') == 'module':
            self.scripts.append(attrs.get('src', ''))
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.styles.append(attrs.get('href', ''))


def fetch(session, relative):
    # All destinations are fixed or validated relative filenames; never send credentials.
    if relative and not re.fullmatch(r'(?:assets/[A-Za-z0-9_-]+\.(?:js|css)|site\.json|data-[a-f0-9]{16}\.json)', relative):
        raise CheckError('Caminho público inválido.')
    with session.get(urljoin(SITE, relative), timeout=(10, 30), allow_redirects=False,
                     stream=True, headers={'Cache-Control': 'no-cache'}) as response:
        if response.status_code != 200:
            raise CheckError(f'HTTP {response.status_code} em {relative or "página inicial"}.')
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                raise CheckError('Resposta excede o limite de 20 MiB.')
        if not content:
            raise CheckError('Resposta vazia.')
        return bytes(content)


def parse_json(raw):
    def invalid(_):
        raise CheckError('JSON contém número não finito.')
    result = json.loads(raw, parse_constant=invalid)
    if not isinstance(result, dict):
        raise CheckError('JSON público deve ser um objeto.')
    return result


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise CheckError('Data de coleta sem fuso horário.')
    return result


def inspect_site(session, expected, now):
    parser = Assets()
    parser.feed(fetch(session, '').decode('utf-8'))
    if not parser.main or not parser.scripts or not parser.styles:
        raise CheckError('HTML não contém a estrutura esperada do dashboard.')
    for asset in set(parser.scripts + parser.styles):
        fetch(session, asset)
    config = parse_json(fetch(session, 'site.json'))
    if config.get('schema_version') != 1 or not re.fullmatch(r'data-[a-f0-9]{16}\.json', str(config.get('data', ''))):
        raise CheckError('Ponteiro público inválido.')
    raw = fetch(session, config['data'])
    digest = hashlib.sha256(raw).hexdigest()
    if digest != config.get('sha256') or config['data'] != f'data-{digest[:16]}.json':
        raise CheckError('Checksum dos dados publicados não confere.')
    data = parse_json(raw)
    manifest = data.get('manifest', {})
    rows, catalog = data.get('rows'), data.get('catalog')
    if (not isinstance(manifest, dict) or data.get('schema_version') != 1 or not isinstance(rows, list) or not rows
            or not isinstance(catalog, list) or not catalog
            or manifest.get('snapshot_id') != config.get('snapshot_id')
            or len(rows) != manifest.get('rows') or len(catalog) != manifest.get('series')):
        raise CheckError('Dados públicos incompletos ou inconsistentes com o manifesto.')
    codes = {item['code'] for item in catalog}
    if len(codes) != len(catalog) or {row['code'] for row in rows} != codes:
        raise CheckError('Catálogo e séries publicadas não correspondem.')
    age = (now - stamp(manifest['created_at'])).total_seconds()
    expected_age = (now - stamp(expected['created_at'])).total_seconds()
    if min(age, expected_age) < -3600:
        raise CheckError('Horário da coleta está no futuro.')
    warnings = []
    if expected_age > 30 * 3600:
        warnings.append('A última base válida do repositório tem mais de 30 horas; conferir o monitor da coleta.')
    status = 'ok'
    if manifest['snapshot_id'] != expected['snapshot_id']:
        if expected_age > GRACE_SECONDS:
            raise CheckError('O site não exibe a última base válida há mais de uma hora.')
        status = 'pending'
        warnings.append('Uma base nova aguarda publicação; tolerância de uma hora após a validação.')
    elif any(manifest.get(key) != expected.get(key) for key in ('rows', 'series', 'created_at', 'as_of')):
        raise CheckError('Metadados públicos divergem da coleta identificada no repositório.')
    return dict(status=status, published_snapshot=manifest['snapshot_id'],
                expected_snapshot=expected['snapshot_id'], rows=len(rows), series=len(catalog), warnings=warnings)


def check(root, session, now):
    report = dict(checked_at=now.isoformat(), site=SITE, status='alert', errors=[])
    try:
        pointer = json.loads((root / 'data/processed/latest.json').read_text())
        directory = (root / pointer['path']).resolve()
        directory.relative_to((root / 'data/processed').resolve())
        expected = json.loads((directory / 'manifest.json').read_text())
        report.update(inspect_site(session, expected, now))
    except requests.RequestException:
        report['errors'].append('Falha de conexão, TLS ou timeout ao consultar o site público.')
    except CheckError as error:
        report['errors'].append(str(error))
    except (ValueError, KeyError, TypeError, OSError):
        report['errors'].append('Configuração local ou formato dos dados públicos inválido.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/pages-monitor.json')
    args = parser.parse_args()
    with requests.Session() as session:
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 502, 503, 504],
                      allowed_methods=['GET'], respect_retry_after_header=False)
        session.mount('https://', HTTPAdapter(max_retries=retry))
        report = check(ROOT, session, datetime.now(timezone.utc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    lines = [f"Estado HTTP/dados: {report['status']}", *report['errors'], *report.get('warnings', [])]
    if report.get('published_snapshot'):
        lines += [f"Coleta publicada: {report['published_snapshot']}", f"Coleta esperada: {report['expected_snapshot']}"]
    text = '## Monitoramento do site publicado\n\n' + '\n\n'.join(lines) + '\n'
    print(text)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write(text)
    return int(report['status'] == 'alert')


if __name__ == '__main__':
    sys.exit(main())
