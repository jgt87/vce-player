"""JSON, VCEX and OEF import, scoring and local session storage."""
import hashlib
import json
import math
import sqlite3
from pathlib import Path


def load_exam(path):
    raw = Path(path).read_bytes()
    if raw[:2] == b'\x85\xa8':
        raise ValueError('VCE container detected. Question framing is not established in the handover. Use an original JSON exam.')
    if Path(path).suffix.lower() == '.oef':
        from oef_reader import decode_oef
        exam = decode_oef(raw)
        digest = hashlib.sha256(raw + b':oef-v1').hexdigest()
    elif raw[:4] == b'PV12' or Path(path).suffix.lower() == '.vcex':
        from vcex_reader import read_vcex, practice_exam
        exam = practice_exam(read_vcex(path))
        digest = hashlib.sha256(raw + b':vcex-practice-v1').hexdigest()
    else:
        exam = json.loads(raw)
        digest = hashlib.sha256(raw).hexdigest()
    if not isinstance(exam, dict) or not isinstance(exam.get('title'), str):
        raise ValueError('Exam must have a title.')
    questions = exam.get('questions')
    if not isinstance(questions, list) or not questions:
        raise ValueError('Exam must contain questions.')
    for q in questions:
        if not isinstance(q, dict) or not isinstance(q.get('prompt'), str):
            raise ValueError('Every question needs a prompt.')
        kind = q.get('type')
        if kind == 'choice':
            options, answer = q.get('options'), q.get('answer')
            if not isinstance(options, list) or len(options) < 2 or not all(isinstance(x, str) for x in options):
                raise ValueError('Choice questions need at least two text options.')
            if not isinstance(answer, list) or not answer or len(set(answer)) != len(answer) or any(type(x) is not int or x < 0 or x >= len(options) for x in answer):
                raise ValueError('Choice answers must be distinct valid option indexes.')
        elif kind == 'text':
            if not isinstance(q.get('answer'), list) or not q['answer'] or not all(isinstance(x, str) and x.strip() for x in q['answer']):
                raise ValueError('Text questions need accepted answer strings.')
        elif kind == 'order':
            items, answer = q.get('items'), q.get('answer')
            if not isinstance(items, list) or len(items) < 2 or not all(isinstance(x, str) and x.strip() for x in items):
                raise ValueError('Order questions need at least two text items.')
            if not isinstance(answer, list) or any(type(x) is not int for x in answer) or sorted(answer) != list(range(len(items))):
                raise ValueError('Order answers must be a permutation of the item indexes.')
        elif kind == 'connect':
            boxes, connectors, answer = q.get('boxes'), q.get('connectors'), q.get('answer')
            if not isinstance(boxes, list) or len(boxes) < 2 or not all(isinstance(x, str) and x.strip() for x in boxes):
                raise ValueError('Connect questions need at least two text boxes.')
            if not isinstance(connectors, list) or not connectors or not all(isinstance(x, str) and x.strip() for x in connectors):
                raise ValueError('Connect questions need connector labels.')
            if not isinstance(answer, list) or not answer:
                raise ValueError('Connect questions need at least one relationship.')
            for link in answer:
                if (not isinstance(link, list) or len(link) != 3 or any(type(x) is not int for x in link)
                        or not 0 <= link[0] < len(boxes) or not 0 <= link[1] < len(boxes) or not 0 <= link[2] < len(connectors)):
                    raise ValueError('Connect relationships must be valid [source, target, connector] indexes.')
        else:
            raise ValueError('Supported question types: choice, text, order, connect.')
    for key, default, low, high in [('passing_score', 70, 0, 100), ('time_limit_minutes', 30, 1, 1440)]:
        value = exam.get(key, default)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'Invalid {key}.')
        exam[key] = value
    return exam, digest


def correct(question, response):
    kind = question['type']
    if kind == 'choice':
        return sorted(response or []) == sorted(question['answer'])
    if kind == 'order':
        return list(response or []) == question['answer']
    if kind == 'connect':
        return {tuple(link) for link in (response or [])} == {tuple(link) for link in question['answer']}
    if kind == 'hotspot':
        return bool(question['answer']) and set(response or []) == set(question['answer'])
    if kind == 'point':
        if not response or len(response) != 2:
            return False
        x, y = response
        left, top, right, bottom = question['rect']
        return min(left, right) <= x <= max(left, right) and min(top, bottom) <= y <= max(top, bottom)
    return str(response or '').strip().casefold() in [x.strip().casefold() for x in question['answer']]


def score(exam, answers):
    right = sum(correct(q, answers.get(str(i))) for i, q in enumerate(exam['questions']))
    incomplete = sum(not answers.get(str(i)) for i in range(len(exam['questions'])))
    percent = right * 100 / len(exam['questions'])
    sections = {}
    for i, q in enumerate(exam['questions']):
        section = sections.setdefault(q.get('section', 'General'), dict(correct=0, total=0))
        section['total'] += 1
        section['correct'] += int(correct(q, answers.get(str(i))))
    result = dict(correct=right, total=len(exam['questions']), incomplete=incomplete,
                  percent=percent, passed=percent >= exam['passing_score'], sections=sections)
    if 'oef_passmark' in exam:
        result['normalized_score'] = right * 1000 // len(exam['questions'])
        result['passed'] = result['normalized_score'] >= exam['oef_passmark']
    return result


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS library (digest TEXT PRIMARY KEY, path TEXT, title TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, state TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, title TEXT, digest TEXT, result TEXT)')
        self.db.commit()

    def add(self, digest, path, title):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO library VALUES (?,?,?)', (digest, str(Path(path).resolve()), title))

    def save(self, digest, state):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)', (digest, json.dumps(state)))

    def resume(self, digest):
        row = self.db.execute('SELECT state FROM sessions WHERE digest=?', (digest,)).fetchone()
        return json.loads(row[0]) if row else None

    def finish(self, digest, title, result):
        with self.db:
            self.db.execute('INSERT INTO history(title,digest,result) VALUES (?,?,?)', (title, digest, json.dumps(result)))
            self.db.execute('DELETE FROM sessions WHERE digest=?', (digest,))
