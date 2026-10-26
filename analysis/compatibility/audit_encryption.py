"""Audit each question's block framing and key coverage without exporting content."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vce_container import read_container
from vce_reader import Reader, VCEError
from richview import parse_nested_documents


def audit(path):
    data = Path(path).read_bytes()
    container = read_container(path)
    initial = Reader(data, 8)
    pool = initial.take(initial.length())
    reserved_size = initial.length()
    records = []
    for record in container['records']:
        reader = Reader(memoryview(data)[:record['end']], record['payload_offset'], pool)
        fields = {}
        def block(name):
            start = reader.pos
            length = reader.length()
            marker = reader.u8()
            entry = dict(offset=start, framed_length=length, cipher_bytes=max(0, length - 5),
                         marker=marker, pool_selector='protected' if marker >= 128 else 'initial')
            if length > 5:
                key_offset = reader.u32()
                entry.update(key_offset=key_offset, key_and_iv_in_initial_pool=key_offset + 48 <= len(pool))
                reader.take(length - 5)
            end = reader.pos
            probe = Reader(memoryview(data)[:end], start, pool)
            decoded = None
            try:
                decoded = probe.blob()
                entry['status'] = 'padding_valid'
                entry['plaintext_bytes'] = len(decoded)
            except VCEError as error:
                entry['status'] = ('protected_pool_unavailable' if marker >= 128 else
                    'outside_initial_pool' if entry.get('key_and_iv_in_initial_pool') is False else 'decryption_failed')
                entry['error'] = str(error)
            fields[name] = entry
            return decoded
        try:
            block('identity')
            kind = reader.u8()
            common = [reader.u32() for _ in range(3)]
            prompt = block('prompt')
            block('answer')
            if common[2] < 0x80000000 and common[2] > 0:
                block('extra')
            if prompt is not None:
                try:
                    documents = parse_nested_documents(prompt)
                    fields['prompt']['richview_documents'] = len(documents)
                except ValueError as error:
                    fields['prompt']['document_error'] = str(error)
            records.append(dict(question=record['index'] + 1, group=record['group'] + 1,
                                type=kind, envelope_offset=record['offset'], fields=fields))
        except (ValueError, IndexError) as error:
            records.append(dict(question=record['index'] + 1, envelope_offset=record['offset'],
                                framing_error=str(error), fields=fields))
    summary = dict(sha256=hashlib.sha256(data).hexdigest(), file_bytes=len(data),
                   initial_pool_bytes=len(pool), reserved_block_bytes=reserved_size,
                   question_count=len(records),
                   field_status_counts=dict(Counter(f['status'] for r in records for f in r['fields'].values())),
                   pool_selector_counts=dict(Counter(f['pool_selector'] for r in records for f in r['fields'].values())),
                   richview_prompt_count=sum('richview_documents' in r['fields'].get('prompt', {}) for r in records),
                   complete_records=container['decoded_count'])
    offsets = [field['key_offset'] for record in records for field in record['fields'].values()
               if 'key_offset' in field]
    summary['minimum_referenced_pool_bytes'] = max(offsets, default=0) + 48
    return dict(summary=summary, records=records)


if __name__ == '__main__':
    result = audit(sys.argv[1])
    output = Path(__file__).parent / 'encryption-audit.json'
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['summary'], indent=2))
    print(json.dumps(result['records'][4:7], indent=2))
