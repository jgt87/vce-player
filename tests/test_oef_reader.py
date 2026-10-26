"""Interoperability fixtures authored from the published OEF protobuf schema."""
import io
import struct
import tempfile
import unittest
from pathlib import Path

from exam_engine import load_exam, score
from oef_reader import decode_oef, OEFError


def varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    return bytes(out) + bytes([value])


def integer(number, value):
    return varint(number << 3) + varint(value)


def blob(number, value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return varint((number << 3) | 2) + varint(len(value)) + value


def fixture(multiple=False, packed=False, image=b'', hide=False, minutes=20, passmark=700):
    props = blob(1, 'Original OEF example') + blob(2, 'OEF-1')
    props += integer(3, 3) + b'\x21' + struct.pack('<d', passmark)
    props += integer(5, minutes) + blob(6, 'Read each question carefully.') + integer(7, int(hide))
    # Labels deliberately differ from list order and start at C.
    opts = [integer(1, ord(label)) + blob(2, text) for label, text in [('C', 'First'), ('A', 'Second'), ('B', 'Third')]]
    question = integer(1, 1) + blob(2, 'An original question?') + blob(3, image)
    question += integer(4, ord('A')) + integer(5, int(multiple))
    if multiple:
        question += blob(6, b'CB') if packed else integer(6, ord('C')) + integer(6, ord('B'))
    question += b''.join(blob(7, o) for o in opts) + blob(8, 'An original explanation.')
    return blob(1, props) + blob(2, blob(1, 'Original section') + blob(2, question))


class OEFTests(unittest.TestCase):
    def test_single_choice_labels_metadata_and_score(self):
        exam = decode_oef(fixture())
        self.assertEqual(exam['passing_score'], 70)
        self.assertEqual(exam['time_limit_minutes'], 20)
        self.assertEqual(exam['questions'][0]['answer'], [1])
        self.assertEqual(exam['questions'][0]['section'], 'Original section')
        self.assertEqual(exam['questions'][0]['explanation'], 'An original explanation.')
        self.assertEqual(score(exam, {'0': [1]})['normalized_score'], 1000)
        self.assertFalse(score(exam, {'0': [0]})['passed'])

    def test_packed_and_unpacked_multiple_answers(self):
        for packed in (False, True):
            exam = decode_oef(fixture(multiple=True, packed=packed))
            self.assertEqual(exam['questions'][0]['answer'], [0, 2])
            self.assertEqual(score(exam, {'0': [2, 0]})['correct'], 1)
            self.assertEqual(score(exam, {'0': [0]})['correct'], 0)

    def test_integer_normalized_score_matches_upstream(self):
        exam = decode_oef(fixture(passmark=333.2))
        exam['questions'] *= 3
        result = score(exam, {'0': [1]})
        self.assertEqual(result['normalized_score'], 333)
        self.assertFalse(result['passed'])

    def test_untimed_and_hide_answers(self):
        exam = decode_oef(fixture(minutes=0, hide=True))
        self.assertTrue(exam['practice_only'])
        self.assertTrue(exam['hide_answers'])
        self.assertEqual(exam['source_time_limit_minutes'], 0)

    def test_file_import_and_stable_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'exam.OEF'
            path.write_bytes(fixture())
            exam, digest = load_exam(path)
            self.assertEqual(exam['exam_number'], 'OEF-1')
            self.assertEqual(load_exam(path)[1], digest)
            path.write_bytes(fixture(multiple=True))
            self.assertNotEqual(load_exam(path)[1], digest)

    def test_unknown_protobuf_fields_are_ignored(self):
        exam = decode_oef(fixture() + blob(99, b'future field'))
        self.assertEqual(len(exam['questions']), 1)

    def test_corruption_and_invalid_metadata_rejected(self):
        for raw in (b'', fixture()[:-1], b'\xff' * 20, b'\x0f', fixture(passmark=float('nan')), fixture(minutes=1441)):
            with self.assertRaises(ValueError):
                decode_oef(raw)

    def test_invalid_legacy_records_are_data_only_and_rejected(self):
        header = b'\x00' + struct.pack('<iiii', 1, -1, 1, 0)
        for raw in (header, header + b'\x15', header + b'\x09\x01\x00\x00\x00\x0b'):
            with self.assertRaises(ValueError):
                decode_oef(raw)

    def test_jpeg_image_converted_to_png(self):
        from PIL import Image
        image_data = io.BytesIO()
        Image.new('RGB', (3, 2), 'red').save(image_data, 'JPEG')
        image = decode_oef(fixture(image=image_data.getvalue()))['questions'][0]['images'][0]
        with Image.open(io.BytesIO(image)) as decoded:
            self.assertEqual(decoded.format, 'PNG')
            self.assertEqual(decoded.size, (3, 2))

    def test_corrupt_image_is_not_silently_omitted(self):
        with self.assertRaisesRegex(OEFError, 'image'):
            decode_oef(fixture(image=b'not an image'))


if __name__ == '__main__':
    unittest.main()
