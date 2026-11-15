"""Aboard web server.

Serves the website in ./static and a small JSON API. It reuses the desktop app's code in ../app:
rules and NASA baselines decide every status; a local Ollama model (Llama 3.2 3B) reads entries,
explains results and answers questions. Only the Python standard library and Pillow are needed.

Run:  python3 server.py --port 8080
"""
import argparse
import json
import os
import secrets
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
APP = HERE.parent / 'app'
sys.path.insert(0, str(APP))
os.environ.setdefault('ABOARD_DATA_DIR', str(HERE / 'data'))

import ai_core  # noqa: E402
from baseline import baseline, compare  # noqa: E402
from demo_journal import seed_demo  # noqa: E402
from dialogue import normalize, urgent_request  # noqa: E402
from medical_followup import WELLBEING, apply_followup, wellbeing_summary  # noqa: E402
from nasa_reference import NASA_MEASUREMENTS, assess, supported_entry  # noqa: E402
from storage import Journal  # noqa: E402

CREW = ('mo', 'parisa', 'nayan')
STATIC = HERE / 'static'
MODEL = os.environ.get('ABOARD_OLLAMA_MODEL', ai_core.TEXT_MODEL)
LLM_SLOTS = threading.BoundedSemaphore(int(os.environ.get('ABOARD_LLM_SLOTS', '2')))
MAX_BODY = 64 * 1024
MAX_SESSIONS = 1000
MAX_ENTRIES = 200

# ------------------------------------------------------------------------------------------- data
journal = Journal(Path(os.environ['ABOARD_DATA_DIR']))
for name in CREW:
    if name not in journal.profiles():
        journal.add_profile(name)
seed_demo(journal)
DEMO = {name: journal.records(name) for name in CREW}
SESSIONS = OrderedDict()          # session id -> {crew: [records added by this visitor]}
SESSION_LOCK = threading.Lock()


def visitor_records(sid, crew):
    with SESSION_LOCK:
        extra = SESSIONS.get(sid, {}).get(crew, [])
        return DEMO[crew] + list(extra)


def add_record(sid, crew, record):
    with SESSION_LOCK:
        bucket = SESSIONS.setdefault(sid, {})
        SESSIONS.move_to_end(sid)
        rows = bucket.setdefault(crew, [])
        rows.append(record)
        del rows[:-MAX_ENTRIES]
        while len(SESSIONS) > MAX_SESSIONS:
            SESSIONS.popitem(last=False)


# ------------------------------------------------------------------------------------------- views
LABELS = {key: (label, unit) for label, (key, unit) in NASA_MEASUREMENTS.items()}
BODY_SITES = {'brain': ('sleep',), 'eyes': ('trt250_left', 'trt250_right'),
              'heart': ('pulse', 'systolic', 'diastolic'),
              'labs': ('serum_sodium', 'serum_potassium', 'serum_creatinine', 'serum_glucose'),
              'calf_left': ('calf_csa_left',), 'calf_right': ('calf_csa_right',)}


def site_level(status, keys):
    levels = [status.get(key, 'none') for key in keys]
    return next((level for level in ('alert', 'watch', 'ok') if level in levels), 'none')


def today(sid, crew):
    records = visitor_records(sid, crew)
    latest, status = ai_core.snapshot(records)
    tiles = []
    for label, (key, unit) in NASA_MEASUREMENTS.items():
        value = latest.get(key)
        comparison = compare(crew, key, value) if value not in (None, '') else None
        base = comparison or baseline(crew, key)
        tiles.append({'key': key, 'label': label, 'unit': unit, 'value': value, 'status': status.get(key, 'none'),
                      'kind': base['kind'], 'badge': base['badge'], 'low': base['low'], 'high': base['high'],
                      'baseline': base['value'], 'range_text': base['range_text'], 'source': base['source'],
                      'summary': comparison['summary'] if comparison else 'No reading yet'})
    return {'crew': crew, 'tiles': tiles, 'mood': ai_core.mood_summary(records),
            'body': {site: site_level(status, keys) for site, keys in BODY_SITES.items()},
            'entries': len(records)}


