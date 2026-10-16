import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import apply_thinking_policy  # noqa: E402


class ThinkingPolicyTests(unittest.TestCase):
    def test_light_strips_thinking_params(self):
        p = {"messages": [], "reasoning_effort": "high", "thinking": {"type": "enabled"}}
        tag = apply_thinking_policy("light", p)
        self.assertEqual(tag, "thinking:strip")
        self.assertNotIn("reasoning_effort", p)
        self.assertNotIn("thinking", p)

    def test_light_without_thinking_params_is_noop(self):
        p = {"messages": []}
        self.assertEqual(apply_thinking_policy("light", p), "")

    def test_heavy_passes_client_params_untouched(self):
        p = {"messages": [], "reasoning_effort": "high"}
        self.assertEqual(apply_thinking_policy("heavy", p), "")
        self.assertEqual(p["reasoning_effort"], "high")

    def test_passthrough_never_touches_payload(self):
        p = {"messages": [], "thinking": {"type": "enabled"}}
        self.assertEqual(apply_thinking_policy("passthrough", p), "")
        self.assertIn("thinking", p)


if __name__ == "__main__":
    unittest.main()
