"""Structural format-62 reader, with explicit encrypted/unsupported records.

This parses record envelopes without treating an undecodable record as a valid
question. The full content key pool and all interaction schemas remain separate
compatibility obligations.
"""
import struct
from vce_reader import Reader, VCEError, read_metadata
from native_types import read_type_payload
from question_schema import parse_question_schema
from question_schema import parse_question_schema


def skip_blob(reader):
    length = reader.length()
    if length < 1:
        raise VCEError('Invalid VCE field envelope.')
    reader.take(1)
    if length > 5:
        reader.take(length - 1)


def read_container(path, content_pool=None):
    metadata = read_metadata(path)
    if metadata['password_required']:
        raise VCEError('Password-protected VCE files are not supported by this reader yet.')
    with open(path, 'rb') as stream:
        data = stream.read(128 * 1024 * 1024 + 1)
    if len(data) > 128 * 1024 * 1024:
        raise VCEError('VCE file exceeds the supported 128 MiB limit.')
    initial = Reader(data, 8)
    pool_length = initial.length()
    initial_pool = initial.take(pool_length)
    protected_pool = None if content_pool is None else bytes(content_pool)
    reader = Reader(data, metadata['metadata_end'], initial_pool, protected_pool)
    # Shared RichView styles and the file description precede the references.
    styles = reader.blob()
    description = reader.blob()
    reference_count = reader.u32()
    if reference_count != 0:
        raise VCEError('Unsupported pre-reference field: expected the observed zero value.')
    skip_blob(reader)
    group_count = reader.u32()
    if group_count > 10000:
        raise VCEError('Invalid VCE group count.')
    groups = []
    records = []
    for group_index in range(group_count):
        group_start = reader.pos
        group_end = None
        if metadata['format'] == 63:
            group_size = reader.length()
            group_end = reader.pos + group_size
            if group_size < 1 or group_end > len(data):
                raise VCEError('Invalid format-63 reference envelope extent.')
        group_kind = reader.u8()
        if group_kind not in (0, 1):
            raise VCEError('Unknown top-level exam reference type.')
        if metadata['format'] == 63 and group_kind == 1:
            raise VCEError('Format-63 nested reference layout is not validated yet.')
        title_offset = reader.pos
        try:
            title = reader.text()
            title_status = 'decoded'
        except VCEError as error:
            reader.pos = title_offset
            skip_blob(reader)
            title = f'Group {group_index + 1}'
            title_status = str(error)
        children_count = reader.u32() if group_kind == 1 else 1
        if children_count > 10000:
            raise VCEError('Invalid child reference count.')
        group = dict(title=title, title_status=title_status, children=[], count=0,
                     offset=group_start, envelope_end=group_end)
        for child_index in range(children_count):
            kind = reader.u8() if group_kind == 1 else 0
            if kind not in (0, 1):
                raise VCEError('Unknown child exam reference type.')
            # A top-level plain list stores its question count immediately
            # after the title. The raw tag belongs to nested references only.
            tag = reader.u32() if group_kind == 1 else None
            child = dict(kind=kind, tag=tag, records=[])
            if kind == 1:
                case_start = reader.pos
                try:
                    child['title'] = reader.text()
                except VCEError:
                    reader.pos = case_start
                    skip_blob(reader)
                    child['title'] = 'Case study'
                child['value_before_body'] = reader.u32()
                skip_blob(reader)
                body_offset = reader.pos
                try:
                    child['body'] = reader.blob()
                except VCEError:
                    reader.pos = body_offset
                    skip_blob(reader)
                    child['body'] = None
                child['value_after_body'] = reader.u32()
            question_count = reader.u32()
            if question_count > 100000:
                raise VCEError('Invalid VCE question count.')
            for index in range(question_count):
                start = reader.pos
                size = reader.length()
                end = reader.pos + size
                if size < 1 or end > (group_end if group_end is not None else len(data)):
                    raise VCEError('Invalid question envelope extent.')
                record = dict(index=len(records), group=group_index, child=child_index,
                              offset=start, payload_offset=reader.pos, end=end)
                question_reader = Reader(memoryview(data)[:end], reader.pos, initial_pool, protected_pool)
                try:
                    identity = question_reader.blob()
                    record['id'] = struct.unpack_from('<I', identity)[0] if len(identity) >= 4 else None
                    record['type'] = question_reader.u8()
                    record['common_fields'] = [question_reader.u32() for _ in range(3)]
                    record['prompt_data'] = question_reader.blob()
                    record['answer_data'] = question_reader.blob()
                    if struct.unpack('<i', struct.pack('<I', record['common_fields'][2]))[0] > 0:
                        record['extra_data'] = question_reader.blob()
                    record.update(read_type_payload(question_reader, record['type'], end=end))
                    record['decoded'] = True
                    record['parsed_end'] = question_reader.pos
                except (VCEError, struct.error) as error:
                    record['decoded'] = False
                    record['error'] = str(error)
                if record['decoded']:
                    try:
                        record['question_schema'] = parse_question_schema(record)
                        record['schema_status'] = 'decoded'
                    except (VCEError, UnicodeError) as error:
                        record['schema_status'] = 'unavailable'
                        record['schema_error'] = str(error)
                if record['decoded']:
                    try:
                        record['question_schema'] = parse_question_schema(record)
                        record['schema_status'] = 'decoded'
                    except (VCEError, UnicodeError) as error:
                        record['schema_status'] = 'unavailable'
                        record['schema_error'] = str(error)
                records.append(record)
                child['records'].append(record['index'])
                reader.pos = end
            group['count'] += question_count
            group['children'].append(child)
        if group_end is not None and reader.pos != group_end:
            raise VCEError('Unparsed format-63 reference envelope bytes.')
        groups.append(group)
    return dict(metadata=metadata, groups=groups, records=records, styles=styles,
                description=description, parsed_end=reader.pos,
                trailing_bytes=len(data) - reader.pos,
                decoded_count=sum(r['decoded'] for r in records))
