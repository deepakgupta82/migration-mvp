import unittest
from app.core.evidence_utils import normalize_text, evidence_hash, dedupe_evidences

class TestEvidenceUtils(unittest.TestCase):
    def test_normalize_and_hash_stability(self):
        t1 = "Hello   World"  # extra spaces
        t2 = "hello world"    # already normalized
        self.assertEqual(normalize_text(t1), normalize_text(t2))
        self.assertEqual(evidence_hash(t1), evidence_hash(t2))

    def test_dedupe(self):
        evidences = [
            {"content": "Alpha Beta", "weight": 1.0},
            {"content": "Alpha   Beta", "weight": 2.0},  # duplicate after normalization
            {"content": "Gamma", "weight": 1.0},
        ]
        deduped, groups = dedupe_evidences(evidences)
        # Expect 2 groups
        self.assertEqual(len(deduped), 2)
        # Alpha Beta group weight should sum (first kept weight + second added)
        ab = next(d for d in deduped if d['content'].lower().startswith('alpha'))
        self.assertAlmostEqual(ab['weight'], 3.0, places=4)
        # Dup count recorded
        abm = next(g for g in groups if g['hash'] == ab['hash'])
        self.assertEqual(abm['dup_count'], 2)

if __name__ == '__main__':
    unittest.main()
