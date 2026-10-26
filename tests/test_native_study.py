import tempfile
import unittest
from pathlib import Path
from exam_engine import correct, score
from native_study import practice_exam
from vce_container import read_container
from test_vce_container import (fixture, document, plain_list_fixture, question,
                                 fill_question, reorder_question, connect_question,
                                 hotspot_question, point_question)


def container_from(raw):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'original.vce'
        path.write_bytes(raw)
        return read_container(path)


class NativeStudyTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'original.vce'
            path.write_bytes(fixture())
            self.container = read_container(path)

    def test_subset_scope_and_scoring_inputs(self):
        exam, digest = practice_exam(self.container, 'source-id')
        self.assertEqual(exam['source_count'], 2)
        self.assertEqual(exam['questions'][0]['answer'], [0])
        self.assertEqual(exam['questions'][0]['options'], ['First option', 'Second option'])
        self.assertTrue(exam['practice_only'])
        self.assertIn('subset', exam['scope_notice'])
        self.assertEqual(len(digest), 64)

    def test_incomplete_records_are_not_scorable(self):
        self.container['records'][0]['decoded'] = False
        exam, first_digest = practice_exam(self.container, 'source-id')
        self.assertEqual(len(exam['questions']), 1)
        self.container['records'][0]['decoded'] = True
        _, changed_digest = practice_exam(self.container, 'source-id')
        self.assertNotEqual(first_digest, changed_digest)

    def test_no_playable_questions_is_explicit(self):
        for record in self.container['records']:
            record['decoded'] = False
        with self.assertRaisesRegex(ValueError, 'No fully decoded'):
            practice_exam(self.container, 'source-id')

    def test_embedded_case_does_not_shift_option_mapping(self):
        record = self.container['records'][0]
        record['choice_flags'][2] = 1
        record['prompt_data'] = (document('Question text') + document('Case context')
            + document('First option') + document('Second option') + document('Why the first option works'))
        exam, _ = practice_exam(self.container, 'source-id')
        question = exam['questions'][0]
        self.assertIn('Case context', question['prompt'])
        self.assertEqual(question['options'], ['First option', 'Second option'])
        self.assertEqual(question['answer'], [0])
        self.assertIn('Why the first option works', question['explanation'])

    def test_unexpected_document_count_is_not_silently_scored(self):
        self.container['records'][0]['prompt_data'] += document('Unexpected document')
        exam, _ = practice_exam(self.container, 'source-id')
        self.assertEqual(len(exam['questions']), 1)


class FillInTheBlankTests(unittest.TestCase):
    def test_single_blank_is_promoted_and_scored_as_text(self):
        container = container_from(fixture(fill=True))
        self.assertEqual(container['decoded_count'], 2)
        exam, digest = practice_exam(container, 'source-id')
        self.assertEqual(len(exam['questions']), 2)
        blank = exam['questions'][1]
        self.assertEqual(blank['type'], 'text')
        self.assertEqual(blank['answer'], ['Paris'])
        self.assertIn('capital of France', blank['prompt'])
        self.assertIn('Stored answer: Paris', blank['explanation'])
        # Case-insensitive, whitespace-trimmed matching the engine performs.
        self.assertTrue(correct(blank, '  paris '))
        self.assertFalse(correct(blank, 'London'))
        self.assertEqual(score(exam, {'1': 'PARIS'})['sections']['Original section']['correct'], 1)
        self.assertEqual(len(digest), 64)

    def test_multiple_blanks_are_not_scored(self):
        # Two blanks cannot be graded by a single free-text response.
        container = container_from(plain_list_fixture(question(), fill_question(1, blank_count=2)))
        self.assertEqual(container['decoded_count'], 2)
        exam, _ = practice_exam(container, 'source-id')
        self.assertEqual([q['type'] for q in exam['questions']], ['choice'])

    def test_case_sensitive_blank_is_not_scored(self):
        # The engine casefolds, so case-sensitive matching is not promoted.
        container = container_from(plain_list_fixture(question(), fill_question(1, case_sensitive=True)))
        self.assertEqual(container['decoded_count'], 2)
        exam, _ = practice_exam(container, 'source-id')
        self.assertEqual([q['type'] for q in exam['questions']], ['choice'])


