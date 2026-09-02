import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _candidate_commitment_annotated_benchmark as benchmark


class CandidateCommitmentAnnotatedBenchmarkTests(unittest.TestCase):
    def test_fixture_ids_are_unique_and_sources_are_recorded(self):
        ids = [fixture["id"] for fixture in benchmark.FIXTURES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(fixture.get("source") for fixture in benchmark.FIXTURES))

    def test_current_candidate_boundary_passes_annotated_benchmark(self):
        rows = benchmark.run_benchmark()
        failed = [row["id"] for row in rows if not row["passed"]]
        self.assertEqual([], failed)


if __name__ == "__main__":
    unittest.main()
