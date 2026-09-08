"""任务注册表。

调度核心按名字取任务定义；名字只是**配置键**，不参与任何行为分支。
"""

from __future__ import annotations

from typing import Dict, Iterator, Tuple

from ..errors import ContractViolation
from .definition import TaskDefinition


class TaskRegistry:
    """任务名 → 任务定义。"""

    def __init__(self) -> None:
        self._items: Dict[str, TaskDefinition] = {}

    def register(self, definition: TaskDefinition) -> None:
        name = definition.name
        if name in self._items:
            raise ContractViolation(f"任务名重复: {name}")
        self._items[name] = definition

    def get(self, name: str) -> TaskDefinition:
        try:
            return self._items[name]
        except KeyError as exc:
            raise ContractViolation(
                f"未注册的任务: {name!r}；已注册: {sorted(self._items)}"
            ) from exc

    def names(self) -> Tuple[str, ...]:
        return tuple(self._items)

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[TaskDefinition]:
        return iter(self._items.values())
