"""Adapt fully decoded, text-renderable records to a scoped practice session.

Only question types the scoring engine can grade faithfully from recovered data
are promoted:
- single/multiple textual choice (types 0/1),
- single-blank, case-insensitive fill-in-the-blank (type 8),
- reorder-list (type 5) and connect (type 7) — text-only, with scoring
  semantics established in docs/ANDROID-QUESTION-SCHEMAS.md,
- point-and-shoot (type 3) and hotspot (type 9) — image-coordinate, promoted
  only when a Tk-renderable PNG can be recovered from the image field; rects are
  graded in image-pixel space, so native-size rendering makes clicks map 1:1.

Deliberately not promoted (decoded structurally and shown in the native view,
but not graded here): drag-and-drop (type 2) and tree (type 4), whose
placement/hierarchy-to-answer mapping is not established — grading them would
require a guessed model.

No key acquisition occurs; undecoded records are skipped.
"""
import hashlib
import re
from richview import parse_nested_documents, parse_richview, _png_valid
from question_schema import parse_question_schema

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _extract_png(raw):
    """Recover a Tk-renderable PNG from an image field, or None if not present.

    image_aux_data is documented as 'the image'; its exact wrapping is not
    verified here, so this accepts either raw PNG bytes or a RichView document
    carrying exactly one PNG, validates the PNG, and otherwise declines. JPEG is
    not accepted because the player renders PNG only (no PIL dependency).
    """
    raw = bytes(raw)
    if raw.startswith(PNG_SIGNATURE):
        return raw if _png_valid(raw) else None
    try:
        document = parse_richview(raw)
    except ValueError:
        return None
    if document.warnings or len(document.images) != 1:
        return None
    image = document.images[0]
    return image if _png_valid(image) else None


def _case_study_prompt(container, record, prompt):
    """Prefix a case-study child's context; return None if that context is unusable."""
    child = container['groups'][record['group']]['children'][record['child']]
    if child['kind'] != 1:
        return prompt
    if child.get('body') is None:
        return None
    context = parse_richview(child['body'])
    if context.warnings or context.images:
        return None
    if context.text:
        return 'Case study\n' + context.text + '\n\nQuestion\n' + prompt
    return prompt


def _explanation(document, stored):
    """Render the 'Stored answer' line, appending a clean explanation document."""
    tail = ('\n' + document.text if document is not None and not document.warnings
            and not document.images and document.text else '')
    return 'Stored answer: ' + stored + tail


def _prompt_and_explanation(container, record, raw):
    """Parse a 2-document field into (prompt_text, explanation_doc); None to skip."""
    documents = parse_nested_documents(raw)
    if len(documents) != 2:
        return None
    prompt_doc = documents[0]
    if prompt_doc.warnings or prompt_doc.images or not prompt_doc.text:
        return None
    prompt = _case_study_prompt(container, record, prompt_doc.text)
    if prompt is None:
        return None
    return prompt, documents[1]


def _build_choice(record, container):
    """Promote a textual single/multiple-choice record (types 0/1)."""
    documents = parse_nested_documents(record['prompt_data'])
    count = record['choice_count']
    schema = parse_question_schema(record)
    if not 2 <= count <= 26 or len(documents) != len(schema['document_roles']):
        return None
    choice_start = 2 if record['choice_flags'][2] else 1
    used = [documents[0]] + list(documents[choice_start:choice_start + count])
    context_docs = [documents[1]] if choice_start == 2 else []
    if any(d.warnings or d.images for d in context_docs):
        return None
    if any(d.warnings or d.images for d in used) or not all(d.text for d in used):
        return None
    code = record['answer_data'].decode('ascii').strip().upper()
    if not re.fullmatch(r'[A-Z]+(?:[ ,;]+[A-Z]+)*', code):
        return None
    answers = sorted({ord(letter) - 65 for letter in code if letter.isalpha()})
    if not answers or max(answers) >= count:
        return None
    if record['type'] & 127 == 0 and len(answers) != 1:
        return None
    prompt = used[0].text
    if context_docs and context_docs[0].text:
        prompt = 'Case study\n' + context_docs[0].text + '\n\nQuestion\n' + prompt
    prompt = _case_study_prompt(container, record, prompt)
    if prompt is None:
        return None
    group = container['groups'][record['group']]
    return dict(type='choice', prompt=prompt, options=[d.text for d in used[1:]],
                answer=answers, section=group['title'], source_index=record['index'],
                explanation=_explanation(documents[-1], code))


def _build_fill_in_blank(record, container):
    """Promote a single-blank, case-insensitive fill-in-the-blank record (type 8).

    The engine scores one free-text response against accepted strings, so only a
    single blank can be graded, and only when the stored matching is
    case-insensitive (the engine always casefolds). Multi-blank or case-sensitive
    blanks are left unscored rather than graded with the wrong semantics.
    """
    schema = parse_question_schema(record)
    if record['blank_count'] != 1 or schema['case_sensitive']:
        return None
    accepted = schema['accepted_answers'][0]
    if not accepted.strip():
        return None
    documents = parse_nested_documents(record['prompt_data'])
    if len(documents) != len(schema['document_roles']):  # ['prompt', 'explanation']
        return None
    prompt_doc = documents[0]
    if prompt_doc.warnings or prompt_doc.images or not prompt_doc.text:
        return None
    prompt = _case_study_prompt(container, record, prompt_doc.text)
    if prompt is None:
        return None
    group = container['groups'][record['group']]
    return dict(type='text', prompt=prompt, answer=[accepted],
                section=group['title'], source_index=record['index'],
                explanation=_explanation(documents[-1], accepted))


