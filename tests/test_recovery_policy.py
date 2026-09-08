"""恢复策略：升级阶梯、模拟器重启开关、耗尽语义。"""

from __future__ import annotations

import pytest

from qqreader.errors import ContractViolation
from qqreader.recovery.policy import (
    DEFAULT_ESCALATION,
    EscalationPolicy,
    RecoveryAction,
)


def test_ladder_order_and_wrap() -> None:
    policy = EscalationPolicy(max_rounds=2)
    expected = [a for a in DEFAULT_ESCALATION if a is not RecoveryAction.RESTART_EMULATOR]
    for index, action in enumerate(expected):
        assert policy.next_action(index) is action
    # 第二轮重新从头开始
    assert policy.next_action(len(expected)) is expected[0]


def test_emulator_restart_skipped_by_default() -> None:
    policy = EscalationPolicy()
    assert RecoveryAction.RESTART_EMULATOR not in policy.usable_ladder
    for attempt in range(20):
        assert policy.next_action(attempt) is not RecoveryAction.RESTART_EMULATOR


def test_emulator_restart_included_when_allowed() -> None:
    policy = EscalationPolicy(allow_emulator_restart=True)
    assert RecoveryAction.RESTART_EMULATOR in policy.usable_ladder


def test_exhausted_after_max_rounds() -> None:
    policy = EscalationPolicy(max_rounds=2)
    rounds = len(policy.usable_ladder) * 2
    assert policy.exhausted(rounds - 1) is False
    assert policy.exhausted(rounds) is True
    assert policy.next_action(rounds) is RecoveryAction.GIVE_UP


def test_give_up_must_not_be_in_ladder() -> None:
    with pytest.raises(ContractViolation):
        EscalationPolicy(ladder=(RecoveryAction.RESCREENSHOT, RecoveryAction.GIVE_UP))


def test_empty_ladder_rejected() -> None:
    with pytest.raises(ContractViolation):
        EscalationPolicy(ladder=())


def test_negative_attempt_rejected() -> None:
    with pytest.raises(ValueError):
        EscalationPolicy().next_action(-1)
