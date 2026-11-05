"""Boletim determinístico da última coleta validada, sem inferência econômica."""
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from .revisions import EVENT_LABELS, decimal_value, latest_changes, read_history
from .snapshot import load_snapshot


def number(value):
    text = format(Decimal(str(value)), 'f')
    return text.replace('.', ',')


def month(value):
    return str(value)[5:7] + '/' + str(value)[:4]


def build_bulletin(frame, specs, manifest, history, meta):
    changes = latest_changes(history, meta)
    snapshot = manifest['snapshot_id']
    if changes is not None and changes['snapshot_id'] != snapshot:
        raise ValueError('Boletim e histórico pertencem a coletas diferentes')
    catalog = {int(s['code']): s for s in specs}
    counts = changes['counts'] if changes else None
    paragraphs = []
    if counts is None:
        paragraphs.append('Primeira base disponível para o boletim: ainda não há comparação com uma coleta anterior.')
    elif not any(counts.values()):
        paragraphs.append('Nenhuma mudança nos valores originais em relação à coleta anterior.')
    else:
        paragraphs.append(f"{changes['series_count']} indicadores tiveram mudanças: " + '; '.join(
            f'{count} {EVENT_LABELS[kind].lower()}' for kind, count in counts.items()) + '.')
    highlights, revisions = [], []
    if changes is not None:
        events = changes['events'].assign(_code_order=lambda rows: rows['code'].astype(int)).sort_values(['_code_order', 'reference_date'])
        for event in events.to_dict('records'):
            code = int(event['code'])
            spec = catalog[code]
            date = pd.Timestamp(event['reference_date'])
            prefix = f"{spec['name']} (SGS {code}), referência {month(date)}"
            if event['event_type'] == 'revision':
                text = f"{prefix}: {number(event['old_value'])} → {number(event['new_value'])} {event['unit']}; diferença de {number(event['difference'])} {event['difference_unit']}."
                revisions.append({'code': code, 'reference_date': event['reference_date'], 'text': text, 'source_url': spec['source_url']})
            elif event['event_type'] == 'new_observation':
                text = f"{prefix}: {number(event['new_value'])} {event['unit']}."
                # Compare consecutive calendar months inside the CURRENT validated snapshot.
                previous_date = date - pd.offsets.MonthBegin(1)
                previous = frame.loc[(frame.code == code) & (frame.date == previous_date), 'original']
                before = decimal_value(previous.iloc[0]) if len(previous) else None
                current = decimal_value(event['new_value'])
                delta = None
                delta_unit = None
                if before is not None and current is not None:
                    if 'diff_pp' in spec['allowed_transforms']:
                        delta, delta_unit = current - before, 'p.p.'
                    elif 'mom_pct' in spec['allowed_transforms'] and before > 0:
                        delta, delta_unit = (current / before - 1) * 100, '%'
                if delta is not None:
                    text += f" Variação frente a {month(previous_date)}: {number(delta.quantize(Decimal('0.01')))} {delta_unit}."
                elif spec.get('measure_type') != 'variation':
                    text += ' Variação mensal não calculada: ausência de base comparável ou transformação não permitida.'
                highlights.append({'code': code, 'reference_date': event['reference_date'], 'text': text, 'source_url': spec['source_url']})
    notes = [
        'Contagens representam observações (indicador × mês). Preenchimentos históricos e séries incluídas não são novas referências.',
        'Variações mensais comparam meses consecutivos na base atual. Revisões comparam o mesmo mês entre duas coletas. Não se ordenam grandezas de unidades diferentes como se fossem comparáveis.',
        'O horário de coleta/detecção não é a data oficial de divulgação. Coleta sem mudanças não significa ausência de inflação, juros ou movimento econômico.',
        'Resumo descritivo dos dados do BCB/SGS, sem interpretação causal. Atrasos e falhas posteriores são apresentados separadamente pelo monitor do painel.',
    ]
    report = {
        'schema_version': 1, 'snapshot_id': snapshot,
        'previous_snapshot_id': changes['previous_snapshot_id'] if changes else None,
        'created_at': manifest['created_at'], 'as_of': manifest['as_of'],
        'counts': counts, 'series_count': changes['series_count'] if changes else None,
        'paragraphs': paragraphs, 'highlights': highlights, 'revisions': revisions, 'notes': notes,
    }
    stamp = datetime.fromisoformat(manifest['created_at']).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')
    lines = ['# Boletim da coleta', '', f'Coleta validada: {stamp} (Brasília). Corte: {manifest["as_of"]}.', '', *paragraphs]
    for title, items in [('Novas referências e variações mensais', highlights), ('Revisões históricas', revisions)]:
        lines.extend(['', '## ' + title, ''])
        lines.extend(f"- {item['text']} [Fonte]({item['source_url']})" for item in items[:8])
        if not items:
            lines.append('Nenhum registro desta categoria na última comparação.' if changes else 'Comparação ainda indisponível.')
        if len(items) > 8:
            lines.append(f'Exibidos 8 de {len(items)} registros, em ordem de código SGS e referência. O JSON contém todos; consulte também o histórico de revisões.')
    lines.extend(['', '## Critérios', '', *['- ' + note for note in notes], '', f'Coleta: {snapshot}', f'Coleta anterior: {report["previous_snapshot_id"] or "não disponível"}'])
    report['markdown'] = '\n'.join(lines) + '\n'
    return report


def load_bulletin(root):
    root = Path(root)
    frame, specs, _, manifest = load_snapshot(root)
    pointer = json.loads((root / 'data/processed/latest.json').read_text())
    history, meta = read_history(root / pointer['path'], manifest)
    return build_bulletin(frame, specs, manifest, history, meta)
