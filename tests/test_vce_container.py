import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from vce_container import read_container
from vce_reader import VCEError
from richview import parse_nested_documents

POOL = bytes(range(64))


def length(value):
    raw = struct.pack('<I', value)
    return b'\x4d' + bytes([raw[0], raw[1] ^ 1, raw[2] ^ 2, raw[3] ^ 7])


def blob(raw, marker=2):
    pad = PKCS7(128).padder()
    padded = pad.update(raw) + pad.finalize()
    enc = Cipher(algorithms.AES(POOL[:32]), modes.CBC(POOL[32:48])).encryptor()
    encrypted = enc.update(padded) + enc.finalize()
    return length(len(encrypted) + 5) + bytes([marker]) + struct.pack('<I', 0) + encrypted


def document(text):
    data = b'-8 1 3 1\r\n0 1 0 8 0 0\r\n' + text.encode('utf-16-le')
    return length(len(data)) + data


def question(index=0, protected=False):
    marker = 128 if protected else 2
    body = blob(struct.pack('<II', index, 64) + POOL, marker)
    body += b'\x00' + struct.pack('<iii', -1, 5, 0)
    body += blob(document('An original question') + document('First option') + document('Second option') + document(''), marker)
    body += blob(b'A', marker) + struct.pack('<I', 2) + bytes([1, 0, 0]) + blob(b'Original title', marker)
    return length(len(body)) + body


def field(value):
    raw = value.encode('utf-8')
    return length(len(raw)) + raw


def ints(*values):
    return struct.pack('<' + 'i' * len(values), *values)


def reorder_question(index=0, items=('First step', 'Second step', 'Third step'), order=(2, 0, 1)):
    # Native type 5 (reorder): items in prompt_data, correct index order in
    # answer_data, two documents (prompt, explanation) in tree_data.
    marker = 2
    primary = ints(len(items)) + b''.join(field(s) for s in items)
    answer = ints(len(order)) + b''.join(ints(i) for i in order)
    body = blob(struct.pack('<II', index, 64) + POOL, marker)
    body += bytes([5]) + struct.pack('<iii', -1, 5, 0)
    body += blob(primary, marker) + blob(answer, marker)
    body += bytes([0]) + field('category') + field('value')
    body += blob(document('Put the steps in order.') + document('The correct order is shown.'), marker)
    body += bytes([0, 0])
    return length(len(body)) + body


