import struct
import unittest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from vce_reader import Reader, VCEError


def length_header(length, seed=91):
    key = 0
    result = bytearray([seed])
    for i, plain in enumerate(struct.pack('<I', length)):
        cipher = plain ^ key
        result.append(cipher)
        key = (((key + (cipher ^ plain)) & 255) | (i + 1)) & 255
    return bytes(result)


class ModernReaderTests(unittest.TestCase):
    def test_observed_length_vectors(self):
        self.assertEqual(Reader(bytes.fromhex('5f00050207')).length(), 1024)
        self.assertEqual(Reader(bytes.fromhex('6a00080207')).length(), 2304)

    def test_encrypted_field(self):
        pool = bytes(range(128))
        plaintext = b'Original study question'
        padder = PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        cipher = Cipher(algorithms.AES(pool[9:41]), modes.CBC(pool[41:57])).encryptor()
        encrypted = cipher.update(padded) + cipher.finalize()
        data = length_header(len(encrypted) + 5) + b'\x02' + struct.pack('<I', 9) + encrypted
        reader = Reader(data, pool=pool)
        self.assertEqual(reader.blob(), plaintext)
        self.assertEqual(reader.pos, len(data))

        # Marker high bit selects the independent response pool, even when
        # the offset would also fit the initial pool.
        protected_data = data[:5] + b'\x80' + data[6:]
        protected = Reader(protected_data, pool=bytes(128), protected_pool=pool)
        self.assertEqual(protected.blob(), plaintext)
        with self.assertRaisesRegex(VCEError, 'protected content-key pool'):
            Reader(protected_data, pool=pool).blob()
        with self.assertRaisesRegex(VCEError, 'decryption'):
            Reader(protected_data, pool=pool, protected_pool=bytes(128)).blob()
        # An unrelated protected pool cannot alter an initial-pool field.
        self.assertEqual(Reader(data, pool=pool, protected_pool=bytes(128)).blob(), plaintext)

    def test_truncated_and_invalid_lengths(self):
        with self.assertRaises(VCEError):
            Reader(b'\x00').length()
        with self.assertRaises(VCEError):
            Reader(length_header(100) + b'\x00').blob()

    def test_invalid_pool_offset(self):
        data = length_header(21) + b'\x02' + struct.pack('<I', 100) + bytes(16)
        with self.assertRaisesRegex(VCEError, 'key offset'):
            Reader(data, pool=bytes(48)).blob()

    def test_empty_field_consumes_marker_only(self):
        reader = Reader(length_header(1) + b'\x02')
        self.assertEqual(reader.blob(), b'')
        self.assertEqual(reader.pos, 6)
