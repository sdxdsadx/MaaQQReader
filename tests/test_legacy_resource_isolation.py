"""运行资源属于本次子进程；强制停止不得改坏下一项使用的源资源。"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_task


def resource_config(tmp_path):
    resource = tmp_path / '源资源'
    (resource / 'pipeline').mkdir(parents=True)
    (resource / 'image').mkdir()
    (resource / 'model' / 'ocr').mkdir(parents=True)
    (resource / 'model' / 'ocr' / 'model.onnx').write_bytes(b'model')
    pipeline = resource / 'pipeline' / 'qq_reader_trial.json'
    pipeline.write_bytes(b'{"AudiobookFindBook":{"expected":"original","next":[]}}')
    return SimpleNamespace(machine=SimpleNamespace(
        maa_resource_dir=resource, maa_runtime_dir=tmp_path / 'dll',
        adb_path='adb.exe', adb_address='test-device', package_name='com.qq.reader',
        log_dir=tmp_path / 'runtime' / 'logs',
    ))


def test_legacy_child_reads_private_overrides_without_mutating_source(tmp_path, monkeypatch):
    config = resource_config(tmp_path)
    source = config.machine.maa_resource_dir
    original = (source / 'pipeline' / 'qq_reader_trial.json').read_bytes()
    monkeypatch.setattr('qqreader.maa.adb.ensure_maa_ready', lambda *a, **k: (True, 'test'))

    def launch(command, **kwargs):
        bundle = Path(command[command.index('--resource') + 1])
        # 此时旧实现尚未 finally 恢复，捕获真实的源文件被覆盖问题。
        assert (source / 'pipeline' / 'qq_reader_trial.json').read_bytes() == original
        assert bundle != source
        assert json.loads((bundle / 'pipeline' / 'qq_reader_trial.json').read_text(encoding='utf-8'))['AudiobookFindBook']['expected'] == '新书'
        assert (bundle / 'model' / 'ocr' / 'model.onnx').read_bytes() == b'model'
        return SimpleNamespace(stdout=iter([]), wait=lambda: 2)

    monkeypatch.setattr(run_task.subprocess, 'Popen', launch)
    assert run_task._run_legacy_task('DailyAudiobookFlow', config, None,
                                    run_task.BookSelection(title='新书')) == 2
    assert (source / 'pipeline' / 'qq_reader_trial.json').read_bytes() == original


def test_audiobook_cover_does_not_overwrite_existing_source_image(tmp_path, monkeypatch):
    config = resource_config(tmp_path)
    source_image = config.machine.maa_resource_dir / 'image' / run_task.AUDIOBOOK_COVER_TEMPLATE
    source_image.write_bytes(b'original-template')
    cover = tmp_path / 'selected-cover.png'
    cover.write_bytes(b'new-cover')
    monkeypatch.setattr('qqreader.maa.adb.ensure_maa_ready', lambda *a, **k: (True, 'test'))

    def launch(command, **kwargs):
        bundle = Path(command[command.index('--resource') + 1])
        assert source_image.read_bytes() == b'original-template'
        assert (bundle / 'image' / run_task.AUDIOBOOK_COVER_TEMPLATE).read_bytes() == b'new-cover'
        return SimpleNamespace(stdout=iter([]), wait=lambda: 0)

    monkeypatch.setattr(run_task.subprocess, 'Popen', launch)
    assert run_task._run_legacy_task('DailyAudiobookFlow', config, None,
        run_task.BookSelection(title='新书', cover_image=str(cover))) == 0
    assert source_image.read_bytes() == b'original-template'


@pytest.mark.skipif(os.name != 'nt', reason='复现本机 GUI 的 Windows PID 整树强制停止')
def test_forced_wrapper_stop_leaves_source_pipeline_byte_identical(tmp_path):
    config = resource_config(tmp_path)
    pipeline = config.machine.maa_resource_dir / 'pipeline' / 'qq_reader_trial.json'
    original = pipeline.read_bytes()
    ready = tmp_path / 'loaded-resource.json'
    worker = tmp_path / 'worker.py'
    worker.write_text(
        "import sys,json,time\nfrom pathlib import Path\n"
        "p=Path(sys.argv[sys.argv.index('--resource')+1])\n"
        f"Path({str(ready)!r}).write_text(json.dumps(str(p)),encoding='utf-8')\n"
        "time.sleep(30)\n", encoding='utf-8')
    wrapper = tmp_path / 'wrapper.py'
    wrapper.write_text(
        "import sys\nfrom pathlib import Path\nfrom types import SimpleNamespace as S\n"
        f"sys.path.insert(0,{str(Path(run_task.__file__).parent)!r})\nimport run_task\n"
        "import qqreader.maa.adb\nqqreader.maa.adb.ensure_maa_ready=lambda *a,**k:(True,'test')\n"
        f"run_task._find_legacy_runner=lambda _:Path({str(worker)!r})\n"
        f"c=S(machine=S(maa_resource_dir=Path({str(config.machine.maa_resource_dir)!r}),"
        f"maa_runtime_dir='dll',adb_path='adb.exe',adb_address='test-device',"
        f"package_name='com.qq.reader',log_dir=Path({str(config.machine.log_dir)!r})))\n"
        "run_task._run_legacy_task('DailyAudiobookFlow',c,None,run_task.BookSelection(title='新书'))\n",
        encoding='utf-8')
    process = subprocess.Popen([sys.executable, str(wrapper)], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        deadline = time.monotonic() + 8
        while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.03)
        assert ready.exists(), '本地测试子进程未加载资源'
    finally:
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=10, check=True)
        process.wait(timeout=5)
    assert pipeline.read_bytes() == original
    bundle = Path(json.loads(ready.read_text(encoding='utf-8')))
    assert bundle != config.machine.maa_resource_dir
    assert json.loads((bundle / 'pipeline' / 'qq_reader_trial.json').read_text(encoding='utf-8'))['AudiobookFindBook']['expected'] == '新书'
