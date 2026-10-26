"""Data-only reader for legacy OEF NRBF records; never loads .NET objects.

Only the record/primitive forms used by OEF are accepted. References are kept
as IDs until the exam mapper selects its known properties.
"""
import struct


class NRBFError(ValueError):
    pass


class Ref:
    def __init__(self, key):
        self.key = key


class Nulls:
    def __init__(self, count):
        self.count = count


class NRBF:
    def __init__(self, data):
        self.data, self.pos = memoryview(data), 0
        self.objects, self.classes = {}, {}
        self.records = 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise NRBFError('Truncated legacy OEF record.')
        value = bytes(self.data[self.pos:self.pos + count])
        self.pos += count
        return value

    def byte(self):
        return self.take(1)[0]

    def integer(self):
        return struct.unpack('<i', self.take(4))[0]

    def count(self, maximum=100000):
        value = self.integer()
        if not 0 <= value <= maximum:
            raise NRBFError('Legacy OEF collection exceeds supported limits.')
        return value

    def string(self):
        size = 0
        for shift in range(0, 35, 7):
            value = self.byte()
            size |= (value & 127) << shift
            if not value & 128:
                return self.take(size).decode('utf-8')
        raise NRBFError('Invalid legacy OEF string length.')

    def primitive(self, kind):
        formats = {1: '?', 2: 'B', 6: 'd', 7: 'h', 8: 'i', 9: 'q',
                   10: 'b', 11: 'f', 12: 'q', 13: 'Q', 14: 'H', 15: 'I', 16: 'Q'}
        if kind in formats:
            fmt = '<' + formats[kind]
            return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]
        if kind == 3:
            lead = self.take(1)
            size = 1 if lead[0] < 128 else 2 if lead[0] < 224 else 3 if lead[0] < 240 else 4
            value = (lead + self.take(size - 1)).decode('utf-8')
            if len(value) != 1:
                raise NRBFError('Invalid legacy OEF character.')
            return value
        if kind == 18:
            return self.string()
        if kind == 17:
            return None
        raise NRBFError(f'Unsupported legacy OEF primitive {kind}.')

    def type_info(self, kind):
        if kind in (0, 7):
            return self.byte()
        if kind == 3:
            return self.string()
        if kind == 4:
            return (self.string(), self.integer())
        if kind in (1, 2, 5, 6):
            return None
        raise NRBFError('Invalid legacy OEF member type.')

    def register(self, key, value):
        if key in self.objects:
            raise NRBFError('Duplicate legacy OEF object ID.')
        self.objects[key] = value
        return value

    def values(self, count, kind, info, depth):
        if kind == 0:
            if info == 2:
                return self.take(count)
            return [self.primitive(info) for _ in range(count)]
        result = []
        while len(result) < count:
            value = self.record(depth + 1)
            if isinstance(value, Nulls):
                if not 1 <= value.count <= count - len(result):
                    raise NRBFError('Invalid legacy OEF null run.')
                result.extend([None] * value.count)
            else:
                result.append(value)
        return result

    def instance(self, key, meta, depth):
        name, names, kinds, infos = meta
        obj = self.register(key, {'__type__': name})
        for member, kind, info in zip(names, kinds, infos):
            value = self.primitive(info) if kind == 0 else self.record(depth + 1)
            if isinstance(value, Nulls):
                raise NRBFError('Unexpected legacy OEF null run in class.')
            obj[member] = value
        return obj

    def record(self, depth=0):
        self.records += 1
        if depth > 100 or self.records > 200000:
            raise NRBFError('Legacy OEF nesting or record limit exceeded.')
        kind = self.byte()
        while kind == 12:  # BinaryLibrary: metadata only, never loaded.
            self.integer()
            self.string()
            kind = self.byte()
        if kind in (4, 5):
            key, name, count = self.integer(), self.string(), self.count()
            names = [self.string() for _ in range(count)]
            kinds = [self.byte() for _ in range(count)]
            infos = [self.type_info(k) for k in kinds]
            if kind == 5:
                self.integer()
            meta = (name, names, kinds, infos)
            self.classes[key] = meta
            return self.instance(key, meta, depth)
        if kind == 1:
            key, meta_id = self.integer(), self.integer()
            if meta_id not in self.classes:
                raise NRBFError('Unknown legacy OEF class metadata.')
            return self.instance(key, self.classes[meta_id], depth)
        if kind == 6:
            key = self.integer()
            return self.register(key, self.string())
        if kind == 8:
            return self.primitive(self.byte())
        if kind == 9:
            return Ref(self.integer())
        if kind == 10:
            return None
        if kind in (13, 14):
            return Nulls(self.byte() if kind == 13 else self.count())
        if kind in (15, 16, 17):
            key, count = self.integer(), self.count(64 * 1024 * 1024 if kind == 15 else 100000)
            member_kind, info = (0, self.byte()) if kind == 15 else (2, None)
            if count > 100000 and info != 2:
                raise NRBFError('Legacy OEF primitive array exceeds supported limits.')
            return self.register(key, self.values(count, member_kind, info, depth))
        if kind == 7:
            key, array_type, rank = self.integer(), self.byte(), self.count()
            if rank != 1 or array_type not in (0, 1):
                raise NRBFError('Unsupported legacy OEF array dimensions.')
            count, member_kind = self.count(), self.byte()
            info = self.type_info(member_kind)
            return self.register(key, self.values(count, member_kind, info, depth))
        raise NRBFError(f'Unsupported legacy OEF record {kind}.')

    def resolve(self, value):
        seen = set()
        while isinstance(value, Ref):
            if value.key in seen or value.key not in self.objects:
                raise NRBFError('Invalid legacy OEF object reference.')
            seen.add(value.key)
            value = self.objects[value.key]
        return value

    def read(self):
        if self.byte() != 0:
            raise NRBFError('Invalid legacy OEF stream header.')
        root = self.integer()
        self.integer()
        if (self.integer(), self.integer()) != (1, 0):
            raise NRBFError('Unsupported legacy OEF stream version.')
        while self.pos < len(self.data) and self.data[self.pos] != 11:
            self.record()
        if self.take(1) != b'\x0b' or self.pos != len(self.data):
            raise NRBFError('Invalid legacy OEF stream ending.')
        return self.resolve(Ref(root))


