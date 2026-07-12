import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def load_script(name, path):
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
module = load_script("codex_waybar", ROOT / "bin" / "codex-waybar")
configure = load_script("codex_waybar_configure", ROOT / "bin" / "codex-waybar-configure")


def rate_result(five_used=22, weekly_used=18):
    return {
        "rateLimits": {
            "limitId": "codex",
            "planType": "plus",
            "primary": {
                "usedPercent": five_used,
                "windowDurationMins": 300,
                "resetsAt": 10_000,
            },
            "secondary": {
                "usedPercent": weekly_used,
                "windowDurationMins": 10_080,
                "resetsAt": 200_000,
            },
        }
    }


class UsageModuleTests(unittest.TestCase):
    def test_fetch_handles_multiple_responses_in_one_pipe_read(self):
        server = """import json, sys
for line in sys.stdin:
    message = json.loads(line)
    if message.get('id') == 2:
        result = {'rateLimits': {'limitId': 'codex'}}
        responses = [
            {'id': 1, 'result': {}},
            {'method': 'notification', 'params': {}},
            {'id': 2, 'result': result},
        ]
        sys.stdout.write(''.join(json.dumps(item) + '\\n' for item in responses))
        sys.stdout.flush()
        break
"""
        real_popen = subprocess.Popen

        def fake_popen(command, **kwargs):
            return real_popen([sys.executable, "-c", server], **kwargs)

        with patch.object(module.subprocess, "Popen", side_effect=fake_popen):
            result = module.fetch_rate_limits(timeout=1)
        self.assertEqual(result, {"rateLimits": {"limitId": "codex"}})

    def test_parse_json_lines_ignores_notifications(self):
        output = "\n".join(
            [
                '{"id":1,"result":{}}',
                '{"method":"notification","params":{}}',
                json.dumps({"id": 2, "result": rate_result()}),
            ]
        )
        self.assertEqual(module.parse_json_lines(output), rate_result())

    def test_selects_windows_by_duration_not_position(self):
        result = rate_result()
        snapshot = result["rateLimits"]
        snapshot["primary"], snapshot["secondary"] = snapshot["secondary"], snapshot["primary"]
        values, percentage = module.format_values(snapshot, now=1_000)
        self.assertEqual(values["five_hour_used"], 22)
        self.assertEqual(values["weekly_used"], 18)
        self.assertEqual(percentage, 22)

    def test_countdown_formats_and_clamps(self):
        self.assertEqual(module.human_countdown(1_000, 1_000), "0m")
        self.assertEqual(module.human_countdown(4_601, 1_000), "1h 01m")
        self.assertEqual(module.human_countdown(91_000, 1_000), "1d 1h")
        self.assertEqual(module.human_countdown(999, 1_000), "0m")

    def test_output_sets_classes_and_custom_format(self):
        output = module.output_json(
            rate_result(five_used=72),
            "{five_hour_used}/{weekly_used} {five_hour_reset_in}",
            "{plan}",
            warning=70,
            critical=90,
            now=1_000,
        )
        self.assertEqual(output["text"], "72/18 2h 30m")
        self.assertEqual(output["tooltip"], "plus")
        self.assertEqual(output["class"], ["warning"])
        self.assertEqual(output["percentage"], 72)

    def test_missing_window_is_rendered_as_unavailable(self):
        result = rate_result()
        result["rateLimits"]["secondary"] = None
        output = module.output_json(result, module.DEFAULT_FORMAT, module.DEFAULT_TOOLTIP, 70, 90)
        self.assertIn("W n/a%", output["text"])
        self.assertEqual(output["percentage"], 22)

    def test_unknown_template_field_is_rejected(self):
        with self.assertRaises(module.UsageError):
            module.validate_template("{not_a_field}")

    def test_main_uses_stale_cache_after_fetch_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "codex-waybar" / "rate-limits.json"
            module.save_cache(path, rate_result())
            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}),
                patch.object(module, "fetch_rate_limits", side_effect=module.UsageError("offline")),
                redirect_stdout(stdout),
            ):
                exit_code = module.main(["--format", "{five_hour_used}%"])
            output = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(output["text"], "22%")
            self.assertIn("stale", output["class"])

    def test_main_returns_unavailable_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}),
                patch.object(module, "fetch_rate_limits", side_effect=module.UsageError("offline")),
                redirect_stdout(stdout),
            ):
                module.main([])
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["class"], ["unavailable"])
            self.assertIn("offline", output["tooltip"])

    def test_terminal_mode_renders_readable_usage(self):
        stdout = io.StringIO()
        with (
            patch.object(module, "fetch_rate_limits", return_value=rate_result(five_used=72, weekly_used=18)),
            redirect_stdout(stdout),
        ):
            exit_code = module.main(["--terminal", "--color", "never"])
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Codex usage · plus", output)
        self.assertIn("5-hour", output)
        self.assertIn("72% used", output)
        self.assertIn("Weekly", output)
        self.assertIn("WARNING", output)
        self.assertNotIn("\033[", output)

    def test_terminal_mode_reports_unavailable_without_json(self):
        stdout = io.StringIO()
        with (
            patch.object(module, "fetch_rate_limits", side_effect=module.UsageError("offline")),
            patch.object(module, "load_cache", return_value=None),
            redirect_stdout(stdout),
        ):
            module.main(["--mode", "terminal", "--color", "never"])
        self.assertIn("Codex usage unavailable", stdout.getvalue())
        self.assertNotIn('{"text"', stdout.getvalue())


class ConfigureTests(unittest.TestCase):
    CONFIG = """{
  // Existing comment
  "modules-left": ["clock"],
  "modules-center": [],
  "modules-right": [
    "cpu"
  ],
  "cpu": {"interval": 5}
}
"""

    def test_configure_preserves_comments_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.jsonc"
            style = Path(tmp) / "style.css"
            config.write_text(self.CONFIG)
            style.write_text("* { color: white; }\n")

            configure.configure(config, style, "right")
            first_config = config.read_text()
            first_style = style.read_text()
            configure.configure(config, style, "right")

            self.assertIn("// Existing comment", first_config)
            self.assertEqual(first_config.count('"custom/codex-usage"'), 2)
            self.assertEqual(config.read_text(), first_config)
            self.assertEqual(style.read_text(), first_style)
            self.assertEqual(first_style.count("#custom-codex-usage"), 5)

    def test_ambiguous_section_aborts_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.jsonc"
            style = Path(tmp) / "style.css"
            original = '{"modules-right": [], "modules-right": []}\n'
            config.write_text(original)
            style.write_text("")
            with self.assertRaises(configure.ConfigureError):
                configure.configure(config, style, "right")
            self.assertEqual(config.read_text(), original)


if __name__ == "__main__":
    unittest.main()
