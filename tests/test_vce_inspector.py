import tempfile
import unittest
from pathlib import Path
from analysis.phase3.codec.vce_codec import encode_field, f, g
from vce_inspector import inspect_vce


class InspectorTests(unittest.TestCase):
    def inspect_bytes(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'original.vce'
            path.write_bytes(data)
            return inspect_vce(path)

    def test_trace_vectors(self):
        self.assertEqual(f(77, 205), 155)
        self.assertEqual(g(128, 155, 0), 144)
        self.assertEqual(g(144, 15, 1), 95)

    def test_original_metadata(self):
        data = b'\x85\xa8\x03\x01\x00' + encode_field(b'OWN-001', 77) + encode_field(b'Original exam', 14)
        result = self.inspect_bytes(data)
        self.assertEqual(result['exam_number'], 'OWN-001')
        self.assertEqual(result['title'], 'Original exam')

    def test_truncated_metadata(self):
        result = self.inspect_bytes(b'\x85\xa8\x03\x01\x00\x4d')
        self.assertNotIn('title', result)
        self.assertIn('bounded', result['metadata_status'])

    def test_other_version_has_no_assumed_decoder(self):
        result = self.inspect_bytes(b'\x85\xa8\x04\x02')
        self.assertEqual(result['format'], 42)
        self.assertNotIn('title', result)

    def test_invalid_signature(self):
        with self.assertRaises(ValueError):
            self.inspect_bytes(b'bad')