def decode_legacy(data):
    reader = NRBF(data)
    root = reader.read()

    def member(obj, key, default=None):
        obj = reader.resolve(obj)
        if not isinstance(obj, dict):
            raise NRBFError('Expected legacy OEF class data.')
        return reader.resolve(obj.get(f'<{key}>k__BackingField', default))

    def items(value):
        value = reader.resolve(value)
        if value is None:
            return []
        if isinstance(value, list):
            return [reader.resolve(v) for v in value]
        if not isinstance(value, dict):
            raise NRBFError('Invalid legacy OEF list.')
        values = reader.resolve(value.get('_items'))
        count = value.get('_size')
        if not isinstance(values, list) or type(count) is not int or not 0 <= count <= len(values):
            raise NRBFError('Invalid legacy OEF list extent.')
        return [reader.resolve(v) for v in values[:count]]

    if not isinstance(root, dict) or root.get('__type__', '').split('.')[-1] != 'Exam':
        raise NRBFError('Legacy OEF root is not an Exam.')
    props = member(root, 'Properties')
    result = {'Properties': {k: member(props, k, default) for k, default in
                            [('Title', ''), ('Code', ''), ('Version', 0), ('Passmark', 0),
                             ('TimeLimit', 0), ('Instructions', ''), ('HideAnswers', False)]}, 'Sections': []}
    for section in items(member(root, 'Sections')):
        mapped = {'Title': member(section, 'Title', ''), 'Questions': []}
        for question in items(member(section, 'Questions')):
            q = {k: member(question, k, default) for k, default in
                 [('No', 0), ('Text', ''), ('Answer', ''), ('IsMultipleChoice', False),
                  ('Answers', []), ('Explanation', '')]}
            q['Options'] = [{'Alphabet': member(o, 'Alphabet', ''), 'Text': member(o, 'Text', '')}
                            for o in items(member(question, 'Options'))]
            image = member(question, 'Image')
            if image is not None:
                if not isinstance(image, dict):
                    raise NRBFError('Unsupported legacy OEF image data.')
                image = reader.resolve(image.get('Data'))
                if not isinstance(image, bytes):
                    raise NRBFError('Unsupported legacy OEF image data; export using Open Exam Suite.')
            q['Image'] = image
            mapped['Questions'].append(q)
        result['Sections'].append(mapped)
    return result
