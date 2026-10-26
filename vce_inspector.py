"""Bounded metadata inspection using the existing research codec.

Only the first two format-31 strings are interpreted. No question extraction.
"""
from pathlib import Path
from analysis.phase3.codec.vce_codec import decode_field, encode_field


def inspect_vce(path):
    with open(path, 'rb') as stream:
        prefix = stream.read(8192)
    if len(prefix) < 4 or prefix[:2] != b'\x85\xa8':
        raise ValueError('Invalid VCE signature or truncated header.')
    version = prefix[2] * 10 + prefix[3]
    result = dict(format=version, size=Path(path).stat().st_size,
                  metadata_status='Not decoded: only format 31 has sample-validated string framing.')
    if version in (62, 63):
        from vce_reader import read_metadata
        return read_metadata(path)
    if version == 31:
        try:
            pos = 5
            for key in ('exam_number', 'title'):
                start = pos
                seed, length, data, pos = decode_field(prefix, pos)
                if length > 4096 or encode_field(data, seed) != prefix[start:pos]:
                    raise ValueError('Metadata length or round-trip check failed.')
                result[key] = data.decode('utf-8', errors='backslashreplace')
            result['metadata_status'] = 'First two strings decoded using sample-validated framing; remaining payload not validated.'
        except (IndexError, ValueError, OverflowError):
            result.pop('exam_number', None)
            result.pop('title', None)
            result['metadata_status'] = 'Metadata could not be decoded within the bounded prefix.'
    return result
