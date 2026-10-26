import struct
import unittest
from question_schema import parse_question_schema
from vce_reader import VCEError
from test_vce_container import length


def ints(*values):
    return struct.pack('<' + 'i' * len(values), *values)


def text(value):
    raw = value.encode('utf-8')
    return length(len(raw)) + raw


def record(kind, primary=b'', answer=b'', **tail):
    return dict(decoded=True, type=kind, prompt_data=primary, answer_data=answer, **tail)


class QuestionSchemaTests(unittest.TestCase):
    def test_hotspot_signed_coordinates_and_flags(self):
        source = record(9, ints(2, -10, 2, 30, 40, 50, 60, 80, 90), ints(2) + b'\x01\x00')
        schema = parse_question_schema(source)
        self.assertEqual(schema['areas'][0]['rect']['left'], -10)
        self.assertEqual([a['correct'] for a in schema['areas']], [True, False])
        self.assertEqual(schema['document_source'], 'image_data')

    def test_geometry_mismatch_truncation_and_extra_bytes_rejected(self):
        valid = record(9, ints(1, 0, 0, 20, 30), ints(1) + b'\x01')
        for primary, answer in [(valid['prompt_data'][:-1], valid['answer_data']),
                                (valid['prompt_data'], ints(2) + b'\x01\x00'),
                                (valid['prompt_data'], valid['answer_data'] + b'\0')]:
            with self.assertRaises(VCEError):
                parse_question_schema(record(9, primary, answer))

    def test_source_target_and_correct_placement_values(self):
        primary = ints(1, 1, 2, 31, 42) + b'\x02' + ints(-1)
        schema = parse_question_schema(record(2, primary, ints(123, 7), image_flags=[0, 1]))
        self.assertEqual(schema['places'][0]['role'], 'target')
        self.assertEqual(schema['places'][0]['answer_value'], 7)
        self.assertEqual(schema['answer_header'], 123)

    def test_reorder_rejects_unknown_index(self):
        primary = ints(2) + text('First') + text('Second')
        parsed = parse_question_schema(record(5, primary, ints(2, 1, 0)))
        self.assertEqual(parsed['correct_order'], [1, 0])
        with self.assertRaises(VCEError):
            parse_question_schema(record(5, primary, ints(1, 2)))

    def test_tree_variable_strings_and_answer_values(self):
        primary = ints(1) + text('Root') + ints(2) + b'\x01' + ints(-1)
        primary += ints(1) + text('Child')
        result = parse_question_schema(record(4, primary, ints(1, 0)))
        self.assertEqual(result['roots'][0]['label'], 'Root')
        self.assertEqual(result['items'], ['Child'])
        self.assertEqual(result['answer_values'], [0])

    def test_connect_direction_and_positions(self):
        primary = ints(1) + text('Arrow') + b'\x01' + ints(2) + text('A') + text('B')
        answer = ints(1, 0, 1, 0) + b'\x00'
        result = parse_question_schema(record(7, primary, answer,
            connection_data=[b'', ints(10, 20, 30, 40, 50, 60)]))
        self.assertEqual(result['relationships'][0]['source'], 1)
        self.assertEqual(result['relationships'][0]['target'], 0)
        self.assertEqual(result['box_positions'][1], dict(x=30, y=40))
        with self.assertRaises(VCEError):
            parse_question_schema(record(7, primary, answer, connection_data=[b'', ints(1)]))

    def test_fill_answers_and_normalization_flags(self):
        result = parse_question_schema(record(8, b'documents', text('Blue') + text('Azure'),
            blank_count=2, blank_flags=[1, 0, 1]))
        self.assertEqual(result['accepted_answers'], ['Blue', 'Azure'])
        self.assertTrue(result['case_sensitive'])
        self.assertFalse(result['ignore_multiple_spaces'])
        self.assertTrue(result['trim_user_response'])

    def test_choice_case_context_and_option_indexes(self):
        result = parse_question_schema(record(1, b'', b'AC', choice_count=3, choice_flags=[1, 0, 1]))
        self.assertEqual(result['correct_option_indexes'], [0, 2])
        self.assertEqual(result['document_roles'], ['prompt', 'case_context', 'choice', 'choice', 'choice', 'explanation'])

    def test_unavailable_fields_and_hostile_count_rejected(self):
        with self.assertRaises(VCEError):
            parse_question_schema(dict(decoded=False))
        with self.assertRaises(VCEError):
            parse_question_schema(record(9, ints(100000000), ints(0)))

    def test_point_and_shoot_uses_answer_rect(self):
        result = parse_question_schema(record(3, b'ignored primary', ints(1, 2, 3, 4)))
        self.assertEqual(result['answer_rect'], dict(left=1, top=2, right=3, bottom=4))


if __name__ == '__main__':
    unittest.main()