def trends(sid, crew):
    records = visitor_records(sid, crew)
    out = []
    for label, (key, unit) in NASA_MEASUREMENTS.items():
        series = []
        for record in records:
            try:
                series.append([record['stamp'][:10], float(record['checkin'][key])])
            except (KeyError, TypeError, ValueError):
                continue
        base = baseline(crew, key)
        out.append({'key': key, 'label': label, 'unit': unit, 'series': series[-60:], 'kind': base['kind'],
                    'low': base['low'], 'high': base['high'], 'baseline': base['value'],
                    'range_text': base['range_text']})
    strain = [[r['stamp'][:10], round(mean(r['wellbeing']['ratings'].values()), 2)] for r in records
              if r.get('wellbeing') and r['wellbeing'].get('ratings')]
    return {'metrics': out, 'strain': strain[-60:]}


def save_entry(sid, crew, data, ratings=None):
    """Same steps as the desktop app's save: supported fields, NASA comparison, follow-up rules."""
    history = visitor_records(sid, crew)
    checkin = supported_entry(data)
    result = apply_followup(checkin, assess(checkin, history))
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    record = {'checkin': checkin, 'assessment': result, 'status': result['status'], 'daily': ratings is not None,
              'stamp': stamp, 'web_visitor': True}
    if ratings is not None:
        record['wellbeing'] = wellbeing_summary(ratings)
    add_record(sid, crew, record)
    comparisons = [dict(compare(crew, key, value), label=LABELS[key][0])
                   for key, value in checkin.items() if key in LABELS and compare(crew, key, value)]
    return {'stamp': stamp, 'status': result['status'], 'title': result.get('title', ''),
            'actions': result.get('actions', []), 'rationale': result.get('rationale', []),
            'questions': ai_core.clarifications(record), 'comparisons': comparisons,
            'wellbeing': record.get('wellbeing'), 'vision_symptom': bool(result.get('vision_symptom'))}


def cleaned(sid, crew):
    rows = []
    for record in visitor_records(sid, crew):
        values = {k: v for k, v in supported_entry(record['checkin']).items() if not k.endswith('_path')}
        rows.append({'date': record['stamp'][:10], 'simulated': bool(record.get('demo_series')), 'values': values,
                     'strain': mean(record['wellbeing']['ratings'].values()) if record.get('wellbeing') else None})
    return rows


def find_record(sid, crew, stamp):
    return next((r for r in reversed(visitor_records(sid, crew)) if r['stamp'] == stamp), None)


