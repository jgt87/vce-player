"""Bounded semantic decoding of recovered fields, traced from Android 2.6.9.

Sources: docs/ANDROID-QUESTION-SCHEMAS.md. No key acquisition or scoring occurs
here. A semantic failure does not change the underlying structural decode.
"""
import struct
from vce_reader import Reader, VCEError


class Fields(Reader):
    def integer(self):
        return struct.unpack('<i', self.take(4))[0]

    def count(self, minimum=1):
        value = self.integer()
        if not 0 <= value <= 10000 or value * minimum > len(self.data) - self.pos:
            raise VCEError('Invalid nested item count.')
        return value

    def string(self):
        try:
            return self.take(self.length()).decode('utf-8')
        except UnicodeError as error:
            raise VCEError('Invalid nested UTF-8 string.') from error

    def rect(self):
        return dict(zip(('left', 'top', 'right', 'bottom'), [self.integer() for _ in range(4)]))

    def done(self):
        if self.pos != len(self.data):
            raise VCEError(f'Unparsed nested bytes: {len(self.data) - self.pos}.')


def parse_question_schema(record):
    """Return meanings of already decrypted payloads; reject malformed extents."""
    if not record.get('decoded'):
        raise VCEError('Question fields are not fully decoded.')
    kind = record['type'] & 127
    primary, answer = Fields(record['prompt_data']), Fields(record['answer_data'])
    result = dict(version=1, type_code=kind)
    if kind in (0, 1):
        if not 0 <= record['choice_count'] <= 10000:
            raise VCEError('Invalid choice count.')
        result.update(kind='single_choice' if kind == 0 else 'multiple_choice',
                      allow_shuffle=bool(record['choice_flags'][0]),
                      document_source='prompt_data',
                      document_roles=['prompt'] + (['case_context'] if record['choice_flags'][2] else [])
                      + ['choice'] * record['choice_count'] + ['explanation'])
        # Android K1 maps option indexes to consecutive uppercase characters.
        code = bytes(answer.data).decode('utf-8')
        result['correct_option_indexes'] = [i for i in range(record['choice_count']) if chr(65+i) in code]
        return result
    if kind == 2:
        count = primary.count(21)
        answer_header = answer.integer()  # F10 discards it; do not infer a count.
        places = []
        for _ in range(count):
            rect, place_type = primary.rect(), primary.u8()
            if place_type not in (1, 2):
                raise VCEError('Unknown source/target place type.')
            places.append(dict(rect=rect, role='source' if place_type == 1 else 'target',
                               value=primary.integer(), answer_value=answer.integer()))
        result.update(kind='drag_and_drop', places=places, answer_header=answer_header,
                      document_source='image_data', document_roles=['prompt', 'explanation'],
                      image_source='image_aux_data', image_mode=record['image_flags'][1])
    elif kind == 3:
        # D10 deliberately skips the primary geometry blob and reads one answer rectangle.
        primary.take(len(primary.data))
        result.update(kind='point_and_shoot', answer_rect=answer.rect(),
                      document_source='image_data', document_roles=['prompt', 'explanation'],
                      image_source='image_aux_data')
    elif kind == 9:
        count, answer_count = primary.count(16), answer.count(1)
        if count != answer_count:
            raise VCEError('Hotspot rectangle and answer counts differ.')
        areas = [dict(rect=primary.rect(), correct=bool(answer.u8())) for _ in range(count)]
        result.update(kind='hotspot', areas=areas, document_source='image_data',
                      document_roles=['prompt', 'explanation'], image_source='image_aux_data')
    elif kind == 4:
        roots = []
        for index in range(primary.count(14)):
            roots.append(dict(label=primary.string(), icon=primary.integer(),
                              flag=bool(primary.u8()), value=primary.integer(), index=index))
        items = [primary.string() for _ in range(primary.count(5))]
        values = [answer.integer() for _ in range(answer.count(4))]
        result.update(kind='create_tree', roots=roots, items=items, answer_values=values,
                      document_source='tree_data', document_roles=['prompt', 'explanation'])
    elif kind == 5:
        order = [answer.integer() for _ in range(answer.count(4))]
        items = [primary.string() for _ in range(primary.count(5))]
        if any(i < 0 or i >= len(items) for i in order):
            raise VCEError('Reorder answer references an unknown item.')
        result.update(kind='reorder_list', items=items, correct_order=order,
                      document_source='tree_data', document_roles=['prompt', 'explanation'])
    elif kind == 7:
        count = answer.count(13)
        connectors = []
        for _ in range(primary.count(6)):
            label, mode = primary.string(), primary.u8()
            if mode > 4:
                raise VCEError('Unknown connector mode.')
            connectors.append(dict(label=label, mode=mode))
        boxes = [primary.string() for _ in range(primary.count(5))]
        relationships = []
        for _ in range(count):
            first, second, connector = [answer.integer() for _ in range(3)]
            forward = bool(answer.u8())
            if not (0 <= first < len(boxes) and 0 <= second < len(boxes)
                    and 0 <= connector < len(connectors)):
                raise VCEError('Connector relationship references an unknown item.')
            relationships.append(dict(source=first if forward else second,
                                      target=second if forward else first,
                                      connector=connector, forward=forward))
        positions = Fields(record['connection_data'][1])
        box_positions = [dict(x=positions.integer(), y=positions.integer()) for _ in boxes]
        relationship_positions = [dict(x=positions.integer(), y=positions.integer()) for _ in relationships]
        positions.done()
        result.update(kind='connect', connectors=connectors, boxes=boxes,
                      relationships=relationships, box_positions=box_positions,
                      relationship_positions=relationship_positions,
                      document_source='connection_data[0]', document_roles=['prompt', 'explanation'])
    elif kind == 8:
        # The primary blob contains two framed RichView documents, not geometry.
        primary.take(len(primary.data))
        answers = [answer.string() for _ in range(record['blank_count'])]
        flags = record['blank_flags']
        result.update(kind='fill_in_the_blank', accepted_answers=answers,
                      case_sensitive=bool(flags[0]), ignore_multiple_spaces=bool(flags[1]),
                      trim_user_response=bool(flags[2]), document_source='prompt_data',
                      document_roles=['prompt', 'explanation'])
    else:
        raise VCEError(f'Unsupported Android question type {kind}.')
    primary.done()
    answer.done()
    return result
