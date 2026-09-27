"""GUI 选择模拟器地址、阅读小说、听书书名与封面。

* 书名识别用真实书架 OCR 帧（``tests/fixtures/autoread_shelf_frames.json``，
  2026-09-27 实机，书架上同时有《宇智波》和《全职法师》）。
* 听书 pipeline 覆盖用与本机 ``qq_reader_trial.json`` 同结构的节点（``dev/`` 不进仓库）。
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import auto_read_30min as arm  # noqa: E402
import run_task  # noqa: E402

from qqreader.config import load_config  # noqa: E402
from qqreader.gui import cover as cover_tools  # noqa: E402
from qqreader.gui.commands import build_run_task_command  # noqa: E402
from qqreader.gui.device import (  # noqa: E402
    ADB_ADDRESS_ENV,
    candidate_addresses,
    child_env,
    load_device_address,
    mumu_default_addresses,
    parse_adb_devices,
    save_device_address,
    validate_address,
)
from qqreader.gui.task_catalog import (  # noqa: E402
    DEFAULT_TASK_CATALOG,
    apply_daily_preset,
    build_serial_plan,
    carry_over_selection,
    default_settings,
    load_task_settings,
    save_task_settings,
)
from qqreader.gui.widgets import describe_settings  # noqa: E402

FRAMES = json.loads(
    (ROOT / "tests" / "fixtures" / "autoread_shelf_frames.json").read_text(encoding="utf-8")
)
Box = Tuple[int, int, int, int]
SHELF: List[Tuple[str, Box]] = [(t, tuple(b)) for t, b in FRAMES["shelf"]["boxes"]]
SPECS = {spec.key: spec for spec in DEFAULT_TASK_CATALOG}

# 与本机 dev/resource/pipeline/qq_reader_trial.json 听书节点同结构（2026-09-27 读取）。
AUDIOBOOK_PIPELINE = {
    "DailyAudiobookFlow": {
        "action": "StartApp",
        "package": "com.qq.reader",
        "next": [
            "EnsureShelfOrGotoAudio",
            "AudiobookPlaying",
            "AudiobookFindBook",
            "AudiobookOpenFirstShelfBook",
            "AudiobookBackUntilShelf",
        ],
    },
    "AudiobookLeaveRewardPage": {"recognition": "OCR", "next": ["AudiobookFindBook"]},
    "AudiobookBackUntilShelf": {
        "action": "ClickKey",
        "key": 4,
        "max_hit": 8,
        "next": ["AudiobookFindBook", "AudiobookOpenFirstShelfBook", "AudiobookBackUntilShelf"],
    },
    "AudiobookOpenFirstShelfBook": {
        "recognition": "OCR",
        "target": [290, 180],
        "next": ["AudiobookPlaying", "AudiobookDismissProgressSync", "AudiobookOpenMenu"],
    },
    "AudiobookFindBook": {
        "recognition": "OCR",
        "expected": "全职法师",
        "action": "Click",
        "post_delay": 2500,
        "next": ["AudiobookPlaying", "AudiobookDismissProgressSync", "AudiobookOpenMenu"],
    },
    "AudiobookWaitOneMinute": {"post_delay": 1920000, "next": []},
}


# ------------------------------------------------------------------ 阅读：小说书名


def test_parse_book_keywords_defaults_and_splits() -> None:
    assert arm.parse_book_keywords("") == ("宇智波",)
    assert arm.parse_book_keywords(None) == ("宇智波",)
    assert arm.parse_book_keywords(" 全职 法师 ") == ("全职法师",)
    assert arm.parse_book_keywords("全职法师/宇智波 | ") == ("全职法师", "宇智波")
    assert arm.parse_book_keywords(" / ") == ("宇智波",)


def test_selected_novel_is_found_on_real_shelf(monkeypatch) -> None:
    """真实书架 OCR：选《全职法师》就点《全职法师》，不点默认的《宇智波》。"""
    monkeypatch.setattr(arm, "_allowed_keywords", arm.parse_book_keywords("全职法师"))
    box, why = arm.locate_allowed_book_ui(SHELF)
    expected = next(b for t, b in SHELF if "全职法师" in t)
    assert box == expected
    assert "全职法师" in why


def test_default_novel_still_uchiha_on_real_shelf(monkeypatch) -> None:
    monkeypatch.setattr(arm, "_allowed_keywords", arm.ALLOWED_BOOK_KEYWORDS)
    box, why = arm.locate_allowed_book_ui(SHELF)
    assert box is not None
    assert "宇智波" in why


def test_novel_not_on_shelf_is_rejected_not_substituted(monkeypatch) -> None:
    monkeypatch.setattr(arm, "_allowed_keywords", ("斗破苍穹",))
    box, why = arm.locate_allowed_book_ui(SHELF)
    assert box is None
    assert "斗破苍穹" in why


# ------------------------------------------------------------------ 听书：书名与封面


def test_audiobook_title_and_cover_override_pipeline() -> None:
    data = copy.deepcopy(AUDIOBOOK_PIPELINE)
    selection = run_task.BookSelection(title="斗罗大陆(第二部)", cover_image="x.png")

    run_task._apply_audiobook_book_overrides(data, selection, with_cover=True)

    assert data["AudiobookFindBook"]["expected"] == r"斗罗大陆\(第二部\)"
    cover = data[run_task.AUDIOBOOK_COVER_NODE]
    assert cover["recognition"] == "TemplateMatch"
    assert cover["template"] == run_task.AUDIOBOOK_COVER_TEMPLATE
    assert cover["next"] == data["AudiobookFindBook"]["next"]
    for name in ("DailyAudiobookFlow", "AudiobookBackUntilShelf", "AudiobookLeaveRewardPage"):
        nexts = data[name]["next"]
        assert nexts.index(run_task.AUDIOBOOK_COVER_NODE) == nexts.index("AudiobookFindBook") + 1
    # 默认仍保留“找不到时打开第一本”，与改动前行为一致。
    assert "AudiobookOpenFirstShelfBook" in data["DailyAudiobookFlow"]["next"]


def test_audiobook_without_fallback_never_opens_first_book() -> None:
    data = copy.deepcopy(AUDIOBOOK_PIPELINE)
    selection = run_task.BookSelection(title="全职法师", first_book_fallback=False)

    run_task._apply_audiobook_book_overrides(data, selection, with_cover=False)

    assert run_task.AUDIOBOOK_COVER_NODE not in data
    for node in data.values():
        assert "AudiobookOpenFirstShelfBook" not in node.get("next", [])
    assert data["AudiobookBackUntilShelf"]["next"] == ["AudiobookFindBook", "AudiobookBackUntilShelf"]


def test_patch_legacy_pipeline_writes_selection_and_returns_original(tmp_path: Path) -> None:
    pipeline = tmp_path / "pipeline" / "qq_reader_trial.json"
    pipeline.parent.mkdir()
    original = json.dumps(AUDIOBOOK_PIPELINE, ensure_ascii=False).encode("utf-8")
    pipeline.write_bytes(original)

    saved = run_task._patch_legacy_pipeline(
        tmp_path, "AudiobookWaitOneMinute", 1.0, "DailyAudiobookFlow",
        selection=run_task.BookSelection(title="诡秘之主"), with_cover=False,
    )

    assert saved == original
    patched = json.loads(pipeline.read_text(encoding="utf-8"))
    assert patched["AudiobookFindBook"]["expected"] == "诡秘之主"
    assert patched["AudiobookWaitOneMinute"]["post_delay"] == 60000


def test_install_cover_copies_into_maa_image_dir(tmp_path: Path) -> None:
    source = tmp_path / "封面 截图.png"
    source.write_bytes(b"\x89PNGcover")
    target = run_task._install_audiobook_cover(tmp_path / "resource", str(source))
    assert target == tmp_path / "resource" / "image" / run_task.AUDIOBOOK_COVER_TEMPLATE
    assert target.read_bytes() == b"\x89PNGcover"
    assert run_task._install_audiobook_cover(tmp_path / "resource", str(tmp_path / "no.png")) is None


def test_gui_settings_reach_run_task_arguments(tmp_path: Path, monkeypatch) -> None:
    """GUI 参数 → 命令行 → run_task 解析 → 分发到阅读 / 听书流程，整条链路。"""
    settings = default_settings()
    settings["DailyReadingFlow"].values["book_title"] = "全职法师"
    settings["DailyAudiobookFlow"].values.update(
        book_title="诡秘之主", cover_image=str(tmp_path / "c.png"), first_book_fallback=False
    )
    calls = {}
    monkeypatch.setattr(
        run_task, "_run_reading_task",
        lambda config, minutes, book="": calls.setdefault("reading", (minutes, book)) and 1,
    )
    monkeypatch.setattr(
        run_task, "_run_legacy_task",
        lambda task, config, minutes, selection=None: calls.setdefault("audio", selection) and 1,
    )
    for key in ("DailyReadingFlow", "DailyAudiobookFlow"):
        spec = SPECS[key]
        command = build_run_task_command(
            "python", ROOT, tmp_path / "c.json", key,
            settings=settings[key].normalized(spec).values,
        )
        args = run_task._build_parser().parse_args(list(command[2:]))
        assert run_task._main(args, object(), object()) == 1

    assert calls["reading"] == (35.0, "全职法师")
    assert calls["audio"] == run_task.BookSelection(
        title="诡秘之主", cover_image=str(tmp_path / "c.png"), first_book_fallback=False
    )


def test_default_audiobook_command_keeps_fallback(tmp_path: Path) -> None:
    spec = SPECS["DailyAudiobookFlow"]
    values = default_settings()[spec.key].normalized(spec).values
    command = build_run_task_command("python", ROOT, tmp_path / "c.json", spec.key, settings=values)
    assert command[command.index("--book-title") + 1] == "全职法师"
    assert "--cover-image" not in command
    assert "--no-first-book-fallback" not in command


# ------------------------------------------------------------------ 任务设置


def test_selection_survives_save_load_and_presets(tmp_path: Path) -> None:
    path = tmp_path / "gui_tasks.json"
    settings = default_settings()
    settings["DailyAudiobookFlow"].values.update(book_title=" 诡秘之主 ", cover_image="C:/a b/c.png")
    save_task_settings(path, settings)
    loaded = load_task_settings(path)
    apply_daily_preset(loaded, formal=False)
    plan = build_serial_plan(loaded)
    audio = next(item for item in plan if item.spec.key == "DailyAudiobookFlow")
    assert audio.settings.values["book_title"] == "诡秘之主"
    assert audio.settings.values["cover_image"] == "C:/a b/c.png"
    assert "《诡秘之主》" in describe_settings(audio.spec, audio.settings)


def test_dynamic_plan_keeps_selected_books() -> None:
    previous = default_settings()
    previous["DailyReadingFlow"].values["book_title"] = "全职法师"
    previous["DailyAudiobookFlow"].values["cover_image"] = "c.png"
    planned = default_settings()
    planned["DailyReadingFlow"].values["minutes"] = 12
    carry_over_selection(planned, previous)
    assert planned["DailyReadingFlow"].values["book_title"] == "全职法师"
    assert planned["DailyReadingFlow"].values["minutes"] == 12
    assert planned["DailyAudiobookFlow"].values["cover_image"] == "c.png"


# ------------------------------------------------------------------ 模拟器地址


def test_parse_adb_devices_output() -> None:
    output = (
        "* daemon not running; starting now at tcp:5037\n"
        "List of devices attached\n"
        "127.0.0.1:16384\tdevice\n"
        "127.0.0.1:16416\toffline\n"
        "emulator-5554\tdevice\n\n"
    )
    assert parse_adb_devices(output) == [
        ("127.0.0.1:16384", "device"),
        ("127.0.0.1:16416", "offline"),
        ("emulator-5554", "device"),
    ]


@pytest.mark.parametrize("raw", ["127.0.0.1:16384", " 127.0.0.1:5555 ", "emulator-5554", "localhost:7555"])
def test_validate_address_accepts(raw: str) -> None:
    assert validate_address(raw) == raw.strip()


@pytest.mark.parametrize("raw", ["", "127.0.0.1:", "127.0.0.1:99999", "a b", "http://x:1"])
def test_validate_address_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_address(raw)


def test_candidates_order_and_dedup() -> None:
    devices = [("127.0.0.1:16416", "device"), ("127.0.0.1:16448", "offline")]
    result = candidate_addresses(
        "127.0.0.1:16384", devices, saved="127.0.0.1:16416", extra=mumu_default_addresses(3)
    )
    assert result == ["127.0.0.1:16416", "127.0.0.1:16384", "127.0.0.1:16448"]


def test_device_choice_persists_and_reaches_child_config(tmp_path: Path) -> None:
    prefs = tmp_path / "gui_device.json"
    assert load_device_address(prefs) == ""
    save_device_address(prefs, "127.0.0.1:16416")
    assert load_device_address(prefs) == "127.0.0.1:16416"

    config = tmp_path / "qqreader.local.json"
    config.write_text(
        json.dumps({"machine": {"adb_path": "adb.exe", "adb_address": "127.0.0.1:16384"}}),
        encoding="utf-8",
    )
    env = child_env({"PATH": "x"}, load_device_address(prefs))
    assert env[ADB_ADDRESS_ENV] == "127.0.0.1:16416"
    # 子进程（run_task / auto_read / 旧流程）都经 load_config 读地址。
    assert load_config(config, env=env).machine.adb_address == "127.0.0.1:16416"
    assert load_config(config, env={}).machine.adb_address == "127.0.0.1:16384"

    save_device_address(prefs, "")
    assert load_device_address(prefs) == ""
    assert ADB_ADDRESS_ENV not in child_env({"PATH": "x"}, "")


# ------------------------------------------------------------------ 封面截取


def test_cover_crop_maps_display_to_screen_and_matches_back(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(7)
    screen = rng.integers(0, 255, size=(1280, 720, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", screen)
    assert ok
    png = encoded.tobytes()

    scale = cover_tools.display_scale(720, 1280, 420, 760)
    assert scale == 2
    box = cover_tools.crop_box((150, 400), (60, 300), scale, (720, 1280))
    assert box == (120, 600, 180, 200)

    path = cover_tools.save_cover(tmp_path, cover_tools.crop_png(png, box))
    assert path.parent == tmp_path / "covers"
    assert cover_tools.check_cover_file(path) == ""
    template = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _min, best, _loc, (x, y) = cv2.minMaxLoc(result)
    assert (x, y) == (120, 600) and best > 0.99


def test_cover_box_too_small_or_whole_screen_is_rejected() -> None:
    with pytest.raises(ValueError):
        cover_tools.crop_box((10, 10), (15, 15), 2, (720, 1280))
    with pytest.raises(ValueError):
        cover_tools.crop_box((0, 0), (360, 640), 2, (720, 1280))


def test_full_screenshot_is_not_accepted_as_cover(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    path = tmp_path / "full.png"
    ok, encoded = cv2.imencode(".png", np.zeros((1280, 720, 3), dtype=np.uint8))
    path.write_bytes(encoded.tobytes())
    assert "截取封面" in cover_tools.check_cover_file(path)
    assert "不存在" in cover_tools.check_cover_file(tmp_path / "missing.png")


def test_capture_screen_png_reports_adb_failure() -> None:
    class Result:
        def __init__(self, code, out, err=b""):
            self.returncode, self.stdout, self.stderr = code, out, err

    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return Result(0, b"\x89PNG\r\n")

    assert cover_tools.capture_screen_png("adb", "127.0.0.1:16416", runner=runner) == b"\x89PNG\r\n"
    assert calls[0] == ["adb", "-s", "127.0.0.1:16416", "exec-out", "screencap", "-p"]
    with pytest.raises(RuntimeError):
        cover_tools.capture_screen_png(
            "adb", "x:1", runner=lambda c, **k: Result(1, b"", b"device offline")
        )


def test_cover_dialog_hint_fits_canvas(tmp_path: Path) -> None:
    """2026-09-27 GUI 实机：截取对话框顶部说明右侧被截断（wraplength 大于画布宽度）。"""
    tk = pytest.importorskip("tkinter")
    from qqreader.gui.app import CoverCaptureDialog

    try:
        root = tk.Tk()
    except tk.TclError as exc:  # 本机 Tcl 偶发不可用时与 test_gui_user_click_flow 一样跳过
        pytest.skip(f"Tk 不可用: {exc}")
    root.withdraw()
    try:
        dialog = CoverCaptureDialog(
            root,
            adb_path=str(tmp_path / "missing-adb.exe"),
            address="127.0.0.1:16384",
            runtime_dir=tmp_path,
            on_saved=lambda _path: None,
        )
        root.update_idletasks()
        hint = next(
            w for w in dialog._top.winfo_children()
            if isinstance(w, tk.Label) and "书架" in str(w.cget("text"))
        )
        assert hint.winfo_reqwidth() <= int(dialog._canvas.cget("width")) + 24
    finally:
        root.destroy()
