"""Open Exam Suite OEF: protobuf and data-only legacy NRBF import.

Schema reference: bolorundurowb/Open-Exam-Suite, Core/Exam.cs at
453c3cf31d611cf6ad9601ab8e4f1179f7569a8d. No upstream code is executed.
"""
import io
import math
import struct

MAX_SIZE = 64 * 1024 * 1024


class OEFError(ValueError):
    pass


# field number -> (name, representation); repeated fields end in [].
OPTION = {1: ('Alphabet', 'char'), 2: ('Text', 'string')}
QUESTION = {1: ('No', 'int'), 2: ('Text', 'string'), 3: ('Image', 'bytes'),
            4: ('Answer', 'char'), 5: ('IsMultipleChoice', 'bool'),
            6: ('Answers', 'char[]'), 7: ('Options', OPTION), 8: ('Explanation', 'string')}
SECTION = {1: ('Title', 'string'), 2: ('Questions', QUESTION)}
PROPERTIES = {1: ('Title', 'string'), 2: ('Code', 'string'), 3: ('Version', 'int'),
              4: ('Passmark', 'double'), 5: ('TimeLimit', 'int'),
              6: ('Instructions', 'string'), 7: ('HideAnswers', 'bool')}
EXAM = {1: ('Properties', PROPERTIES), 2: ('Sections', SECTION)}
REPEATED = {'Sections', 'Questions', 'Options'}


class Wire:
    def __init__(self, raw):
        self.raw, self.pos = memoryview(raw), 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.raw):
            raise OEFError('Truncated OEF protobuf field.')
        value = bytes(self.raw[self.pos:self.pos + count])
        self.pos += count
        return value

    def varint(self):
        result = 0
        for shift in range(0, 70, 7):
            value = self.take(1)[0]
            if shift == 63 and value > 1:
                break
            result |= (value & 127) << shift
            if not value & 128:
                return result
        raise OEFError('Invalid OEF protobuf integer.')

    def fields(self, schema, depth=0):
        if depth > 4:
            raise OEFError('Invalid OEF protobuf nesting.')
        result = {}
        fields = 0
        while self.pos < len(self.raw):
            fields += 1
            if fields > 100000:
                raise OEFError('Too many OEF protobuf fields.')
            tag = self.varint()
            number, wire = tag >> 3, tag & 7
            if number == 0 or number > 0x1fffffff:
                raise OEFError('Invalid OEF protobuf tag.')
            if wire == 0:
                value = self.varint()
            elif wire == 1:
                value = self.take(8)
            elif wire == 2:
                value = self.take(self.varint())
            elif wire == 5:
                value = self.take(4)
            else:
                raise OEFError('Unsupported OEF protobuf wire type.')
            if number not in schema:
                continue
            name, kind = schema[number]
            if isinstance(kind, dict):
                if wire != 2:
                    raise OEFError(f'Invalid OEF {name} message.')
                value = Wire(value).fields(kind, depth + 1)
            elif kind in ('string', 'bytes'):
                if wire != 2:
                    raise OEFError(f'Invalid OEF {name} field.')
                if kind == 'string':
                    value = value.decode('utf-8')
            elif kind == 'double':
                if wire != 1:
                    raise OEFError('Invalid OEF pass mark encoding.')
                value = struct.unpack('<d', value)[0]
            elif kind == 'char[]':
                if wire == 2:
                    packed, values = Wire(value), []
                    while packed.pos < len(packed.raw):
                        values.append(char(packed.varint()))
                    value = values
                elif wire == 0:
                    value = [char(value)]
                else:
                    raise OEFError('Invalid OEF multiple-answer encoding.')
            else:
                if wire != 0:
                    raise OEFError(f'Invalid OEF {name} integer.')
                if kind == 'char':
                    value = char(value)
                elif kind == 'bool':
                    if value not in (0, 1):
                        raise OEFError('Invalid OEF boolean.')
                    value = bool(value)
                elif value > 0x7fffffff:
                    raise OEFError('OEF integer is out of range.')
            if name in REPEATED:
                result.setdefault(name, []).append(value)
            elif kind == 'char[]':
                result.setdefault(name, []).extend(value)
            else:
                result[name] = value
        return result


