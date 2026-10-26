"""Bounded ProfExam PV12/PRFEXV12 reader. Encrypted fields stay unavailable.

No activation or key acquisition. Format evidence: docs/VCEX-SUPPORT.md.
"""
import base64
import io
import json
import re
import zipfile
import zlib
from html.parser import HTMLParser

MAX_SIZE = 128 * 1024 * 1024


class VCEXError(ValueError):
    pass


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 1033

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise VCEXError(f'Truncated VCEX data at byte {self.pos}.')
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def block(self):
        digits = self.take(1)[0]
        if not 1 <= digits <= 9:
            raise VCEXError('Invalid VCEX length prefix.')
        raw = self.take(digits)
        if not raw.isdigit():
            raise VCEXError('Invalid VCEX block length.')
        return self.take(int(raw))

    def count(self):
        value = self.block()
        if not value.isdigit() or int(value) > 10000:
            raise VCEXError('Invalid VCEX item count.')
        return int(value)

    def json(self):
        return decode_json(self.block())


def decode_json(raw):
    try:
        return json.loads(base64.b64decode(raw, validate=True))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise VCEXError('Invalid VCEX base64 JSON record.') from error


def read_vcex(path):
    with open(path, 'rb') as stream:
        raw = stream.read(MAX_SIZE + 1)
    if len(raw) > MAX_SIZE:
        raise VCEXError('VCEX file exceeds the 128 MiB limit.')
    if raw[:4] != b'PV12':
        raise VCEXError('Supported VCEX container version: PV12.')
    try:
        with zipfile.ZipFile(io.BytesIO(b'PK\x03\x04' + raw[4:])) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].is_dir():
                raise VCEXError('Expected one VCEX payload.')
            info = members[0]
            if info.flag_bits & 1:
                raise VCEXError('Password-encrypted VCEX ZIP containers are unsupported.')
            if info.file_size > MAX_SIZE:
                raise VCEXError('VCEX payload exceeds the 128 MiB limit.')
            with archive.open(info) as stream:
                payload = stream.read(MAX_SIZE + 1)
            if len(payload) > MAX_SIZE:
                raise VCEXError('VCEX payload exceeds the 128 MiB limit.')
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as error:
        raise VCEXError('Invalid or unsupported VCEX archive.') from error
    if payload[:8] != b'PRFEXV12' or len(payload) < 1033:
        raise VCEXError('Unsupported or truncated VCEX payload; expected PRFEXV12.')
    reader = Reader(payload)
    reader.block()  # EP flag
    password = reader.block()
    if not password.startswith(b'SP'):
        raise VCEXError('Invalid VCEX password header.')
    reader.block()  # public content-key identifier
    reader.block()  # auxiliary key data
    count, image_count = reader.count(), reader.count()
    metadata, exams, sections, testlets, qsets = [reader.json() for _ in range(5)]
    if not isinstance(metadata, dict) or not isinstance(metadata.get('d1'), str):
        raise VCEXError('Invalid VCEX exam metadata.')
    if not all(isinstance(x, list) for x in (exams, sections, testlets, qsets)):
        raise VCEXError('Invalid VCEX exam structure.')
    images = {}
    for _ in range(image_count):
        try:
            key = reader.block().decode('ascii')
        except UnicodeError as error:
            raise VCEXError('Invalid VCEX image identifier.') from error
        if key in images:
            raise VCEXError('Duplicate VCEX image identifier.')
        images[key] = reader.block()
    records, encrypted = [], 0
    for index in range(count):
        block = reader.block()
        protected = block.startswith(b'*')
        record = decode_json(block[1:] if protected else block)
        if not isinstance(record, dict):
            raise VCEXError('Invalid VCEX question record.')
        encrypted += protected
        records.append(dict(data=record, encrypted=protected, index=index))
    if reader.pos != len(payload):
        raise VCEXError('Unexpected trailing VCEX data.')
    return dict(format='PRFEXV12', title=metadata['d1'], exam_number=metadata.get('d2', ''),
                time_limit_minutes=metadata.get('d4', 30), passing_score_raw=metadata.get('d3'),
                source_count=count, encrypted_count=encrypted, readable_count=count-encrypted,
                image_count=image_count, password_required=bool(password[2:].strip()),
                records=records, images=images, sections=sections, testlets=testlets,
                exams=exams, qsets=qsets)


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden, self.unsupported = [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ('head', 'script', 'style'):
            self.hidden += 1
        elif not self.hidden and tag in ('br', 'p', 'div', 'li', 'tr'):
            self.parts.append('\n')
        elif tag in ('img', 'table', 'svg', 'math', 'object', 'iframe'):
            self.unsupported = True

    def handle_endtag(self, tag):
        if tag in ('head', 'script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ('p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_html(value):
    if not isinstance(value, str):
        raise VCEXError('Invalid VCEX HTML field.')
    parser = TextHTML()
    parser.feed(value)
    if parser.unsupported:
        raise VCEXError('Question requires unsupported HTML layout or resources.')
    return re.sub(r'\n\s*\n+', '\n\n', ''.join(parser.parts)).strip()


IMAGE = re.compile(r'\[@_img_([\w-]+)_@\]')


def practice_exam(data):
    if data['password_required']:
        raise VCEXError('This VCEX exam requires a password. Password-protected exams are unsupported.')
    questions = []
    sections = {s['d0']: s['d1'] for s in data['sections'] if isinstance(s, dict) and 'd0' in s and 'd1' in s}
    for entry in data['records']:
        r = entry['data']
        if entry['encrypted'] or r.get('x5') not in (1, 2):
            continue
        if r.get('x7') not in (None, '', '00000000-0000-0000-0000-000000000000') or r.get('x10'):
            continue  # Case studies and exhibits require a separate renderer.
        try:
            prompt, explanation = plain_html(r['x2']), plain_html(r['x3'])
            options_data = json.loads(r['x4'])['x0']
            if not isinstance(options_data, list) or len(options_data) < 2:
                continue
            if any(type(o.get('x1')) is not bool for o in options_data):
                continue
            options = [plain_html(o['x3']) for o in options_data]
            answer = [i for i, o in enumerate(options_data) if o['x1']]
            if not prompt or not all(options) or not answer or (r['x5'] == 1 and len(answer) != 1):
                continue
            if any(IMAGE.search(s) for s in options + [explanation]):
                continue
            image_ids = IMAGE.findall(prompt)
            if any(key not in data['images'] or not data['images'][key].startswith(b'\x89PNG\r\n\x1a\n') for key in image_ids):
                continue
            images = [data['images'][key] for key in image_ids]
            number = iter(range(1, len(images) + 1))
            prompt = IMAGE.sub(lambda _: f'[Image {next(number)}]', prompt)
            questions.append(dict(type='choice', prompt=prompt, options=options, answer=answer,
                                  explanation=explanation, section=sections.get(r.get('x9'), 'General'),
                                  source_number=r.get('x1', str(entry['index'] + 1)), images=images))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    if not questions:
        raise VCEXError(f'No supported readable questions. {data["encrypted_count"]} of {data["source_count"]} records are encrypted.')
    total = data['source_count']
    scope = (f'VCEX practice: {len(questions)} of {total} source questions. '
             f'{data["encrypted_count"]} encrypted; {data["readable_count"] - len(questions)} readable questions unsupported. '
             'Scoring applies only to this subset.')
    return dict(title=data['title'] + ' — VCEX practice', exam_number=data['exam_number'],
                questions=questions, passing_score=70, time_limit_minutes=30,
                practice_only=True, source_count=total, scope_notice=scope)