# ------------------------------------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    server_version = 'Aboard/1.0'

    def log_message(self, fmt, *args):  # quieter logs, no visitor content
        sys.stderr.write('%s %s\n' % (self.command, self.path.split('?')[0]))

    # -- helpers
    def session(self):
        jar = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        sid = jar['aboard'].value if 'aboard' in jar else ''
        if len(sid) != 32 or not sid.isalnum():
            sid = secrets.token_hex(16)
            self._new_cookie = sid
        return sid

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.extra_headers()
        self.end_headers()
        self.wfile.write(body)

    def extra_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if getattr(self, '_new_cookie', None):
            self.send_header('Set-Cookie', f'aboard={self._new_cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800')

    def body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_BODY:
            raise ValueError('Request too large.')
        return json.loads(self.rfile.read(length) or b'{}')

    def crew(self, value):
        value = str(value or '').lower()
        if value not in CREW:
            raise ValueError('Unknown crew member.')
        return value

    def stream(self, work):
        """Stream plain text as the model writes it. HTTP/1.0: the body ends when the connection closes."""
        self.close_connection = True
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('Connection', 'close')
        self.extra_headers()
        self.end_headers()
        sent = ['']

        def write(text):
            delta = text[len(sent[0]):] if text.startswith(sent[0]) else '\n' + text
            sent[0] = text
            if delta:
                self.wfile.write(delta.encode('utf-8'))
                self.wfile.flush()
        try:
            if not LLM_SLOTS.acquire(timeout=90):
                raise ValueError('The onboard AI is busy. Please try again in a moment.')
            try:
                final = work(write)
            finally:
                LLM_SLOTS.release()
            write(final or sent[0])
        except (ai_core.OllamaUnavailable, ValueError, OSError) as error:
            write(sent[0] + ('\n' if sent[0] else '') + f'[Local AI unavailable: {error}]')

    # -- routes
    def do_GET(self):
        sid = self.session()
        path, _, query = self.path.partition('?')
        params = dict(part.split('=', 1) for part in query.split('&') if '=' in part)
        try:
            if path == '/api/today':
                return self.send_json(today(sid, self.crew(params.get('crew'))))
            if path == '/api/trends':
                return self.send_json(trends(sid, self.crew(params.get('crew'))))
            if path == '/api/health':
                try:
                    tags = ai_core.ollama_request('/api/tags', timeout=2)
                    ready = MODEL in {m.get('name') for m in tags.get('models', [])}
                except Exception:
                    ready = False
                return self.send_json({'ok': True, 'ai': ready, 'model': MODEL})
            if path == '/api/questions':
                return self.send_json({'questions': WELLBEING})
        except ValueError as error:
            return self.send_json({'error': str(error)}, 400)
        return self.static(path)

    def do_POST(self):
        sid = self.session()
        try:
            data = self.body()
            if self.path == '/api/extract':
                text = str(data.get('text', ''))[:2000]
                photo = data.get('photo_text')
                photo = str(photo)[:2000] if photo else None
                if not LLM_SLOTS.acquire(timeout=60):
                    return self.send_json(ai_core.rule_extract(text) | {'engine': 'offline rules (AI busy)'})
                try:
                    result = ai_core.extract_entry(text, None, MODEL, photo_text=photo)
                finally:
                    LLM_SLOTS.release()
                result['readings'] = {k: v for k, v in result['readings'].items() if k in LABELS}
                result['engine'] = result['engine'].replace('on this device', 'on the Aboard server')
                result['labels'] = {k: LABELS[k] for k in result['readings']}
                result['comparisons'] = {k: compare(self.crew(data.get('crew')), k, v)['summary']
                                         for k, v in result['readings'].items()}
                return self.send_json(result)
            if self.path == '/api/entry':
                crew = self.crew(data.get('crew'))
                readings = {k: str(v) for k, v in (data.get('readings') or {}).items()
                            if k in LABELS and ai_core.numbers_in(str(v))}
                notes = str(data.get('notes', ''))[:2000]
                entry = dict(readings, notes=notes, region=str(data.get('region', 'General'))[:20],
                             urgent=bool(data.get('urgent')) or urgent_request(normalize(notes)))
                return self.send_json(save_entry(sid, crew, entry))
            if self.path == '/api/questionnaire':
                crew = self.crew(data.get('crew'))
                ratings = {k: int(data['ratings'][k]) for k in WELLBEING}
                result = save_entry(sid, crew, {}, ratings)
                return self.send_json(result | {'mood': ai_core.mood_summary(visitor_records(sid, crew))})
            if self.path == '/api/explain':
                crew = self.crew(data.get('crew'))
                record = find_record(sid, crew, data.get('stamp'))
                if not record:
                    raise ValueError('Entry not found.')
                return self.stream(lambda emit: ai_core.explain_entry(record, MODEL, emit))
            if self.path == '/api/ask':
                crew = self.crew(data.get('crew'))
                question = str(data.get('question', '')).strip()[:300]
                if not question:
                    raise ValueError('Ask a question first.')
                rows = cleaned(sid, crew)
                return self.stream(lambda emit: ai_core.answer_journal(question, rows, MODEL, emit, crew))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            return self.send_json({'error': str(error)}, 400)
        self.send_json({'error': 'Not found'}, 404)

    def static(self, path):
        if path in ('', '/'):
            path = '/index.html'
        target = (STATIC / path.lstrip('/')).resolve()
        if STATIC not in target.parents or not target.is_file():
            return self.send_json({'error': 'Not found'}, 404)
        types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
                 '.js': 'text/javascript; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg',
                 '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webp': 'image/webp'}
        body = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', types.get(target.suffix, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'public, max-age=300')
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description='Aboard website')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()

    def warm():
        try:
            ai_core.warm_up(MODEL)
        except Exception:
            pass
    threading.Thread(target=warm, daemon=True).start()
    print(f'Aboard website on http://{args.host}:{args.port}  (model {MODEL})')
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
