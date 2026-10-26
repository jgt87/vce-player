import json
import tempfile
import unittest
from pathlib import Path
from exam_engine import Store, load_exam, score, correct


def load_json_exam(exam):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'exam.json'
        path.write_text(json.dumps(exam), encoding='utf-8')
        return load_exam(path)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.exam, self.digest = load_exam(Path(__file__).resolve().parents[1] / 'examples/network-basics.json')

    def test_multi_answer_requires_exact_set(self):
        q = self.exam['questions'][1]
        self.assertTrue(correct(q, [1, 0]))
        self.assertFalse(correct(q, [0]))
        self.assertFalse(correct(q, [0, 1, 2]))

    def test_score_and_unanswered(self):
        result = score(self.exam, {'0': [0], '1': [1, 0], '2': ' 127.0.0.1 '})
        self.assertEqual(result['percent'], 75)
        self.assertEqual(result['incomplete'], 1)
        self.assertTrue(result['passed'])
        self.assertEqual(score(self.exam, {})['percent'], 0)

    def test_persistence_and_finish_atomic_state(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'test.db'
            store = Store(db)
            state = dict(index=1, answers={'0': [0]}, marked=[1], remaining=19.5, practice=False)
            store.save(self.digest, state)
            store.db.close()
            store = Store(db)
            self.assertEqual(store.resume(self.digest), state)
            store.finish(self.digest, self.exam['title'], score(self.exam, state['answers']))
            self.assertIsNone(store.resume(self.digest))
            self.assertEqual(store.db.execute('SELECT count(*) FROM history').fetchone()[0], 1)
            store.db.close()

    def test_order_type_scores_exact_sequence(self):
        exam = dict(title='Order', questions=[dict(type='order', prompt='Sort',
                    items=['a', 'b', 'c'], answer=[2, 0, 1])])
        loaded, _ = load_json_exam(exam)
        q = loaded['questions'][0]
        self.assertTrue(correct(q, [2, 0, 1]))
        self.assertFalse(correct(q, [0, 2, 1]))
        self.assertFalse(correct(q, None))

    def test_order_requires_permutation(self):
        for bad in ([0, 0, 1], [0, 1], [0, 1, 3]):
            with self.assertRaises(ValueError):
                load_json_exam(dict(title='Order', questions=[dict(type='order',
                    prompt='Sort', items=['a', 'b', 'c'], answer=bad)]))

    def test_connect_type_scores_as_unordered_set(self):
        exam = dict(title='Connect', questions=[dict(type='connect', prompt='Link',
                    boxes=['A', 'B', 'C'], connectors=['to'], answer=[[0, 1, 0], [1, 2, 0]])])
        loaded, _ = load_json_exam(exam)
        q = loaded['questions'][0]
        self.assertTrue(correct(q, [[1, 2, 0], [0, 1, 0]]))
        self.assertFalse(correct(q, [[0, 1, 0]]))
        self.assertFalse(correct(q, [[0, 1, 0], [1, 2, 0], [2, 0, 0]]))

    def test_connect_rejects_out_of_range_indexes(self):
        with self.assertRaises(ValueError):
            load_json_exam(dict(title='Connect', questions=[dict(type='connect', prompt='Link',
                boxes=['A', 'B'], connectors=['to'], answer=[[0, 2, 0]])]))

    def test_hotspot_scores_as_region_set(self):
        q = dict(type='hotspot', prompt='Pick', areas=[[0, 0, 10, 10], [20, 20, 30, 30]], answer=[0])
        self.assertTrue(correct(q, [0]))
        self.assertFalse(correct(q, [0, 1]))
        self.assertFalse(correct(q, []))

    def test_point_scores_inside_normalized_rect(self):
        q = dict(type='point', prompt='Click', rect=[80, 90, 20, 30])  # reversed corners
        self.assertTrue(correct(q, [50, 60]))
        self.assertFalse(correct(q, [0, 0]))
        self.assertFalse(correct(q, [50]))

    def test_vce_is_not_misrepresented_as_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sample.vce'
            path.write_bytes(bytes([0x85, 0xa8, 3, 1]))
            with self.assertRaisesRegex(ValueError, 'framing'):
                load_exam(path)


if __name__ == '__main__':
    unittest.main()
