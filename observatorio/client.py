"""BCData/SGS: janelas inferiores a 10 anos e evidência imutável por execução."""
import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import requests

log = logging.getLogger(__name__)

class APIError(RuntimeError):
    pass

def windows(start: date, end: date):
    if start > end:
        raise ValueError('Início posterior ao fim')
    cursor = start
    while cursor <= end:
        stop = min(end, date(cursor.year + 4, 12, 31))
        yield cursor, stop
        cursor = stop + timedelta(days=1)

class SGSClient:
    def __init__(self, raw_dir, run_id, timeout=30, attempts=3, session=None, sleeper=time.sleep, monthly_codes=()):
        self.raw_dir = Path(raw_dir) / run_id
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.run_id, self.timeout, self.attempts = run_id, timeout, attempts
        self.session = session or requests.Session()
        self.sleep = sleeper
        self.monthly_codes = set(monthly_codes)

    def fetch(self, code, start, end):
        all_rows = []
        for a, b in ([(start, end)] if code in self.monthly_codes else windows(start, end)):
            params = {'formato':'json','dataInicial':a.strftime('%d/%m/%Y'),'dataFinal':b.strftime('%d/%m/%Y')}
            if code in self.monthly_codes:
                params = {'formato': 'json'}
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados'
            for attempt in range(self.attempts):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout)
                    # Preserve inclusive invalid responses and transient errors for auditing.
                    body = response.content
                    stem = f'{code}_{a}_{b}_attempt{attempt}'
                    (self.raw_dir / f'{stem}.body').write_bytes(body)
                    evidence = dict(run_id=self.run_id, code=code, url=response.url, params=params,
                        start=str(a), end=str(b), extracted_at=datetime.now(timezone.utc).isoformat(),
                        status=response.status_code, sha256=hashlib.sha256(body).hexdigest(), body_file=f'{stem}.body')
                    (self.raw_dir / f'{stem}.json').write_text(json.dumps(evidence, indent=2))
                    if response.status_code == 429 or response.status_code >= 500:
                        raise requests.exceptions.ConnectionError(f'HTTP transitório {response.status_code}')
                    if not response.ok:
                        raise APIError(f'HTTP {response.status_code}: {body[:160]!r}')
                    try:
                        rows = response.json()
                    except ValueError as exc:
                        raise APIError('JSON inválido') from exc
                    if not isinstance(rows, list):
                        raise APIError(f'Resposta não é lista SGS: {str(rows)[:160]}')
                    if code in self.monthly_codes:
                        rows = [row for row in rows if start <= datetime.strptime(row['data'], '%d/%m/%Y').date() <= end]
                    all_rows.extend(rows)
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                    if attempt + 1 == self.attempts:
                        raise APIError(f'Falha após {self.attempts} tentativas: {exc}') from exc
                    log.warning('SGS %s tentativa %s: %s', code, attempt + 1, exc)
                    retry_after = response.headers.get('Retry-After', '') if 'response' in locals() else ''
                    delay = min(float(retry_after), 60) if retry_after.isdigit() else 2 ** attempt
                    self.sleep(delay)
        return all_rows

class ReplayClient:
    """Reprocessa evidências reais verificando checksum, status e intervalo solicitado."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.envelopes = []
        for path in self.directory.glob('*.json'):
            d = json.loads(path.read_text())
            if 'body_file' in d:
                self.envelopes.append(d)

    def fetch(self, code, start, end):
        relevant = [d for d in self.envelopes if d['code'] == code and d['status'] == 200]
        if not relevant:
            raise APIError(f'Nenhuma resposta bruta válida para SGS {code}')
        # Keep only final successful extraction per identical window.
        unique = {(d['start'],d['end']):d for d in sorted(relevant,key=lambda d:d['extracted_at'])}
        cursor = start
        rows = []
        for d in sorted(unique.values(), key=lambda d:d['start']):
            a, b = date.fromisoformat(d['start']), date.fromisoformat(d['end'])
            if b < start or a > end:
                continue
            if a > cursor:
                raise APIError(f'Lacuna de extração a partir de {cursor}')
            cursor = max(cursor, b + timedelta(days=1))
            body = (self.directory / d['body_file']).read_bytes()
            if hashlib.sha256(body).hexdigest() != d['sha256']:
                raise APIError('Checksum do bruto divergente')
            items = json.loads(body)
            if not isinstance(items, list):
                raise APIError('Bruto não é lista')
            for item in items:
                dt = datetime.strptime(item['data'], '%d/%m/%Y').date()
                if start <= dt <= end:
                    rows.append(item)
        if cursor <= end:
            raise APIError(f'Extração não cobre fim solicitado: {end}')
        return rows
