"""Local Aboard journal and astronaut profiles."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from unicodedata import normalize
from uuid import uuid4

from assistants import image_bytes


DEMO_PROFILE = 'Simulated crew'
PRACTICE_PROFILE = 'Manual practice'
BUILTIN_PROFILES = (DEMO_PROFILE, PRACTICE_PROFILE)
ROUTINE = dict(sleep=7.4, fatigue=2, mood=4, pulse=64, systolic=116, diastolic=76, temperature=36.7)


def _profile_key(name):
    return normalize('NFC', name).casefold()


class Journal:
    def __init__(self, home):
        self.home = Path(home).absolute()
        self.home.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.home / 'journal.sqlite')
        self.db.execute('PRAGMA foreign_keys = ON')
        with self.db:
            self.db.execute('''CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY, stamp TEXT, profile TEXT, record TEXT)''')
            self.db.execute('''CREATE TABLE IF NOT EXISTS profiles (
                name TEXT PRIMARY KEY NOT NULL)''')
            self.db.executemany('INSERT OR IGNORE INTO profiles (name) VALUES (?)',
                                [(name,) for name in BUILTIN_PROFILES])
            # Register existing journal names verbatim so previously saved rows remain visible.
            self.db.execute('''INSERT OR IGNORE INTO profiles (name)
                SELECT DISTINCT profile FROM entries WHERE profile IS NOT NULL AND trim(profile) <> '' ''')
            self.db.execute('''CREATE TABLE IF NOT EXISTS conversation (
                id INTEGER PRIMARY KEY,
                profile TEXT NOT NULL REFERENCES profiles (name),
                stamp TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL)''')
            self.db.execute('''CREATE TABLE IF NOT EXISTS handoff_drafts (
                profile TEXT NOT NULL REFERENCES profiles (name),
                stamp TEXT NOT NULL,
                draft TEXT NOT NULL,
                PRIMARY KEY (profile, stamp))''')
            self.db.execute('CREATE INDEX IF NOT EXISTS entries_profile_stamp ON entries (profile, stamp, id)')
            self.db.execute('CREATE INDEX IF NOT EXISTS conversation_profile_id ON conversation (profile, id)')

    def close(self):
        self.db.close()

    def profiles(self):
        names = [row[0] for row in self.db.execute('SELECT name FROM profiles')]
        users = sorted((name for name in names if name not in BUILTIN_PROFILES), key=_profile_key)
        return [*BUILTIN_PROFILES, *users]

    def add_profile(self, name):
        display_name = normalize('NFC', name.strip())
        if not display_name:
            raise ValueError('Enter an astronaut name or call sign.')
        if not display_name.isprintable():
            raise ValueError('Use a single-line name or call sign.')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if any(_profile_key(display_name) == _profile_key(existing) for existing in self.profiles()):
                raise ValueError('An astronaut profile with that name already exists.')
            self.db.execute('INSERT INTO profiles (name) VALUES (?)', (display_name,))
        return display_name

    def save(self, profile, stamp, record):
        row = self._entry(profile, stamp, record)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO profiles (name) VALUES (?)', (profile,))
            self.db.execute('INSERT INTO entries (stamp, profile, record) VALUES (?, ?, ?)', row)

    @staticmethod
    def _entry(profile, stamp, record):
        return stamp, profile, json.dumps(dict(record, stamp=stamp), ensure_ascii=False)

    def records(self, profile):
        rows = self.db.execute('SELECT record FROM entries WHERE profile = ? ORDER BY stamp, id', (profile,))
        return [json.loads(row[0]) for row in rows]

    def save_turn(self, profile, role, text):
        stamp = datetime.now().astimezone().isoformat(timespec='seconds')
        with self.db:
            self.db.execute('INSERT INTO conversation (profile, stamp, role, message) VALUES (?, ?, ?, ?)',
                            (profile, stamp, role, text))

    def turns(self, profile):
        rows = self.db.execute('SELECT stamp, role, message FROM conversation WHERE profile = ? ORDER BY id', (profile,))
        return [{'stamp': stamp, 'role': role, 'text': message} for stamp, role, message in rows]

    def save_draft(self, profile, stamp, text):
        with self.db:
            self.db.execute('''INSERT INTO handoff_drafts (profile, stamp, draft) VALUES (?, ?, ?)
                ON CONFLICT (profile, stamp) DO UPDATE SET draft = excluded.draft''', (profile, stamp, text))

    def draft(self, profile, stamp):
        row = self.db.execute('SELECT draft FROM handoff_drafts WHERE profile = ? AND stamp = ?',
                              (profile, stamp)).fetchone()
        return row[0] if row else ''

    def attach(self, path):
        data, mime = image_bytes(path)
        folder = self.home / 'attachments'
        folder.mkdir(exist_ok=True)
        suffix = '.png' if mime == 'image/png' else '.jpg'
        target = folder / (uuid4().hex + suffix)
        try:
            with target.open('xb') as destination:
                destination.write(data)
        except FileExistsError:
            raise
        except OSError:
            target.unlink(missing_ok=True)
            raise
        return str(target)

    def seed(self):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT 1 FROM entries WHERE profile = ? LIMIT 1', (DEMO_PROFILE,)).fetchone():
                return
            today = date.today()
            rows = []
            for ago, sleep in zip(range(6, 0, -1), (7.4, 7.2, 7.6, 7.3, 5.6, 5.2)):
                day = today - timedelta(days=ago)
                checkin = dict(ROUTINE, sleep=sleep, fatigue=4 if ago <= 2 else 2)
                rows.append(self._entry(DEMO_PROFILE, day.isoformat() + 'T08:00:00',
                                        {'checkin': checkin, 'status': 'seeded'}))
            self.db.executemany('INSERT INTO entries (stamp, profile, record) VALUES (?, ?, ?)', rows)
