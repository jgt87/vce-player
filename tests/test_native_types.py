import struct
import unittest

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from native_types import read_type_payload
from vce_reader import Reader, VCEError
from test_vce_container import length


POOL = bytes(range(128))


def field(plain):
    padder = PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    cipher = Cipher(algorithms.AES(POOL[9:41]), modes.CBC(POOL[41:57])).encryptor()
    encrypted = cipher.update(padded) + cipher.finalize()
    size = struct.pack('<I', len(encrypted) + 5)
    header = b'\x42' + bytes([size[0], size[1] ^ 1, size[2] ^ 2, size[3] ^ 7])
    return header + b'\x02' + struct.pack('<I', 9) + encrypted


class NativeTypeTests(unittest.TestCase):
    def parse(self, kind, data):
        reader = Reader(data, pool=POOL)
        result = read_type_payload(reader, kind, end=len(data))
        self.assertEqual(reader.pos, len(data))
        return result

    def test_image_variants_preserve_binary_order(self):
        data = field(b'original image') + b'\x03\x07' + field(b'original image map')
        for kind in (2, 3, 9):
            result = self.parse(kind, data)
            self.assertEqual(result['image_flags'], [3, 7])
            self.assertEqual(result['image_aux_data'], b'original image map')

    def test_tree_variants_preserve_strings_and_flags(self):
        data = b'\x02' + length(13) + b'Original root' + length(20) + b'Original instruction'
        data += field(b'original tree') + b'\x01\x00'
        for kind in (4, 5):
            result = self.parse(kind, data)
            self.assertEqual(result['tree_mode'], 2)
            self.assertEqual(result['tree_labels'], ['Original root', 'Original instruction'])
            self.assertEqual(result['tree_flags'], [1, 0])

    def test_empty_tree_labels_are_raw_zero_length_fields(self):
        data = b'\x00' + length(0) + length(0) + field(b'original tree') + b'\x00\x00'
        self.assertEqual(self.parse(4, data)['tree_labels'], ['', ''])

    def test_connection_and_blank_shapes(self):
        data = field(b'original nodes') + field(b'original links') + field(b'Original label')
        data += struct.pack('<II', 3, 4)
        self.assertEqual(self.parse(7, data)['connection_fields'], [3, 4])
        result = self.parse(8, struct.pack('<I', 2) + b'\x01\x00\x01')
        self.assertEqual(result['blank_count'], 2)
        self.assertEqual(result['blank_flags'], [1, 0, 1])

    def test_type_high_bit_masks_factory_type(self):
        data = struct.pack('<I', 2) + b'\x00\x00\x00' + field(b'Original label')
        self.assertEqual(self.parse(128, data)['choice_count'], 2)

    def test_boundary_rejects_extra_or_truncated_and_is_atomic(self):
        data = struct.pack('<I', 2) + b'\x01\x00\x01'
        for bad in (data[:-1], data + b'\x00'):
            reader = Reader(bad, pool=POOL)
            with self.assertRaises(VCEError):
                read_type_payload(reader, 8, end=len(bad))
            self.assertEqual(reader.pos, 0)

    def test_unknown_type_rejected(self):
        with self.assertRaisesRegex(VCEError, 'Unknown'):
            self.parse(6, b'')


if __name__ == '__main__':
    unittest.main()