class ReorderTests(unittest.TestCase):
    def test_reorder_is_promoted_and_scored_as_order(self):
        container = container_from(plain_list_fixture(reorder_question(0)))
        self.assertEqual(container['decoded_count'], 1)
        exam, _ = practice_exam(container, 'source-id')
        q = exam['questions'][0]
        self.assertEqual(q['type'], 'order')
        self.assertEqual(q['items'], ['First step', 'Second step', 'Third step'])
        self.assertEqual(q['answer'], [2, 0, 1])
        self.assertIn('Put the steps in order', q['prompt'])
        self.assertTrue(correct(q, [2, 0, 1]))
        self.assertFalse(correct(q, [0, 1, 2]))
        self.assertEqual(score(exam, {'0': [2, 0, 1]})['percent'], 100)

    def test_duplicate_order_indexes_are_not_promoted(self):
        # A non-permutation order cannot be graded as a reordering.
        container = container_from(plain_list_fixture(question(), reorder_question(1, order=(0, 0, 1))))
        exam, _ = practice_exam(container, 'source-id')
        self.assertEqual([q['type'] for q in exam['questions']], ['choice'])


class ConnectTests(unittest.TestCase):
    def test_connect_is_promoted_and_scored_as_set(self):
        container = container_from(plain_list_fixture(connect_question(0)))
        self.assertEqual(container['decoded_count'], 1)
        exam, _ = practice_exam(container, 'source-id')
        q = exam['questions'][0]
        self.assertEqual(q['type'], 'connect')
        self.assertEqual(q['boxes'], ['Alpha', 'Beta'])
        self.assertEqual(q['connectors'], ['links to'])
        self.assertEqual(q['answer'], [[0, 1, 0]])
        # Scoring is order-independent and rejects spurious or missing links.
        self.assertTrue(correct(q, [[0, 1, 0]]))
        self.assertFalse(correct(q, []))
        self.assertFalse(correct(q, [[0, 1, 0], [1, 0, 0]]))
        self.assertEqual(score(exam, {'0': [[0, 1, 0]]})['percent'], 100)


class HotspotTests(unittest.TestCase):
    def test_hotspot_is_promoted_and_scored(self):
        container = container_from(plain_list_fixture(hotspot_question(0)))
        self.assertEqual(container['decoded_count'], 1)
        exam, _ = practice_exam(container, 'source-id')
        q = exam['questions'][0]
        self.assertEqual(q['type'], 'hotspot')
        self.assertEqual(q['areas'], [[10, 10, 50, 50], [60, 60, 90, 90]])
        self.assertEqual(q['answer'], [0])
        self.assertTrue(bytes(q['image']).startswith(b'\x89PNG'))
        self.assertIn('Click the correct area', q['prompt'])
        self.assertTrue(correct(q, [0]))
        self.assertFalse(correct(q, [0, 1]))
        self.assertFalse(correct(q, []))
        self.assertEqual(score(exam, {'0': [0]})['percent'], 100)

    def test_hotspot_without_renderable_image_is_not_promoted(self):
        container = container_from(plain_list_fixture(question(), hotspot_question(1)))
        container['records'][1]['image_aux_data'] = b'not an image'
        exam, _ = practice_exam(container, 'source-id')
        self.assertEqual([q['type'] for q in exam['questions']], ['choice'])


class PointTests(unittest.TestCase):
    def test_point_is_promoted_and_scored_inside_rect(self):
        container = container_from(plain_list_fixture(point_question(0)))
        self.assertEqual(container['decoded_count'], 1)
        exam, _ = practice_exam(container, 'source-id')
        q = exam['questions'][0]
        self.assertEqual(q['type'], 'point')
        self.assertEqual(q['rect'], [20, 30, 80, 90])
        self.assertTrue(bytes(q['image']).startswith(b'\x89PNG'))
        self.assertTrue(correct(q, [50, 60]))   # inside
        self.assertTrue(correct(q, [20, 30]))   # on the edge
        self.assertFalse(correct(q, [10, 10]))  # outside
        self.assertFalse(correct(q, None))
        self.assertEqual(score(exam, {'0': [50, 60]})['percent'], 100)
