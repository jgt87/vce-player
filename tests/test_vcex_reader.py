import base64
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from exam_engine import load_exam, score
from vcex_reader import read_vcex, practice_exam, VCEXError


def block(value):
    if not isinstance(value, bytes):
        value = str(value).encode()
    size = str(len(value)).encode()
    return bytes([len(size)]) + size + value


def encoded(value):
    return base64.b64encode(json.dumps(value).encode())


def fixture(password=b'SP', protected=False, image=False):
    q = dict(x0='q1', x1='1', x2='<p>Original question &amp; context</p>',
             x3='<p>Original explanation.</p>',
             x4=json.dumps({'x0': [dict(x1=True, x3='<p>First</p>'), dict(x1=False, x3='<p>Second</p>')]}),
             x5=1, x7='', x9='section', x10=[])
    if image:
        q['x2'] += '[@_img_picture_@]'
    payload = b'PRFEXV12' + bytes(1025)
    payload += b''.join(block(v) for v in (b'EP', password, b'public-id', b'', 1, int(image)))
    for v in ({'d1': 'Original VCEX fixture', 'd2': 'OWN-1'}, [],
              [{'d0': 'section', 'd1': 'Basics'}], [], []):
        payload += block(encoded(v))
    if image:
        payload += block(b'picture') + block(b'\x89PNG\r\n\x1a\nfixture')
    payload += block((b'*' if protected else b'') + encoded(q))
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('exam.bin.d', payload)
    return b'PV12' + out.getvalue()[4:]


class VCEXTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'original.vcex'

    def write(self, **kwargs):
        self.path.write_bytes(fixture(**kwargs))
        return read_vcex(self.path)

    def test_import_scoring_and_stable_resume_digest(self):
        self.write()
        exam, digest = load_exam(self.path)
        self.assertEqual(exam['questions'][0]['prompt'], 'Original question & context')
        self.assertEqual(exam['questions'][0]['section'], 'Basics')
        self.assertEqual(exam['questions'][0]['options'], ['First', 'Second'])
        self.assertEqual(score(exam, {'0': [0]})['percent'], 100)
        self.assertTrue(exam['practice_only'])
        self.assertEqual(load_exam(self.path)[1], digest)

    def test_protected_records_never_enter_practice(self):
        data = self.write(protected=True)
        self.assertEqual(data['encrypted_count'], 1)
        self.assertEqual(data['readable_count'], 0)
        with self.assertRaisesRegex(VCEXError, 'No supported readable'):
            practice_exam(data)

    def test_password_gate(self):
        with self.assertRaisesRegex(VCEXError, 'password'):
            practice_exam(self.write(password=b'SPnonemptyhash'))

    def test_embedded_prompt_image_retained(self):
        q = practice_exam(self.write(image=True))['questions'][0]
        self.assertIn('[Image 1]', q['prompt'])
        self.assertEqual(len(q['images']), 1)

    def test_missing_image_does_not_produce_incomplete_question(self):
        data = self.write(image=True)
        data['images'].clear()
        with self.assertRaisesRegex(VCEXError, 'No supported readable'):
            practice_exam(data)

    def test_unsupported_layout_does_not_get_scored(self):
        data = self.write()
        data['records'][0]['data']['x2'] = '<table><tr><td>Layout</td></tr></table>'
        with self.assertRaisesRegex(VCEXError, 'No supported readable'):
            practice_exam(data)

    def test_truncated_and_unknown_containers(self):
        for raw in (fixture()[:-20], b'PV11', b'invalid'):
            self.path.write_bytes(raw)
            with self.assertRaises(VCEXError):
                read_vcex(self.path)

    def test_archive_crc_failure(self):
        raw = bytearray(fixture())
        raw[14] ^= 1  # local CRC disagrees with central CRC only; alter data too
        raw[60] ^= 1
        self.path.write_bytes(raw)
        with self.assertRaises(ValueError):
            read_vcex(self.path)


if __name__ == '__main__':
    unittest.main()