def char(value):
    if not 0 <= value <= 0xffff or 0xd800 <= value <= 0xdfff:
        raise OEFError('Invalid OEF answer character.')
    return chr(value)


def normalize_image(raw):
    if not raw:
        return []
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 20000000:
                raise OEFError('OEF question image exceeds 20 million pixels.')
            if image.format not in ('PNG', 'JPEG', 'BMP', 'GIF', 'TIFF'):
                raise OEFError('Unsupported OEF image format.')
            image.load()
            out = io.BytesIO()
            image.convert('RGBA').save(out, format='PNG')
            return [out.getvalue()]
    except ImportError as error:
        raise OEFError('OEF images require Pillow. Install requirements.txt.') from error
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise OEFError(f'Unable to decode OEF question image: {error}') from error


def read_oef(path):
    with open(path, 'rb') as stream:
        raw = stream.read(MAX_SIZE + 1)
    return decode_oef(raw)


def decode_oef(raw):
    if not raw or len(raw) > MAX_SIZE:
        raise OEFError('OEF file is empty or exceeds the 64 MiB limit.')
    legacy = raw[:1] == b'\x00'
    try:
        if legacy:
            from oef_nrbf import decode_legacy
            data = decode_legacy(raw)
        else:
            data = Wire(raw).fields(EXAM)
        return adapt_exam(data, legacy)
    except (UnicodeError, KeyError, TypeError, RecursionError, struct.error) as error:
        raise OEFError('Invalid or unsupported OEF exam data.') from error


def adapt_exam(data, legacy=False):
    props = data.get('Properties', {})
    title = props.get('Title', '')
    if not isinstance(title, str) or not title.strip():
        raise OEFError('OEF exam must have a title.')
    passmark = props.get('Passmark', 0)
    minutes = props.get('TimeLimit', 0)
    if type(passmark) not in (int, float) or not math.isfinite(passmark) or not 0 <= passmark <= 1000:
        raise OEFError('OEF pass mark must be between 0 and 1000.')
    if type(minutes) is not int or not 0 <= minutes <= 1440:
        raise OEFError('Invalid OEF time limit.')
    questions = []
    for section in data.get('Sections', []):
        section_title = section.get('Title', '') or 'General'
        if not isinstance(section_title, str):
            raise OEFError('Invalid OEF section title.')
        for q in section.get('Questions', []):
            prompt = q.get('Text', '')
            options = q.get('Options', [])
            if not isinstance(prompt, str) or not prompt.strip() or len(options) < 2:
                raise OEFError('Every OEF question needs a prompt and at least two options.')
            labels = [o.get('Alphabet', '\0') for o in options]
            if len(set(labels)) != len(labels) or any(not isinstance(label, str) or len(label) != 1 or label == '\0' for label in labels):
                raise OEFError('OEF option labels must be distinct and nonempty.')
            answer_labels = list(q.get('Answers', [])) if q.get('IsMultipleChoice', False) else [q.get('Answer', '\0')]
            if not answer_labels or len(set(answer_labels)) != len(answer_labels) or any(a not in labels for a in answer_labels):
                raise OEFError('OEF question has missing or invalid correct answers.')
            texts = [o.get('Text', '') for o in options]
            if not all(isinstance(t, str) and t.strip() for t in texts):
                raise OEFError('OEF options must contain text.')
            questions.append(dict(type='choice', prompt=prompt, options=texts,
                                  answer=[labels.index(a) for a in answer_labels],
                                  explanation=q.get('Explanation') or '', section=section_title,
                                  source_number=str(q.get('No', len(questions) + 1)),
                                  images=normalize_image(q.get('Image'))))
            if len(questions) > 10000:
                raise OEFError('OEF exam exceeds 10,000 questions.')
    if not questions:
        raise OEFError('OEF exam contains no questions.')
    return dict(title=title, exam_number=props.get('Code', ''), questions=questions,
                passing_score=passmark / 10, oef_passmark=passmark,
                time_limit_minutes=minutes or 30, source_time_limit_minutes=minutes,
                practice_only=minutes == 0, hide_answers=bool(props.get('HideAnswers', False)),
                instructions=props.get('Instructions', ''), source_format='OEF legacy NRBF' if legacy else 'OEF protobuf',
                source_count=len(questions))
