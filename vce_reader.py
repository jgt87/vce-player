"""Modern VCE primitives recovered from the installed Player and supplied files.

This module currently reads metadata. Full exam record parsing is separate.
"""
import struct
from pathlib import Path


class VCEError(ValueError):
    pass


class Reader:
    def __init__(self, data, pos=0, pool=b'', protected_pool=None):
        self.data = memoryview(data)
        self.pos = pos
        self.pool = pool
        self.protected_pool = protected_pool

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise VCEError(f'Truncated VCE data at byte {self.pos}.')
        result = bytes(self.data[self.pos:self.pos + size])
        self.pos += size
        return result

    def u8(self):
        return self.take(1)[0]

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]

    def u64(self):
        return struct.unpack('<Q', self.take(8))[0]

    def length(self):
        seed = self.u8()
        key = (128 + (seed ^ (seed ^ 128))) & 255
        plain = bytearray()
        for i in range(4):
            cipher = self.u8()
            value = cipher ^ key
            plain.append(value)
            key = (((key + (cipher ^ value)) & 255) | (i + 1)) & 255
        value = int.from_bytes(plain, 'little', signed=True)
        if value < 0:
            raise VCEError('Negative VCE block length.')
        return value

    def blob(self, limit=16 * 1024 * 1024):
        length = self.length()
        if not 1 <= length <= limit:
            raise VCEError(f'Invalid encrypted VCE block length {length}.')
        marker = self.u8()
        cipher_length = length - 5
        if cipher_length <= 0:
            # 0x8528b8 consumes the marker only for empty blocks.
            return b''
        key_offset = self.u32()
        ciphertext = self.take(cipher_length)
        pool = self.protected_pool if marker >= 0x80 else self.pool
        if pool is None:
            raise VCEError('VCE field requires the unavailable protected content-key pool.')
        if key_offset + 48 > len(pool) or cipher_length % 16:
            raise VCEError('Invalid VCE key offset or cipher block size.')
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.padding import PKCS7
        except ImportError as error:
            raise VCEError('Format 62 requires cryptography. Install requirements.txt.') from error
        try:
            decryptor = Cipher(algorithms.AES(pool[key_offset:key_offset + 32]),
                               modes.CBC(pool[key_offset + 32:key_offset + 48])).decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()
            unpadder = PKCS7(128).unpadder()
            return unpadder.update(padded) + unpadder.finalize()
        except ValueError as error:
            raise VCEError('VCE block decryption or padding check failed.') from error

    def text(self):
        try:
            return self.blob(limit=1024 * 1024).decode('utf-8')
        except UnicodeError as error:
            raise VCEError('Invalid UTF-8 VCE metadata string.') from error


def read_metadata(path):
    # Bounded prefix: only metadata and the initial key pool are required.
    with open(path, 'rb') as stream:
        data = stream.read(1024 * 1024)
    reader = Reader(data)
    if reader.take(2) != b'\x85\xa8':
        raise VCEError('Invalid VCE signature.')
    format_value = reader.u8() * 10 + reader.u8()
    if format_value not in (62, 63):
        raise VCEError(f'This reader currently targets formats 62 and 63, received {format_value}.')
    container_value = reader.u32()
    pool_length = reader.length()
    if not 48 <= pool_length <= 65536:
        raise VCEError('Invalid initial VCE key pool size.')
    reader.pool = reader.take(pool_length)
    reserved_length = reader.length()
    reader.take(reserved_length)
    metadata_offset = reader.pos
    flags = reader.u8()
    number, title = reader.text(), reader.text()
    passing_score_raw, time_limit_minutes = reader.u32(), reader.u32()
    file_version = reader.text()
    created, modified = reader.u64(), reader.u64()
    return dict(format=format_value, size=Path(path).stat().st_size,
                exam_number=number, title=title, file_version=file_version,
                passing_score_raw=passing_score_raw, time_limit_minutes=time_limit_minutes,
                created_raw=created, modified_raw=modified, flags=flags,
                password_required=bool(flags & 4), metadata_offset=metadata_offset,
                metadata_end=reader.pos, container_value=container_value,
                metadata_status=f'Format-{format_value} metadata decoded; question coverage is reported separately.')
