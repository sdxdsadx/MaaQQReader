"""MFAAvalonia ``interface.json`` 与 pipeline 生成器的测试。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from qqreader.gui.task_catalog import (
    DEFAULT_TASK_CATALOG,
    FORMAL_PRESET_KEYS,
    TRIAL_PRESET_KEYS,
)
from qqreader.mfa.agent_action import ACTION_NAME, parse_param
from qqreader.mfa.interface import (
    build_interface,
    build_pipeline,
    entry_name,
    option_name,
    read_project_version,
)

ROOT = Path(__file__).resolve().parents[1]
INTERFACE_PATH = ROOT / "mfa" / "interface.json"
PIPELINE_PATH = ROOT / "mfa" / "resource" / "pipeline" / "qqreader.json"
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _settable_fields(spec):
    return [item for item in spec.fields if item.key != "count"]


class MfaInterfaceTest(unittest.TestCase):
    def setUp(self):
        self.version = read_project_version(ROOT / "pyproject.toml")
        self.interface = build_interface(version=self.version)
        self.pipeline = build_pipeline()

    def test_version_read_from_pyproject(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{self.version}"', text)
        self.assertEqual(self.interface["version"], self.version)

    def test_committed_files_match_generator(self):
        self.assertEqual(
            json.loads(INTERFACE_PATH.read_text(encoding="utf-8")), self.interface
        )
        self.assertEqual(
            json.loads(PIPELINE_PATH.read_text(encoding="utf-8")), self.pipeline
        )

    def test_build_script_check_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_mfa_interface.py"), "--check"],
            cwd=str(ROOT),
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_top_level_fields(self):
        data = self.interface
        self.assertEqual(data["interface_version"], 2)
        self.assertEqual(data["name"], "MaaQQReader")
        self.assertEqual(data["label"], "QQ阅读每日任务")
        self.assertEqual(data["title"], "QQ阅读每日任务")
        self.assertEqual(
            data["controller"],
            [{"name": "MuMu安卓端", "type": "Adb", "display_short_side": 720}],
        )
        self.assertEqual(data["resource"], [{"name": "QQ阅读", "path": ["./resource"]}])
        self.assertEqual(
            data["agent"],
            {"child_exec": "python", "child_args": ["-X", "utf8", "./agent/main.py"]},
        )

    def test_every_task_in_catalog(self):
        tasks = self.interface["task"]
        self.assertEqual([t["entry"] for t in tasks], [entry_name(s.key) for s in DEFAULT_TASK_CATALOG])
        self.assertEqual(
            set(self.pipeline), {entry_name(s.key) for s in DEFAULT_TASK_CATALOG}
        )
        for spec, task in zip(DEFAULT_TASK_CATALOG, tasks):
            self.assertEqual(task["name"], spec.name)
            self.assertEqual(task["description"], spec.description)
            self.assertEqual(task["default_check"], spec.default_enabled)
            self.assertIn(task["entry"], self.pipeline)
            count = next((f for f in spec.fields if f.key == "count"), None)
            if count is None:
                self.assertNotIn("repeatable", task)
            else:
                self.assertIs(task["repeatable"], True)
                self.assertEqual(task["repeat_count"], count.default)

    def test_entry_name(self):
        self.assertEqual(entry_name("DailyAdFlow"), "QQR_DailyAdFlow")

    def test_pipeline_nodes_call_agent_action_with_defaults(self):
        for spec in DEFAULT_TASK_CATALOG:
            node = self.pipeline[entry_name(spec.key)]
            self.assertEqual(node["action"], "Custom")
            self.assertEqual(node["custom_action"], ACTION_NAME)
            param = node["custom_action_param"]
            self.assertEqual(param["task"], spec.key)
            self.assertNotIn("count", param)
            for item in _settable_fields(spec):
                self.assertEqual(param[item.key], item.default)
            # Agent 侧必须能直接解析
            parsed_spec, _ = parse_param(param)
            self.assertEqual(parsed_spec.key, spec.key)

    def test_one_input_option_per_task_with_full_param(self):
        """MFA 把各选项的覆盖按顺序交给 MaaFramework，节点顶层键整体替换，
        所以同一节点的 custom_action_param 只能由一个选项写全（含 task）。"""
        options = self.interface["option"]
        for spec, task in zip(DEFAULT_TASK_CATALOG, self.interface["task"]):
            fields = _settable_fields(spec)
            if not fields:
                self.assertEqual(task["option"], [])
                continue
            self.assertEqual(task["option"], [option_name(spec.key)])
            option = options[option_name(spec.key)]
            self.assertEqual(option["type"], "input")
            self.assertEqual(set(option["pipeline_override"]), {entry_name(spec.key)})
            param = option["pipeline_override"][entry_name(spec.key)]["custom_action_param"]
            self.assertEqual(param["task"], spec.key)
            self.assertEqual(set(param), {"task"} | {f.key for f in fields})
            for item in fields:
                self.assertEqual(param[item.key], "{" + item.key + "}")

    def test_placeholders_defined(self):
        for name, option in self.interface["option"].items():
            names = {item["name"] for item in option.get("inputs", [])}
            for text in _walk_strings(option.get("pipeline_override", {})):
                for placeholder in PLACEHOLDER.findall(text):
                    self.assertIn(placeholder, names, f"{name}: {{{placeholder}}}")

    def test_pipeline_types_are_supported_by_pi_v2(self):
        kinds = {"float": "string", "int": "int", "bool": "bool", "text": "string", "file": "string"}
        for spec in DEFAULT_TASK_CATALOG:
            fields = _settable_fields(spec)
            if not fields:
                continue
            inputs = {i["name"]: i for i in self.interface["option"][option_name(spec.key)]["inputs"]}
            for item in fields:
                self.assertIn(inputs[item.key]["pipeline_type"], {"string", "int", "bool"})
                self.assertEqual(inputs[item.key]["pipeline_type"], kinds[item.kind])

    def test_defaults_match_catalog(self):
        for spec in DEFAULT_TASK_CATALOG:
            fields = _settable_fields(spec)
            if not fields:
                continue
            inputs = {i["name"]: i for i in self.interface["option"][option_name(spec.key)]["inputs"]}
            for item in fields:
                default = inputs[item.key]["default"]
                self.assertIsInstance(default, str)
                self.assertEqual(item.normalize(default), item.default, f"{spec.key}.{item.key}")
                if item.kind == "bool":
                    self.assertEqual(default, "true" if item.default else "false")
                elif item.kind in ("text", "file"):
                    self.assertEqual(default, str(item.default))
                    self.assertNotIn("verify", inputs[item.key])

    def test_every_option_referenced(self):
        referenced = {name for task in self.interface["task"] for name in task["option"]}
        self.assertEqual(set(self.interface["option"]), referenced)

    def test_numeric_verify_rejects_bad_input(self):
        checked = 0
        for option in self.interface["option"].values():
            for item in option["inputs"]:
                if item["pipeline_type"] == "bool":
                    pattern = item["verify"]
                    self.assertTrue(re.fullmatch(pattern, "true"))
                    self.assertTrue(re.fullmatch(pattern, "false"))
                    self.assertFalse(re.fullmatch(pattern, "yes"))
                    continue
                if "verify" not in item:
                    continue
                pattern = item["verify"]
                checked += 1
                for bad in ("abc", "-1", ""):
                    self.assertFalse(re.fullmatch(pattern, bad), (pattern, bad))
                goods = ("35",) if item["pipeline_type"] == "int" else ("35", "0.5")
                for good in goods:
                    self.assertTrue(re.fullmatch(pattern, good), (pattern, good))
        self.assertGreater(checked, 0)

    def _preset(self, name):
        return next(p for p in self.interface["preset"] if p["name"] == name)

    def test_formal_preset_defaults(self):
        preset = self._preset("正式每日")
        by_name = {t["name"]: t for t in preset["task"]}
        for spec in DEFAULT_TASK_CATALOG:
            entry = by_name[spec.name]
            self.assertEqual(entry["enabled"], spec.key in FORMAL_PRESET_KEYS)
            fields = _settable_fields(spec)
            if spec.key in FORMAL_PRESET_KEYS and fields:
                values = entry["option"][option_name(spec.key)]
                for item in fields:
                    self.assertEqual(item.normalize(values[item.key]), item.default)

    def test_trial_preset_one_minute(self):
        preset = self._preset("1 分钟试跑")
        by_name = {t["name"]: t for t in preset["task"]}
        for spec in DEFAULT_TASK_CATALOG:
            self.assertEqual(by_name[spec.name]["enabled"], spec.key in TRIAL_PRESET_KEYS)
        minutes = {}
        for spec in DEFAULT_TASK_CATALOG:
            if spec.key not in TRIAL_PRESET_KEYS:
                continue
            values = by_name[spec.name]["option"][option_name(spec.key)]
            for key in ("minutes", "duration_minutes"):
                if key in values:
                    minutes[spec.key] = values[key]
        self.assertEqual(
            minutes,
            {"DailyReadingFlow": "1", "DailyAudiobookFlow": "1", "DailyGameFlow": "1"},
        )

    def test_preset_option_values_are_string_records(self):
        for preset in self.interface["preset"]:
            for task in preset["task"]:
                for option, values in task.get("option", {}).items():
                    self.assertIn(option, self.interface["option"])
                    names = {i["name"] for i in self.interface["option"][option]["inputs"]}
                    self.assertEqual(set(values), names)
                    for value in values.values():
                        self.assertIsInstance(value, str)


if __name__ == "__main__":
    unittest.main()
