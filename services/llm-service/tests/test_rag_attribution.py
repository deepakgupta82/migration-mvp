import unittest
from app.routers.llm import RAGSynthesisResponse

class TestRAGAttributionScaffold(unittest.TestCase):
    def test_attribution_stats_shape(self):
        # Minimal shape test (does not run full pipeline here)
        resp = RAGSynthesisResponse(
            project_id="p1", question="q", answer="a", citations=[], used_kinds=["raw_chunks"],
            retrieval_stats={}, model="m", timestamp="now", attribution_stats={"avg_overlap":0.0,"strong":0,"partial":0,"weak":0,"hallucination_ratio":0.0}
        )
        self.assertIn("avg_overlap", resp.attribution_stats)
        self.assertIn("hallucination_ratio", resp.attribution_stats)

if __name__ == '__main__':
    unittest.main()
