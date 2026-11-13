import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "boss-review"
NOW = "2026-11-10T12:00:00+00:00"
CUTOFF = "2026-10-11T12:00:00+00:00"
RECENT = "2026-11-01T00:00:00Z"


def codex(ts, role, value):
    return {"timestamp": ts, "type": "response_item", "payload": {
        "type": "message", "role": role,
        "content": [{"type": "input_text" if role == "user" else "output_text", "text": value}],
    }}


def claude(ts, role, value, **extra):
    return {"timestamp": ts, "type": role, "message": {"role": role, "content": value}, **extra}


class InstalledSkill(unittest.TestCase):
    def collect(self, provider, records):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source"
            source.mkdir()
            log = source / "log.jsonl"
            log.write_text("\n".join(map(json.dumps, records)) + "\n{unclosed")
            target = Path(root) / "history.jsonl"
            result = subprocess.run([sys.executable, str(SKILL / "scripts/collect_history.py"),
                                     "--provider", provider, "--source", str(source),
                                     "--now", NOW, "--output", str(target)],
                                    check=True, capture_output=True, text=True)
            self.assertNotIn("给我", result.stdout)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            return [json.loads(line) for line in target.read_text().splitlines()]

    def test_codex_window_roles_and_duplicate_event(self):
        session, = self.collect("codex", [
            codex("2026-10-11T11:59:59Z", "user", "旧消息"),
            codex(CUTOFF, "user", "给我一个提纲"),
            {"timestamp": CUTOFF, "type": "event_msg", "payload": {"type": "user_message", "message": "给我一个提纲"}},
            codex(RECENT, "user", "<environment_context>injected</environment_context>"),
            codex(RECENT, "assistant", "已交付提纲"),
            codex(RECENT, "developer", "开发指令"),
            codex("2026-11-10T12:00:01Z", "user", "未来消息"),
        ])
        self.assertEqual([(turn["role"], turn["text"]) for turn in session["messages"]],
                         [("user", "给我一个提纲"), ("assistant", "已交付提纲")])

    def test_codex_retains_unique_event_turns_in_mixed_logs(self):
        session, = self.collect("codex", [
            codex(CUTOFF, "user", "同一句话"),
            {"timestamp": CUTOFF, "type": "event_msg", "payload": {"type": "user_message", "message": "同一句话"}},
            {"timestamp": RECENT, "type": "event_msg", "payload": {"type": "user_message", "message": "同一句话"}},
            {"timestamp": RECENT, "type": "event_msg", "payload": {"type": [], "message": "损坏数据"}},
        ])
        self.assertEqual([turn["text"] for turn in session["messages"]], ["同一句话", "同一句话"])

    def test_claude_excludes_tool_results_and_sidechains(self):
        session, = self.collect("claude", [
            claude(RECENT, "user", "给我一个方案"),
            claude(RECENT, "assistant", [{"type": "text", "text": "这是方案"}, {"type": "thinking", "thinking": "内部"}]),
            claude(RECENT, "user", [{"type": "tool_result", "content": "非用户消息"}]),
            claude(RECENT, "user", "后台任务", isSidechain=True),
        ])
        self.assertEqual([turn["text"] for turn in session["messages"]], ["给我一个方案", "这是方案"])

    def test_render_only_installed_folder_and_safe_offline_html(self):
        module = SKILL / "scripts/render_report.py"
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "report.json"
            target = Path(root) / "report.html"
            source.write_text(json.dumps({"grades": {"交代任务": "B"}, "portraitText": "</textarea><script>alert(1)</script> &quot;"}))
            subprocess.run([sys.executable, str(module), "--json", str(source), "--html-output", str(target)], check=True)
            data = target.read_text()
            self.assertNotIn("</textarea><script>alert(1)", data)
            self.assertIn("\\u0026quot;", data)
            self.assertIn("data:image/png;base64,", data)
            self.assertIn("data:font/woff2;base64,", data)
            self.assertIn("\\u003c/textarea>", data)

    def test_legacy_html_imports_data_instead_of_scripts(self):
        module = SKILL / "scripts/render_report.py"
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "old.html"
            target = Path(root) / "report.html"
            source.write_text('<script>const REPORT = {"portraitText": "</script>"};</script>'
                              '<script>untrustedScript()</script>')
            subprocess.run([sys.executable, str(module), "--html", str(source),
                            "--html-output", str(target)], check=True, capture_output=True)
            data = target.read_text()
            self.assertNotIn("untrustedScript()", data)
            self.assertIn("\\u003c/script>", data)

    def test_score_samples_and_insufficient_coverage(self):
        module = SKILL / "scripts/render_report.py"
        spec = importlib.util.spec_from_file_location("render_report", module)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        samples = json.loads((SKILL.parent.parent / "scripts/samples.json").read_text())
        for grade, expected in zip("ABCDE", (93, 79, 54, 38, 16)):
            got = renderer.compute(samples[grade])
            self.assertEqual((got["overall"], got["avg"]), (grade, expected))
        self.assertEqual(renderer.compute({"grades": {"交代任务": "A"}})["overall"], "?")
        self.assertIsNone(renderer.compute({"grades": dict.fromkeys(renderer.ORDER, "A")})["low"])


if __name__ == "__main__":
    unittest.main()
