"""Bounded readers for the observed RichView text/PNG subset.

Wire evidence: analysis/compatibility/question-schema-findings.md. This is
not a complete RichView implementation. Unsupported items are reported.
"""
from dataclasses import dataclass
import re
import struct
import zlib

MAX_DOCUMENT = 16 * 1024 * 1024
MAX_ITEMS = 10000
NUMERIC_LINE = re.compile(rb'-?\d+(?: -?\d+){5,6}\r\n')
ITEM_LINE = re.compile(rb'(-?\d+)((?: -?\d+){4}) (-?\d+|"[^"\r\n]*")((?: -?\d+){0,8})\r\n')
LIST_CONTROL = re.compile(rb'-11 0 0 0 0 0 [01] 0 1 [01]\r\n')
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


@dataclass(frozen=True)
class RichViewDocument:
    text: str
    images: tuple[bytes, ...] = ()
    warnings: tuple[str, ...] = ()
    links: tuple[str, ...] = ()


def _png_valid(data):
    if not data.startswith(PNG_SIGNATURE):
        return False
    pos = 8
    first = True
    while pos + 12 <= len(data):
        length = struct.unpack_from('>I', data, pos)[0]
        end = pos + 12 + length
        if end > len(data):
            return False
        kind = data[pos + 4:pos + 8]
        if first and (kind != b'IHDR' or length != 13):
            return False
        first = False
        expected = struct.unpack_from('>I', data, end - 4)[0]
        if zlib.crc32(data[pos + 4:end - 4]) & 0xffffffff != expected:
            return False
        if kind == b'IEND':
            return length == 0 and end == len(data)
        pos = end
    return False


def _decode_text(body, unicode_text):
    # RichView stores ASCII CRLF delimiters amongst UTF-16LE runs.
    runs = body.split(b'\r\n')
    encoding = 'utf-16-le' if unicode_text else 'cp1252'
    return '\n'.join(run.decode(encoding) for run in runs).replace('\u2029', '\n').replace('\u2028', '\n')


def _text_end(data, pos, unicode_text):
    for candidate in ITEM_LINE.finditer(data, pos):
        start = candidate.start()
        if start == pos:
            return start, start
        if data[start - 2:start] == b'\r\n':
            return start - 2, start
        # Some observed RVFs separate runs with a UTF-16 paragraph marker
        # rather than an ASCII CRLF. Preserve that marker in the text body.
        if unicode_text and data[start - 2:start] in (b'\x29\x20', b'\x28\x20'):
            return start, start
    return len(data), len(data)


def parse_richview(data):
    """Read one raw RVF document, preserving unsupported-item warnings."""
    data = bytes(data)
    if len(data) > MAX_DOCUMENT:
        raise ValueError('RichView document exceeds the size limit.')
    first_end = data.find(b'\r\n')
    if first_end < 0 or not re.fullmatch(rb'-8 \d+ \d+ \d+', data[:first_end]):
        raise ValueError('Unsupported RichView document header.')
    pos = first_end + 2
    text, images, warnings, links = [], [], [], []
    for _ in range(MAX_ITEMS):
        if pos == len(data):
            break
        match = ITEM_LINE.match(data, pos)
        if not match:
            warnings.append(f'Unsupported RichView item header at byte {pos}.')
            break
        values = [int(match.group(1))] + [int(value) for value in match.group(2).split()]
        if match.group(3).startswith(b'"'):
            links.append(match.group(3)[1:-1].decode('cp1252'))
        pos = match.end()
        style = values[0]
        if style >= 0:
            end, next_pos = _text_end(data, pos, bool(values[3] & 8))
            try:
                text.append(_decode_text(data[pos:end], bool(values[3] & 8)))
            except UnicodeError:
                warnings.append(f'Invalid text encoding in RichView item at byte {pos}.')
            pos = next_pos
        elif match.group() == b'-9 0 0 0 0 0 7\r\n':
            # Observed zero-payload control preceding ordinary item headers.
            # Its formatting semantics are not needed for text extraction.
            continue
        elif LIST_CONTROL.fullmatch(match.group()) and ITEM_LINE.match(data, pos):
            # Observed zero-payload list controls; preserve subsequent text.
            continue
        elif style == -3:
            # Observed picture: blank line, Delphi graphic class, LE32 size.
            if data[pos:pos + 2] == b'\r\n':
                pos += 2
            class_end = data.find(b'\r\n', pos, min(len(data), pos + 256))
            if class_end < 0 or class_end + 6 > len(data):
                warnings.append('Truncated RichView picture header.')
                break
            graphic_class = data[pos:class_end]
            pos = class_end + 2
            # Observed scaled PNGs carry these ASCII properties before size.
            properties = re.match(rb'width=\d{1,9}\r\nheight=\d{1,9}\r\n',data[pos:pos+64])
            if properties:
                pos += properties.end()
            if pos + 4 > len(data):
                warnings.append('Truncated RichView picture size.')
                break
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            if size > MAX_DOCUMENT or pos + size > len(data):
                warnings.append('Truncated or oversized RichView picture.')
                break
            picture = data[pos:pos + size]
            pos += size
            if graphic_class == b'TPngImage' and _png_valid(picture):
                images.append(picture)
                text.append('[Image]')
            elif graphic_class == b'TJPEGImage' and picture.startswith(b'\xff\xd8\xff') and picture.endswith(b'\xff\xd9'):
                images.append(picture)
                text.append('[Image]')
                warnings.append('JPEG bytes extracted; full image decoding is not validated.')
            else:
                warnings.append('Unsupported or invalid RichView picture.')
                text.append('[Unsupported image]')
        else:
            warnings.append(f'Unsupported RichView item style {style}.')
            text.append('[Unsupported document item]')
            break
    else:
        raise ValueError('RichView document exceeds the item limit.')
    return RichViewDocument('\n'.join(text).strip(), tuple(images), tuple(warnings), tuple(links))


def parse_nested_documents(data):
    """Read complete seeded-length/raw-RVF sequences used by question streams."""
    data = bytes(data)
    if len(data) > MAX_DOCUMENT:
        raise ValueError('RichView document sequence exceeds the size limit.')
    pos, result = 0, []
    while pos < len(data):
        if len(result) >= MAX_ITEMS or pos + 5 > len(data):
            raise ValueError('Truncated or excessive RichView document sequence.')
        # Mode4 seed produces zero initial key; seed is still consumed.
        key, plain = 0, bytearray()
        for index, cipher in enumerate(data[pos + 1:pos + 5]):
            value = cipher ^ key
            plain.append(value)
            key = ((key + (cipher ^ value)) & 255) | (index + 1)
        size = int.from_bytes(plain, 'little', signed=True)
        pos += 5
        if size < 0 or size > MAX_DOCUMENT or pos + size > len(data):
            raise ValueError('Invalid nested RichView document length.')
        result.append(parse_richview(data[pos:pos + size]))
        pos += size
    return tuple(result)