def make_png(width=8, height=8):
    """A minimal valid 8-bit RGBA PNG that passes richview._png_valid and Tk."""
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    raw = b''.join(b'\x00' + b'\x20\x40\x60\xff' * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def hotspot_question(index=0):
    # Native type 9 (hotspot): rectangles in prompt_data, per-area correct flags
    # in answer_data, documents in image_data, the image in image_aux_data.
    marker = 2
    primary = ints(2) + ints(10, 10, 50, 50) + ints(60, 60, 90, 90)
    answer = ints(2) + bytes([1, 0])  # first area correct, second not
    body = blob(struct.pack('<II', index, 64) + POOL, marker)
    body += bytes([9]) + struct.pack('<iii', -1, 5, 0)
    body += blob(primary, marker) + blob(answer, marker)
    body += blob(document('Click the correct area.') + document('The top-left area is correct.'), marker)
    body += bytes([0, 0]) + blob(make_png(), marker)
    return length(len(body)) + body


def point_question(index=0, rect=(20, 30, 80, 90)):
    # Native type 3 (point-and-shoot): primary geometry ignored, one answer rect.
    marker = 2
    body = blob(struct.pack('<II', index, 64) + POOL, marker)
    body += bytes([3]) + struct.pack('<iii', -1, 5, 0)
    body += blob(b'geometry-ignored', marker) + blob(ints(*rect), marker)
    body += blob(document('Point to the target.') + document('Target explained.'), marker)
    body += bytes([0, 0]) + blob(make_png(), marker)
    return length(len(body)) + body


def connect_question(index=0):
    # Native type 7 (connect): connectors/boxes in prompt_data, relationships in
    # answer_data, documents in connection_data[0], coordinates in [1].
    marker = 2
    primary = ints(1) + field('links to') + bytes([1]) + ints(2) + field('Alpha') + field('Beta')
    answer = ints(1) + ints(0, 1, 0) + bytes([1])  # one relationship, forward
    body = blob(struct.pack('<II', index, 64) + POOL, marker)
    body += bytes([7]) + struct.pack('<iii', -1, 5, 0)
    body += blob(primary, marker) + blob(answer, marker)
    body += blob(document('Connect the related items.') + document('Alpha links to Beta.'), marker)
    body += blob(ints(0, 0, 10, 0, 5, 5), marker)  # two box positions + one relationship position
    body += blob(b'Connect title', marker) + struct.pack('<II', 0, 0)
    return length(len(body)) + body


def fill_question(index=0, answer='Paris', blank_count=1, case_sensitive=False):
    # Native type 8 (fill-in-the-blank): two RichView documents (prompt,
    # explanation) in prompt_data, one length-prefixed accepted string per blank
    # in answer_data, then the int blank count and three normalization flags.
    marker = 2
    body = blob(struct.pack('<II', index, 64) + POOL, marker)
    body += bytes([8]) + struct.pack('<iii', -1, 5, 0)
    body += blob(document('Name the capital of France.') + document('The capital is Paris.'), marker)
    body += blob(b''.join(field(answer) for _ in range(blank_count)), marker)
    body += struct.pack('<I', blank_count) + bytes([1 if case_sensitive else 0, 1, 1])
    return length(len(body)) + body


def header(format_value=62):
    data = b'\x85\xa8\x06' + bytes([format_value-60]) + struct.pack('<I', 4)
    data += length(len(POOL)) + POOL + length(0)
    data += b'\x00' + blob(b'OWN-001') + blob(b'Original native fixture')
    data += struct.pack('<II', 700, 30) + blob(b'1') + struct.pack('<QQ', 1000, 2000)
    data += blob(b'Original styles') + blob(b'-8 1 3 1\r\n')
    data += struct.pack('<I', 0) + blob(struct.pack('<I', 0))
    return data


def plain_list_fixture(*questions, format_value=62):
    """One top-level plain list holding the given question records in order."""
    reference = (b'\x00' + blob(b'Original section')
                 + struct.pack('<I', len(questions)) + b''.join(questions))
    return (header(format_value) + struct.pack('<I', 1)
            + (length(len(reference)) if format_value == 63 else b'') + reference)


def fixture(plain=False, protected=False, format_value=62, fill=False):
    if fill:
        # A top-level plain list mixing a choice question and a type-8 blank.
        return plain_list_fixture(question(), fill_question(1))
    if plain:
        return plain_list_fixture(question(), question(1, protected=protected),
                                  format_value=format_value)
    data = header(format_value)
    data += struct.pack('<I', 1) + b'\x01' + blob(b'Original section') + struct.pack('<I', 2)
    data += b'\x00' + struct.pack('<II', 20, 1) + question()
    data += b'\x01' + struct.pack('<I', 20) + blob(b'Original case study')
    data += struct.pack('<I', 0) + blob(b'') + blob(b'-8 1 3 1\r\n')
    data += struct.pack('<II', 0, 1) + question(1)
    return data


class ContainerTests(unittest.TestCase):
    def parse(self, raw, pool=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'original.vce'
            path.write_bytes(raw)
            return read_container(path, content_pool=pool)

    def test_original_groups_and_case_study(self):
        result = self.parse(fixture())
        self.assertEqual(len(result['records']), 2)
        self.assertEqual(result['decoded_count'], 2)
        self.assertEqual(result['trailing_bytes'], 0)
        self.assertEqual(result['groups'][0]['count'], 2)
        self.assertEqual(result['groups'][0]['children'][1]['kind'], 1)
        docs = parse_nested_documents(result['records'][0]['prompt_data'])
        self.assertEqual(docs[1].text, 'First option')

    def test_top_level_plain_list_without_nested_reference_tag(self):
        result = self.parse(fixture(plain=True))
        self.assertEqual(result['decoded_count'], 2)
        self.assertEqual(len(result['records']), 2)
        self.assertEqual(result['trailing_bytes'], 0)
        self.assertIsNone(result['groups'][0]['children'][0]['tag'])
        self.assertEqual(result['records'][1]['id'], 1)

    def test_format63_reference_extent(self):
        result=self.parse(fixture(plain=True,format_value=63))
        self.assertEqual(result['metadata']['format'],63)
        self.assertEqual(result['decoded_count'],2)
        self.assertEqual(result['trailing_bytes'],0)
        self.assertEqual(result['groups'][0]['envelope_end'],result['parsed_end'])

    def test_format63_reference_extent_rejects_truncation(self):
        with self.assertRaises(VCEError):
            self.parse(fixture(plain=True,format_value=63)[:-1])

    def test_truncated_record_rejected(self):
        with self.assertRaises(VCEError):
            self.parse(fixture()[:-3])

    def test_protected_pool_does_not_replace_initial_pool(self):
        result = self.parse(fixture(), bytes(64))
        self.assertEqual(result['decoded_count'], 2)

    def test_mixed_preview_and_protected_records(self):
        raw = fixture(plain=True, protected=True)
        preview = self.parse(raw)
        self.assertEqual(preview['decoded_count'], 1)
        self.assertIn('protected content-key pool', preview['records'][1]['error'])
        complete = self.parse(raw, POOL)
        self.assertEqual(complete['decoded_count'], 2)
        wrong = self.parse(raw, bytes(64))
        self.assertEqual(wrong['decoded_count'], 1)
        self.assertTrue(wrong['records'][0]['decoded'])
