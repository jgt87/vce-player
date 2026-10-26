"""Offline VCE decoding to JSON, recovered documents, and binary field assets.

Usage: python vce_decode.py temp/*.vce --output decoded
Inputs are never modified. No vendor program, license service, or GUI is used.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from glob import glob

from vce_container import read_container
from vce_reader import Reader
from richview import parse_nested_documents, parse_richview
from analysis.compatibility.audit_encryption import audit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode_file(source, output):
    source = Path(source)
    container = read_container(source)
    data = source.read_bytes()
    digest = sha(data)
    name = re.sub(r'[^A-Za-z0-9_-]+', '-', source.stem)[:64].strip('-') or 'exam'
    destination = Path(output) / (name + '-' + digest[:12])
    destination.mkdir(parents=True, exist_ok=True)
    assets = destination / 'assets'
    assets.mkdir(exist_ok=True)

    def asset(raw, label, suffix='.bin'):
        name = label + '-' + sha(raw)[:12] + suffix
        path = assets / name
        path.write_bytes(raw)
        return dict(path='assets/' + name, bytes=len(raw), sha256=sha(raw))

    def convert(value, label):
        if isinstance(value, bytes):
            return asset(value, label)
        if isinstance(value, dict):
            return {str(k): convert(v, label + '-' + str(k)) for k,v in value.items()}
        if isinstance(value, (list,tuple)):
            return [convert(v, label + '-' + str(i)) for i,v in enumerate(value)]
        return value

    def documents(raw, label, nested):
        try:
            docs = parse_nested_documents(raw) if nested else [parse_richview(raw)]
            return [dict(text=doc.text, warnings=list(doc.warnings), links=list(doc.links),
                         images=[asset(im,label + f'-doc-{i}-image-{j}',
                                       '.jpg' if im.startswith(b'\xff\xd8') else '.png')
                                 for j,im in enumerate(doc.images)])
                    for i,doc in enumerate(docs)]
        except ValueError as error:
            return dict(unparsed_document=str(error))

    result = convert(container, 'container')
    result['source'] = dict(name=source.name, sha256=digest, bytes=len(data))
    result['description_documents'] = documents(container['description'],'description',False)
    result['all_records_structurally_decoded'] = container['decoded_count'] == len(container['records'])
    result['limitations'] = [
        'Decoded records are structural results; full rendering and scoring are separate.',
        'Unavailable protected fields remain ciphertext; this export does not invent their contents.',
        'Format-63 support is validated for the supplied plain-reference sample; nested references are explicitly unsupported.',
        'The trailing area is preserved without assigning an unverified checksum or other meaning.']
    framing = audit(source)
    for record, exported, framed in zip(container['records'],result['records'],framing['records']):
        exported['field_framing'] = framed.get('fields',{})
        if 'prompt_data' in record:
            exported['prompt_documents'] = documents(record['prompt_data'],f'question-{record["index"]+1}',True)
        schema = record.get('question_schema')
        if schema:
            source_field = schema['document_source']
            raw = (record['connection_data'][0] if source_field == 'connection_data[0]'
                   else record[source_field])
            content = documents(raw, f'question-{record["index"]+1}-content', True)
            exported['content_documents'] = content
            roles = schema['document_roles']
            if isinstance(content, list) and len(content) == len(roles):
                for document, role in zip(content, roles):
                    document['role'] = role
                exported['content_document_status'] = 'roles_validated'
            else:
                exported['content_document_status'] = 'unvalidated_document_count_or_layout'
        if 'answer_data' in record:
            try:
                answer = record['answer_data'].decode('ascii')
                if answer.isprintable(): exported['stored_answer_text'] = answer
            except UnicodeError:
                pass
    for group, exported in zip(container['groups'],result['groups']):
        for child, target in zip(group['children'],exported['children']):
            if child.get('body') is not None:
                target['body_documents'] = documents(child['body'],'case-study',False)
    reader = Reader(data,8)
    initial_start = reader.pos+5
    initial_length = reader.length()
    initial_pool = reader.take(initial_length)
    key_length_offset = reader.pos
    key_length = reader.length()
    key_start = reader.pos
    encoded_key = reader.take(key_length)
    result['file_regions'] = dict(header=dict(offset=0,bytes=4),
        container_value=dict(offset=4,bytes=4,value=container['metadata']['container_value']),
        initial_pool=dict(offset=initial_start,bytes=initial_length,sha256=sha(initial_pool)),
        encoded_key=dict(length_header_offset=key_length_offset,offset=key_start,bytes=key_length,sha256=sha(encoded_key)),
        metadata=dict(offset=container['metadata']['metadata_offset'],end=container['metadata']['metadata_end']),
        trailing=dict(offset=container['parsed_end'],**asset(data[container['parsed_end']:],'trailing')))
    if container['trailing_bytes'] == 12:
        reported_size=struct.unpack_from('<I',data,container['parsed_end'])[0]
        result['file_regions']['trailing'].update(reported_file_bytes=reported_size,
            reported_size_matches_actual=reported_size==len(data),remaining_opaque_bytes=8)
    result['audit_summary'] = framing['summary']
    json_path = destination/'exam.json'
    json_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    text = [container['metadata']['title'],
            f'Structurally decoded records: {container["decoded_count"]}/{len(container["records"])}', '']
    for record in result['records']:
        text.append(f'Question {record["index"]+1} — ' + ('decoded' if record['decoded'] else 'unavailable'))
        if not record['decoded']: text.append(record.get('error','Unparsed record'))
        docs = record.get('prompt_documents',[])
        if isinstance(docs,list):
            for i,doc in enumerate(docs):
                text.append(f'Document {i+1}:\n' + doc['text'])
                if doc['warnings']: text.append('Rendering warnings: ' + '; '.join(doc['warnings']))
                if doc['images']: text.append(f'Images: {len(doc["images"])} (see assets and exam.json)')
                if doc['links']: text.append('Links: ' + ', '.join(doc['links']))
        if 'stored_answer_text' in record: text.append('Stored answer: ' + record['stored_answer_text'])
        text.append('')
    (destination/'questions.txt').write_text('\n'.join(text),encoding='utf-8')
    return dict(source=source.name,format=container['metadata']['format'],
                records=len(container['records']),decoded_records=container['decoded_count'],
                trailing_bytes=container['trailing_bytes'],export=str(json_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+')
    parser.add_argument('--output',default='decoded')
    args=parser.parse_args()
    paths=[]
    for supplied in args.files:
        expanded=glob(supplied)
        paths.extend(expanded or [supplied])
    reports=[]
    failed=False
    for path in dict.fromkeys(paths):
        try:
            report=decode_file(path,args.output)
        except (ValueError,OSError,KeyError) as error:
            report=dict(source=path,error=str(error)); failed=True
        reports.append(report)
        print(json.dumps(report,ensure_ascii=True))
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    (output/'index.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    lines=['# Offline VCE decoded files','',
        'These exports preserve recovered fields and explicitly label unavailable content. Rendering warnings remain in JSON and text.',
        '', '| Source | Format | Structurally decoded records | Exports |', '|---|---:|---:|---|']
    for report in reports:
        if 'error' in report:
            lines.append(f'| {Path(report["source"]).name} | — | Failed | {report["error"]} |')
        else:
            directory=Path(report['export']).parent.name
            lines.append(f'| {report["source"]} | {report["format"]} | {report["decoded_records"]}/{report["records"]} | '
                         f'[Text]({directory}/questions.txt), [JSON]({directory}/exam.json) |')
    (output/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return int(failed)


if __name__=='__main__':
    raise SystemExit(main())
