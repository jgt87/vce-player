"""End-to-end checks available in both source and packaged desktop builds."""
import json
import os
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch


def run_selftest(player_class, report_path):
    checks = []
    with tempfile.TemporaryDirectory() as folder:
        with patch.dict(os.environ, {'LOCALAPPDATA': folder}):
            root = tk.Tk()
            root.withdraw()
            app = player_class(root)
            app.example()
            assert len(app.tree.get_children()) == 1
            checks.append('bundled example and exam import')
            app.start(False)
            app.inputs[0].set(True)
            app.move(1)
            app.inputs[0].set(True)
            app.inputs[1].set(True)
            app.marked.set(True)
            app.save_exit()
            app.tree.selection_set(app.digest)
            app.start(True)
            assert app.state['index'] == 1 and app.state['marked'] == [1]
            checks.append('question navigation, marking, persisted save/resume')
            app.move(1)
            app.inputs.set('127.0.0.1')
            app.move(1)
            app.inputs[1].set(True)
            with patch('player.messagebox.askyesno', return_value=True):
                app.finish()
            result = json.loads(app.store.db.execute('SELECT result FROM history').fetchone()[0])
            assert result['percent'] == 100 and result['correct'] == 4
            assert result['sections']['Protocols']['correct'] == 2
            checks.append('single/multiple choice, text scoring, section results, history')
            app.library()
            app.tree.selection_set(app.digest)
            app.practice.set(False)
            app.start(False)
            app.state['remaining'] = 0
            app.tick()
            assert not app.active
            assert app.store.db.execute('SELECT count(*) FROM history').fetchone()[0] == 2
            checks.append('timed expiry submits once')
            app.history()
            from richview import parse_nested_documents
            from vce_reader import Reader
            from native_view import show_native
            from native_study import practice_exam
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.padding import PKCS7
            import struct
            pool = bytes(range(64))
            padder = PKCS7(128).padder()
            padded = padder.update(b'Original native fixture') + padder.finalize()
            encryptor = Cipher(algorithms.AES(pool[:32]), modes.CBC(pool[32:48])).encryptor()
            encrypted = encryptor.update(padded) + encryptor.finalize()
            def header(value):
                b = struct.pack('<I', value)
                return bytes([77, b[0], b[1] ^ 1, b[2] ^ 2, b[3] ^ 7])
            encoded = header(len(encrypted) + 5) + b'\x02' + bytes(4) + encrypted
            assert Reader(encoded, pool=pool).blob() == b'Original native fixture'
            def document(value):
                raw = b'-8 1 3 1\r\n0 1 0 8 0 0\r\n' + value.encode('utf-16-le')
                return header(len(raw)) + raw
            prompt = b''.join(document(x) for x in ['Original question', 'First', 'Second', ''])
            record = dict(index=0, group=0, child=0, decoded=True, type=0, prompt_data=prompt,
                          answer_data=b'A', choice_count=2, choice_flags=[1, 0, 0])
            container = dict(metadata={'title': 'Original native fixture', 'exam_number': 'OWN-001'},
                             records=[record], decoded_count=1,
                             groups=[dict(title='Original section', count=1,
                                          children=[dict(kind=0, records=[0])])])
            assert len(parse_nested_documents(prompt)) == 4
            native_window = show_native(root, container)
            native_window.withdraw()
            native_window.update_idletasks()
            native_window.destroy()
            native_exam, native_digest = practice_exam(container, 'original-fixture')
            app.begin_session(native_exam, native_digest)
            assert app.active and app.state['practice']
            app.inputs[0].set(True)
            app.save_exit()
            checks.append('native AES dependency, RichView rendering, native viewer and subset practice')
            import base64
            import io
            import zipfile
            from exam_engine import load_exam, score
            from vcex_reader import read_vcex
            def block(value):
                raw = value if isinstance(value, bytes) else str(value).encode()
                digits = str(len(raw)).encode()
                return bytes([len(digits)]) + digits + raw
            def encoded(value):
                return base64.b64encode(json.dumps(value).encode())
            payload = b'PRFEXV12' + bytes(1025)
            payload += b''.join(block(v) for v in (b'EP', b'SP', b'NoKey', b'', 1, 0))
            for value in ({'d1': 'Original VCEX fixture'}, [], [], [], []):
                payload += block(encoded(value))
            question = dict(x1='1', x2='<p>Original VCEX question</p>', x3='<p>Explanation</p>',
                            x4=json.dumps({'x0': [dict(x1=True, x3='First'), dict(x1=False, x3='Second')]}), x5=1)
            payload += block(encoded(question))
            archive_data = io.BytesIO()
            with zipfile.ZipFile(archive_data, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('original.bin.d', payload)
            vcex_path = Path(folder) / 'original.vcex'
            vcex_path.write_bytes(b'PV12' + archive_data.getvalue()[4:])
            assert read_vcex(vcex_path)['readable_count'] == 1
            vcex_exam, vcex_digest = load_exam(vcex_path)
            app.begin_session(vcex_exam, vcex_digest)
            app.inputs[0].set(True)
            app.capture()
            assert score(vcex_exam, app.state['answers'])['percent'] == 100
            app.save_exit()
            checks.append('VCEX archive decoding, HTML conversion and practice scoring')
            from PIL import Image
            def varint(value):
                result = bytearray()
                while value > 127:
                    result.append((value & 127) | 128)
                    value >>= 7
                return bytes(result) + bytes([value])
            def field(number, value):
                raw = value.encode() if isinstance(value, str) else value
                return varint(number * 8 + 2) + varint(len(raw)) + raw
            image_data = io.BytesIO()
            Image.new('RGB', (3, 2), 'red').save(image_data, 'JPEG')
            properties = field(1, 'Original OEF fixture') + b'\x21' + struct.pack('<d', 700) + b'\x28\x1e'
            question = field(2, 'Original OEF question') + field(3, image_data.getvalue()) + b'\x20\x41'
            question += field(7, b'\x08\x41' + field(2, 'First')) + field(7, b'\x08\x42' + field(2, 'Second'))
            oef_path = Path(folder) / 'original.oef'
            oef_path.write_bytes(field(1, properties) + field(2, field(1, 'Original section') + field(2, question)))
            oef_exam, oef_digest = load_exam(oef_path)
            app.begin_session(oef_exam, oef_digest)
            assert len(app.question_images) == 1
            app.inputs[0].set(True)
            app.capture()
            assert score(oef_exam, app.state['answers'])['normalized_score'] == 1000
            app.save_exit()
            checks.append('OEF protobuf decoding, Pillow JPEG rendering and normalized scoring')
            root.update_idletasks()
            app.close()
    report = dict(passed=True, checks=checks)
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
