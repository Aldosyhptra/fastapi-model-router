import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routing import TurnCache, content_to_text, decide  # noqa: E402


def msgs(*texts, system="You are a coding agent."):
    out = [{"role": "system", "content": system}]
    for t in texts:
        out.append({"role": "user", "content": t})
    return out


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.cache = TurnCache()

    def test_simple_task_is_light(self):
        d = decide(msgs("tolong rename variabel x jadi total"), True, self.cache)
        self.assertEqual(d.tier, "light")

    def test_architecture_is_heavy(self):
        d = decide(msgs("Rancang arsitektur modul pembayaran dengan database migration"), True, self.cache)
        self.assertEqual(d.tier, "heavy")

    def test_stack_trace_with_debug_is_heavy(self):
        text = (
            "debug kenapa ini error\n"
            "Traceback (most recent call last):\n"
            '  File "app/main.py", line 10, in <module>\n'
            "ValueError: x"
        )
        d = decide(msgs(text), True, self.cache)
        self.assertEqual(d.tier, "heavy")

    def test_auxiliary_title_is_light_without_tools(self):
        d = decide(msgs("Generate a short title for this conversation"), False, self.cache)
        self.assertEqual(d.tier, "light")
        self.assertIn("bantu", d.reason)

    def test_many_files_and_long_text_is_heavy(self):
        text = "ubah a.py b.ts c.sql d.json " + ("detail " * 400)
        d = decide(msgs(text), True, self.cache)
        self.assertEqual(d.tier, "heavy")

    def test_sticky_within_same_user_turn(self):
        first = decide(msgs("Rancang arsitektur sistem antrian"), True, self.cache)
        self.assertEqual(first.tier, "heavy")
        # agent looping: ada pesan assistant/tool tambahan, pesan user terakhir sama
        looping = msgs("Rancang arsitektur sistem antrian") + [
            {"role": "assistant", "content": "membaca file"},
            {"role": "tool", "content": "ok"},
        ]
        second = decide(looping, True, self.cache)
        self.assertEqual(second.tier, "heavy")
        self.assertTrue(second.cached)

    def test_new_user_turn_is_reevaluated(self):
        decide(msgs("Rancang arsitektur sistem antrian"), True, self.cache)
        d = decide(msgs("Rancang arsitektur sistem antrian", "ganti nama variabel jadi total"), True, self.cache)
        self.assertFalse(d.cached)
        self.assertEqual(d.tier, "light")

    def test_tool_results_do_not_change_decision(self):
        # hasil tool pendek tidak boleh dianggap "tugas ringan"
        base = msgs("Rancang arsitektur sistem antrian")
        d1 = decide(base, True, self.cache)
        with_tool = base + [{"role": "tool", "content": "ok"}]
        d2 = decide(with_tool, True, TurnCache())
        self.assertEqual(d1.tier, d2.tier)

    def test_multimodal_content_is_read(self):
        parts = [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {"url": "x"}}]
        self.assertEqual(content_to_text(parts), "hello")


def assistant_with_tool(name: str, args: str):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "c1", "type": "function",
                        "function": {"name": name, "arguments": args}}],
    }


class UpgradeTests(unittest.TestCase):
    """Sinyal kerja agen boleh meng-upgrade tier di tengah giliran (satu arah)."""

    def setUp(self):
        self.cache = TurnCache()

    def test_light_turn_upgrades_when_agent_edits_source(self):
        base = msgs("ubah warna tombol jadi biru")
        first = decide(base, True, self.cache)
        self.assertEqual(first.tier, "light")
        looping = base + [
            assistant_with_tool("write_file", '{"path":"page.tsx"}'),
            {"role": "tool", "content": "ok"},
        ]
        second = decide(looping, True, self.cache)
        # satu edit tunggal tidak cukup untuk upgrade (kebijakan hemat biaya)
        self.assertEqual(second.tier, "light")
        self.assertNotIn("upgrade", second.reason)
        # edit setelah loop panjang (>= 6 pesan tool) baru memicu upgrade
        for i in range(6):
            looping += [assistant_with_tool("search_files", "{}"), {"role": "tool", "content": "ok"}]
        third = decide(looping, True, self.cache)
        self.assertEqual(third.tier, "heavy")
        self.assertIn("upgrade", third.reason)

    def test_heavy_never_downgrades(self):
        base = msgs("Rancang arsitektur sistem antrian")
        decide(base, True, self.cache)
        looping = base + [
            assistant_with_tool("read_file", '{"path":"app.py"}'),
            {"role": "tool", "content": "isi"},
        ]
        d = decide(looping, True, self.cache)
        self.assertEqual(d.tier, "heavy")
        self.assertTrue(d.cached)

    def test_pure_chat_stays_light(self):
        base = msgs("rename variabel x jadi total")
        looping = base + [{"role": "assistant", "content": f"langkah {i}"} for i in range(5)]
        d = decide(looping, True, self.cache)
        self.assertEqual(d.tier, "light")


if __name__ == "__main__":
    unittest.main()
