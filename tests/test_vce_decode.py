import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from test_vce_container import fixture
from vce_decode import decode_file
from vce_inspector import inspect_vce


class OfflineDecodeTests(unittest.TestCase):
    def test_export_preserves_source_and_labels_unavailable_record(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'original.vce'
            raw=fixture(plain=True,protected=True)
            source.write_bytes(raw)
            summary=decode_file(source,root/'decoded')
            export=Path(summary['export'])
            result=json.loads(export.read_text(encoding='utf-8'))
            self.assertEqual(source.read_bytes(),raw)
            self.assertEqual(summary['decoded_records'],1)
            self.assertFalse(result['all_records_structurally_decoded'])
            self.assertEqual(result['records'][0]['prompt_documents'][0]['text'],'An original question')
            self.assertEqual(result['records'][0]['content_document_status'], 'roles_validated')
            self.assertEqual([d['role'] for d in result['records'][0]['content_documents']],
                             ['prompt', 'choice', 'choice', 'explanation'])
            self.assertEqual(result['records'][1]['field_framing']['prompt']['status'],'protected_pool_unavailable')
            self.assertNotIn('prompt_documents',result['records'][1])
            asset=result['records'][0]['prompt_data']
            actual=(export.parent/asset['path']).read_bytes()
            self.assertEqual(hashlib.sha256(actual).hexdigest(),asset['sha256'])
            self.assertIn('Question 2 — unavailable',(export.parent/'questions.txt').read_text(encoding='utf-8'))

    def test_format63_metadata_inspection_and_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'original.vce'
            source.write_bytes(fixture(plain=True,format_value=63))
            self.assertEqual(inspect_vce(source)['format'],63)
            result=decode_file(source,root/'decoded')
            self.assertEqual((result['format'],result['records'],result['decoded_records']),(63,2,2))
