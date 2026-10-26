import struct
import unittest
import zlib

from richview import parse_nested_documents, parse_richview


def document(text):
    return b'-8 1 3 1\r\n0 1 0 8 0 0\r\n' + text.encode('utf-16-le')


def nested(raw):
    value = struct.pack('<i', len(raw))
    return b'\x42' + bytes([value[0], value[1] ^ 1, value[2] ^ 2, value[3] ^ 7]) + raw


def chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


class RichViewTests(unittest.TestCase):
    def test_unicode_paragraphs_and_ascii_delimiters(self):
        raw = document('Original café\u2029Second') + b'\r\n' + ' paragraph'.encode('utf-16-le')
        parsed = parse_richview(raw)
        self.assertEqual(parsed.text, 'Original café\nSecond\n paragraph')
        self.assertFalse(parsed.warnings)

    def test_nested_choices_and_empty_document(self):
        values = ['Original question', 'Yes', 'No', '\u2029']
        result = parse_nested_documents(b''.join(nested(document(value)) for value in values))
        self.assertEqual([item.text for item in result], ['Original question', 'Yes', 'No', ''])

    def test_picture_then_text(self):
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(b'\0\xff\xff\xff')) + chunk(b'IEND', b'')
        raw = b'-8 1 3 1\r\n-3 3 11 0 2 0 0\r\n\r\nTPngImage\r\n' + struct.pack('<I', len(png)) + png
        raw += b'0 2 11 8 0 0\r\n' + 'Original caption'.encode('utf-16-le')
        result = parse_richview(raw)
        self.assertEqual(result.text, '[Image]\nOriginal caption')
        self.assertEqual(result.images, (png,))
        self.assertFalse(result.warnings)

    def test_truncated_nested_length_rejected(self):
        with self.assertRaises(ValueError):
            parse_nested_documents(nested(document('Original'))[:-1])

    def test_unsupported_item_is_explicit(self):
        result = parse_richview(b'-8 1 3 1\r\n-99 1 0 0 0 0\r\nopaque')
        self.assertTrue(result.warnings)
        self.assertIn('Unsupported', result.text)

    def test_invalid_utf16_does_not_guess(self):
        result = parse_richview(b'-8 1 3 1\r\n0 1 0 8 0 0\r\nx')
        self.assertTrue(result.warnings)
        self.assertEqual(result.text, '')

    def test_observed_zero_payload_control_and_unknown_variant(self):
        raw=b'-8 1 3 1\r\n-9 0 0 0 0 0 7\r\n'+document('Original')[10:]
        result=parse_richview(raw)
        self.assertEqual(result.text,'Original')
        self.assertFalse(result.warnings)
        unknown=parse_richview(raw.replace(b'-9 0 0 0 0 0 7',b'-9 0 0 0 0 0 8'))
        self.assertTrue(unknown.warnings)

    def test_utf16_paragraph_boundary_then_quoted_link_header(self):
        raw=document('Original\u2029')
        raw+=b'17 1 0 8 0 "https://example.test/reference"\r\n'+'Caption'.encode('utf-16le')
        parsed=parse_richview(raw)
        self.assertEqual(parsed.text,'Original\n\nCaption')
        self.assertEqual(parsed.links,('https://example.test/reference',))
        self.assertFalse(parsed.warnings)

    def test_observed_list_control_preserves_following_text(self):
        raw=document('Original introduction\u2029')+b'-11 0 0 0 0 0 1 0 1 1\r\n'
        raw+=b'0 1 -1 9 0 0\r\n'+'Original list entry'.encode('utf-16le')
        result=parse_richview(raw)
        self.assertIn('Original introduction',result.text)
        self.assertIn('Original list entry',result.text)
        self.assertFalse(result.warnings)

    def test_png_dimensions_before_length(self):
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
        png+=chunk(b'IDAT',zlib.compress(b'\0\xff\xff\xff'))+chunk(b'IEND',b'')
        raw=b'-8 1 3 1\r\n-3 5 0 0 2 0 0\r\n\r\nTPngImage\r\nwidth=1\r\nheight=1\r\n'
        result=parse_richview(raw+struct.pack('<I',len(png))+png)
        self.assertEqual(result.images,(png,))
        self.assertFalse(result.warnings)

    def test_jpeg_is_preserved_with_validation_limit(self):
        framed=b'\xff\xd8\xff\xe0synthetic-not-a-complete-jpeg\xff\xd9'
        raw=b'-8 1 3 1\r\n-3 3 0 0 2 0 0\r\n\r\nTJPEGImage\r\n'
        result=parse_richview(raw+struct.pack('<I',len(framed))+framed)
        self.assertEqual(result.images,(framed,))
        self.assertTrue(any('not validated' in w for w in result.warnings))



if __name__ == '__main__':
    unittest.main()
