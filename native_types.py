"""Modern VCE per-type tails after the three common integers/documents.

Field order comes from shipped Delphi instance loaders, not type-name guesses.
Evidence: analysis/compatibility/question-type-loaders.json (same demo SHA256).
This preserves binary interaction data; rendering/scoring it is a separate step.
"""
from vce_reader import Reader, VCEError

TYPE_CLASSES = {
    0: 'TMultipleChoiceQuestion', 1: 'TMultipleChoiceQuestion',
    2: 'TImageQuestion', 3: 'TImageQuestion', 9: 'TImageQuestion',
    4: 'TTreeQuestion', 5: 'TTreeQuestion',
    7: 'TDropAndConnectQuestion', 8: 'TFillInTheBlankQuestion',
}


def _raw_text(reader):
    # Android C3520z10.B/C and C3167v10.A/B use t(), not encrypted p().
    size = reader.length()
    if size > 1024 * 1024:
        raise VCEError('Oversized raw question label.')
    try:
        return reader.take(size).decode('utf-8')
    except UnicodeError as error:
        raise VCEError('Invalid UTF-8 raw question label.') from error


def _read(reader, code):
    kind = code & 127
    if kind not in TYPE_CLASSES:
        raise VCEError(f'Unknown native question type {kind}.')
    result = {'native_class': TYPE_CLASSES[kind]}
    if kind in (0, 1):
        result['choice_count'] = reader.u32()
        result['choice_flags'] = [reader.u8() for _ in range(3)]
        result['label'] = reader.text()
    elif kind in (2, 3, 9):
        # 0x93eba0: stream+38, byte+34, byte+35, stream+3c.
        result['image_data'] = reader.blob()
        result['image_flags'] = [reader.u8(), reader.u8()]
        result['image_aux_data'] = reader.blob()
    elif kind in (4, 5):
        # 0x942af4: byte+3c, strings+34/+38, stream+40, bool+3d/+3e.
        result['tree_mode'] = reader.u8()
        result['tree_labels'] = [_raw_text(reader), _raw_text(reader)]
        result['tree_data'] = reader.blob()
        result['tree_flags'] = [reader.u8(), reader.u8()]
    elif kind == 7:
        # 0x93df04: stream+40/+44, string+34, int+3c, int+38.
        result['connection_data'] = [reader.blob(), reader.blob()]
        result['label'] = reader.text()
        result['connection_fields'] = [reader.u32(), reader.u32()]
    else:  # type8; 0x93c588: int+34, three bool bytes+38/+39/+3a.
        result['blank_count'] = reader.u32()
        result['blank_flags'] = [reader.u8() for _ in range(3)]
    return result


def read_type_payload(reader, type_code, *, end=None):
    """Read a format>=61 type tail; optionally enforce an exact record end.

    Pass the outer record's end to prevent reads across its boundary. In this
    mode failure leaves the caller's reader position unchanged.
    """
    if end is None:
        return _read(reader, type_code)
    if end < reader.pos or end > len(reader.data):
        raise VCEError('Invalid native question boundary.')
    bounded = Reader(reader.data[:end], reader.pos, reader.pool, reader.protected_pool)
    result = _read(bounded, type_code)
    if bounded.pos != end:
        raise VCEError(f'Unparsed native question bytes: {end - bounded.pos}.')
    reader.pos = bounded.pos
    return result
