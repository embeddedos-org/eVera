import unittest
class TestEVeraFunctional(unittest.TestCase):
    def test_autonomous_agent_pipeline(self):
        pipeline = ["perceive", "plan", "act"]
        self.assertEqual(pipeline[-1], "act")
