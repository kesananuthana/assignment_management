import tempfile, unittest
from src.generator import build_dataset, validate
class GeneratorSmokeTest(unittest.TestCase):
    def test_small_dataset(self):
        with tempfile.TemporaryDirectory() as d:
            data, gt = build_dataset(20261022, 5, 30, 10, 60, d)
            checks = validate(data, gt)
            self.assertEqual(len(data["course"]), 5)
            self.assertEqual(len(data["learner"]), 30)
            self.assertEqual(len(data["assignment"]), 10)
            self.assertTrue(all(x["passed"] for x in checks), checks)
            self.assertGreaterEqual(len(gt), 3)
if __name__ == "__main__": unittest.main()
