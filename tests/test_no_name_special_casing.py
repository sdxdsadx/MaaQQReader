"""调度核心不得按任务名特判：名字只是注册键。"""

from __future__ import annotations

from pathlib import Path

import pytest

import qqreader.runner.runner as runner_module
from qqreader.contract.conditions import StateIs, feature, state_in
from qqreader.contract.outcome import TaskOutcome
from qqreader.errors import ContractViolation
from qqreader.page.features import FeatureKind, FeatureSpec
from qqreader.page.states import PageState
from qqreader.runner.registry import TaskRegistry
from qqreader.runner.runner import TaskRunner
from qqreader.runtime.clock import FakeClock
from tests.helpers import (
    FakeAdapter,
    QueueObserver,
    home_observation,
    make_contract,
    make_definition,
    reward_observation,
)


def _contract(name: str):
    return make_contract(
        name=name,
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME),
        ready_condition=StateIs(PageState.REWARD_HOME),
        success_condition=feature(FeatureSpec(kind=FeatureKind.OCR, key="12/12")),
        timeout_seconds=60.0,
    )


def test_runner_behaviour_does_not_depend_on_task_name() -> None:
    def run(name: str):
        observer = QueueObserver(
            [home_observation(), reward_observation(ocr=("12/12",))]
        )
        definition = make_definition(_contract(name), observer, FakeAdapter())
        return TaskRunner(definition, FakeClock()).run()

    custom = run("zzz_custom")
    named = run("DailyAdFlow")

    assert custom.outcome is TaskOutcome.SUCCESS
    assert named.outcome is TaskOutcome.SUCCESS
    assert custom.steps == named.steps
    assert custom.final_state == named.final_state
    assert custom.run_state == named.run_state
    # 唯一允许的差异是任务名本身。
    assert custom.task != named.task


def test_registry_is_pure_lookup_by_name() -> None:
    registry = TaskRegistry()
    definition = make_definition(
        _contract("zzz_custom"), QueueObserver([home_observation()]), FakeAdapter()
    )
    registry.register(definition)
    assert registry.get("zzz_custom") is definition
    with pytest.raises(ContractViolation):
        registry.get("DailyAdFlow")
    with pytest.raises(ContractViolation):
        registry.register(definition)


def test_runner_core_contains_no_task_name_or_feature_literals() -> None:
    source = Path(runner_module.__file__).read_text(encoding="utf-8")
    for literal in ("DailyAdFlow", "DailyGameFlow", "看小视频", "玩游戏领赠币"):
        assert literal not in source, f"调度核心出现任务相关字面量: {literal}"
    assert "from ..tasks" not in source
    assert "import tasks" not in source