def _build_reorder(record, container):
    """Promote a reorder-list record (type 5): arrange items into the stored order."""
    schema = parse_question_schema(record)
    items, order = schema['items'], schema['correct_order']
    if len(items) < 2 or not all(isinstance(s, str) and s.strip() for s in items):
        return None
    # Only a clean permutation is scorable as a reordering; the static loader
    # permits duplicate indexes, which cannot be graded as an ordering.
    if sorted(order) != list(range(len(items))):
        return None
    pair = _prompt_and_explanation(container, record, record['tree_data'])
    if pair is None:
        return None
    prompt, explanation_doc = pair
    group = container['groups'][record['group']]
    stored = ' → '.join(items[i] for i in order)
    return dict(type='order', prompt=prompt, items=items, answer=order,
                section=group['title'], source_index=record['index'],
                explanation=_explanation(explanation_doc, stored))


def _build_connect(record, container):
    """Promote a connect record (type 7): reproduce the stored box relationships."""
    schema = parse_question_schema(record)
    boxes = schema['boxes']
    connectors = [c['label'] for c in schema['connectors']]
    if len(boxes) < 2 or not all(isinstance(b, str) and b.strip() for b in boxes):
        return None
    if not connectors or not all(isinstance(c, str) and c.strip() for c in connectors):
        return None
    answer = sorted({(r['source'], r['target'], r['connector']) for r in schema['relationships']})
    if not answer:
        return None
    pair = _prompt_and_explanation(container, record, record['connection_data'][0])
    if pair is None:
        return None
    prompt, explanation_doc = pair
    group = container['groups'][record['group']]
    stored = '; '.join(f'{boxes[s]} —[{connectors[c]}]→ {boxes[t]}' for s, t, c in answer)
    return dict(type='connect', prompt=prompt, boxes=boxes, connectors=connectors,
                answer=[list(link) for link in answer], section=group['title'],
                source_index=record['index'], explanation=_explanation(explanation_doc, stored))


def _build_hotspot(record, container):
    """Promote a hotspot record (type 9): select the correct image regions."""
    schema = parse_question_schema(record)
    areas = schema['areas']
    answer = sorted(i for i, area in enumerate(areas) if area['correct'])
    if not areas or not answer:
        return None
    image = _extract_png(record['image_aux_data'])
    if image is None:
        return None
    pair = _prompt_and_explanation(container, record, record['image_data'])
    if pair is None:
        return None
    prompt, explanation_doc = pair
    group = container['groups'][record['group']]
    rects = [[a['rect']['left'], a['rect']['top'], a['rect']['right'], a['rect']['bottom']] for a in areas]
    stored = 'Areas ' + ', '.join(str(i + 1) for i in answer)
    return dict(type='hotspot', prompt=prompt, image=image, areas=rects, answer=answer,
                section=group['title'], source_index=record['index'],
                explanation=_explanation(explanation_doc, stored))


def _build_point(record, container):
    """Promote a point-and-shoot record (type 3): click inside the answer rect."""
    schema = parse_question_schema(record)
    rect = schema['answer_rect']
    box = [rect['left'], rect['top'], rect['right'], rect['bottom']]
    image = _extract_png(record['image_aux_data'])
    if image is None:
        return None
    pair = _prompt_and_explanation(container, record, record['image_data'])
    if pair is None:
        return None
    prompt, explanation_doc = pair
    group = container['groups'][record['group']]
    stored = f'a point within ({box[0]}, {box[1]})–({box[2]}, {box[3]})'
    return dict(type='point', prompt=prompt, image=image, rect=box,
                section=group['title'], source_index=record['index'],
                explanation=_explanation(explanation_doc, stored))


# Record type (type & 127) → builder for the scorable, text-renderable subset.
BUILDERS = {0: _build_choice, 1: _build_choice, 3: _build_point, 5: _build_reorder,
            7: _build_connect, 8: _build_fill_in_blank, 9: _build_hotspot}


def practice_exam(container, source_digest):
    questions = []
    for record in container['records']:
        if not record['decoded']:
            continue
        builder = BUILDERS.get(record.get('type', 255) & 127)
        if builder is None:
            continue
        try:
            question = builder(record, container)
        except (ValueError, UnicodeError, KeyError):
            continue
        if question is not None:
            questions.append(question)
    if not questions:
        raise ValueError('No fully decoded textual questions are available for practice.')
    total = len(container['records'])
    scope = f'Decoded subset: {len(questions)} of {total} source records. Scoring applies only to this subset.'
    exam = dict(title=container['metadata']['title'] + ' — decoded subset practice',
                exam_number=container['metadata']['exam_number'], questions=questions,
                passing_score=70, time_limit_minutes=30, practice_only=True,
                source_count=total, scope_notice=scope)
    # Different subset/rendering versions cannot accidentally resume one another.
    indexes = ','.join(str(q['source_index']) for q in questions)
    digest = hashlib.sha256((source_digest + ':native-practice-v3:' + indexes).encode()).hexdigest()
    return exam, digest
