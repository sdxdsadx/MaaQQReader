"""页面特征：类型、规格与匹配。

AGENTS.md §3.2 要求每个状态由**多特征**共同确认：页面标题、固定图标、
OCR 文本、局部模板、屏幕方向、当前 App、页面结构特征。本模块定义这些
特征的描述方式与单条特征的匹配逻辑；组合判定在 :mod:`qqreader.page.recognizer`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Protocol, Tuple

from ..errors import ContractViolation
from .states import Orientation


class FeatureKind(str, Enum):
    """特征种类。"""

    TITLE = "TITLE"                  # 页面标题（OCR）
    ICON = "ICON"                    # 固定图标（模板匹配）
    OCR = "OCR"                      # OCR 文本
    TEMPLATE = "TEMPLATE"            # 局部模板（模板匹配）
    ORIENTATION = "ORIENTATION"      # 屏幕方向
    CURRENT_APP = "CURRENT_APP"      # 当前前台 App 包名
    STRUCTURE = "STRUCTURE"          # 页面结构特征


class MatchMode(str, Enum):
    """匹配方式。"""

    EQUALS = "EQUALS"        # 精确等于
    CONTAINS = "CONTAINS"    # 文本包含
    ONE_OF = "ONE_OF"        # 命中候选之一
    REGEX = "REGEX"          # 正则匹配（候选值即正则表达式）
    MIN_SCORE = "MIN_SCORE"  # 分数达到阈值（模板/结构）


#: 使用「相似度分数表」的特征。
_SCORE_KINDS = frozenset(
    {FeatureKind.ICON, FeatureKind.TEMPLATE, FeatureKind.STRUCTURE}
)
#: 使用「文本/枚举字符串」的特征。
_TEXT_KINDS = frozenset(
    {
        FeatureKind.TITLE,
        FeatureKind.OCR,
        FeatureKind.ORIENTATION,
        FeatureKind.CURRENT_APP,
    }
)


class FeatureSource(Protocol):
    """可供特征匹配的观测来源（:class:`~qqreader.page.observation.PageObservation`）。"""

    current_app: Optional[str]
    orientation: Orientation
    title: Optional[str]
    ocr_texts: Tuple[str, ...]
    icons: Mapping[str, float]
    templates: Mapping[str, float]
    structure: Mapping[str, float]


@dataclass(frozen=True)
class FeatureSpec:
    """一条可确认的特征。

    ``key`` 是主匹配值；``values`` 是备选值（任一命中即可）。
    ``required=True`` 表示该特征必须命中，否则整个状态不成立。
    """

    kind: FeatureKind
    key: str = ""
    weight: float = 1.0
    required: bool = False
    threshold: float = 0.75
    mode: MatchMode = MatchMode.CONTAINS
    values: Tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ContractViolation("FeatureSpec.weight 必须 > 0")
        if not 0.0 <= self.threshold <= 1.0:
            raise ContractViolation("FeatureSpec.threshold 必须在 0..1")
        if self.kind in _SCORE_KINDS:
            if not self.key:
                raise ContractViolation(f"{self.kind.value} 特征必须提供 key")
            if self.mode is not MatchMode.MIN_SCORE:
                raise ContractViolation(f"{self.kind.value} 特征必须使用 MIN_SCORE")
        elif self.kind in _TEXT_KINDS:
            if self.mode is MatchMode.MIN_SCORE:
                raise ContractViolation(f"{self.kind.value} 特征不支持 MIN_SCORE")
            if not self.key and not self.values:
                raise ContractViolation(f"{self.kind.value} 特征必须提供 key 或 values")
            if self.mode is MatchMode.REGEX:
                for pattern in self.candidates:
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        raise ContractViolation(f"非法正则 {pattern!r}: {exc}") from exc
        else:  # pragma: no cover - 枚举已穷尽
            raise ContractViolation(f"未知特征类型: {self.kind}")

    @property
    def candidates(self) -> Tuple[str, ...]:
        """全部候选匹配值（key 在前）。"""
        return tuple(c for c in (self.key,) + self.values if c)


@dataclass(frozen=True)
class FeatureMatch:
    """单条特征的匹配结果。"""

    spec: FeatureSpec
    matched: bool
    score: float
    detail: str

    @property
    def kind(self) -> FeatureKind:
        return self.spec.kind


def _norm(text: str) -> str:
    return text.strip().casefold()


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else float(value)


def _match_text(spec: FeatureSpec, texts: Tuple[str, ...]) -> Tuple[bool, str]:
    normalized = tuple(_norm(t) for t in texts if t and t.strip())
    candidates = tuple(_norm(c) for c in spec.candidates)
    if not normalized or not candidates:
        return False, f"{spec.kind.value} 文本为空或候选为空"
    for text in normalized:
        for candidate in candidates:
            if spec.mode is MatchMode.EQUALS and text == candidate:
                return True, f'{spec.kind.value} 精确命中 "{candidate}"'
            if spec.mode in (MatchMode.CONTAINS, MatchMode.ONE_OF) and candidate in text:
                return True, f'{spec.kind.value} 包含 "{candidate}"'
            if spec.mode is MatchMode.REGEX and re.search(candidate, text):
                return True, f'{spec.kind.value} 正则命中 /{candidate}/'
    return False, f'{spec.kind.value} 未命中候选 {list(spec.candidates)!r}'


def _match_value(spec: FeatureSpec, value: Optional[str]) -> Tuple[bool, str]:
    if value is None or not str(value).strip():
        return False, f"{spec.kind.value} 为空"
    actual = value.value if isinstance(value, Enum) else str(value)
    actual_norm = _norm(actual)
    for candidate in spec.candidates:
        if actual_norm == _norm(candidate):
            return True, f'{spec.kind.value} == "{candidate}"'
    return False, f'{spec.kind.value}={actual!r} 不在 {list(spec.candidates)!r}'


def _match_score(spec: FeatureSpec, table: Mapping[str, float]) -> Tuple[bool, str]:
    raw = float(table.get(spec.key, 0.0))
    score = _clamp(raw)
    matched = score >= spec.threshold
    return matched, f"{spec.kind.value}[{spec.key}]={raw:.3f} (阈值 {spec.threshold:.3f})"


def match_feature(spec: FeatureSpec, source: FeatureSource) -> FeatureMatch:
    """把一条 :class:`FeatureSpec` 与一次观测做匹配。"""
    if spec.kind is FeatureKind.ORIENTATION:
        matched, detail = _match_value(spec, source.orientation)
        return FeatureMatch(spec, matched, 1.0 if matched else 0.0, detail)
    if spec.kind is FeatureKind.CURRENT_APP:
        matched, detail = _match_value(spec, source.current_app)
        return FeatureMatch(spec, matched, 1.0 if matched else 0.0, detail)
    if spec.kind is FeatureKind.TITLE:
        matched, detail = _match_text(spec, (source.title,) if source.title else ())
        return FeatureMatch(spec, matched, 1.0 if matched else 0.0, detail)
    if spec.kind is FeatureKind.OCR:
        matched, detail = _match_text(spec, tuple(source.ocr_texts))
        return FeatureMatch(spec, matched, 1.0 if matched else 0.0, detail)
    if spec.kind is FeatureKind.ICON:
        matched, detail = _match_score(spec, source.icons)
        return FeatureMatch(spec, matched, _clamp(source.icons.get(spec.key, 0.0)), detail)
    if spec.kind is FeatureKind.TEMPLATE:
        matched, detail = _match_score(spec, source.templates)
        return FeatureMatch(spec, matched, _clamp(source.templates.get(spec.key, 0.0)), detail)
    if spec.kind is FeatureKind.STRUCTURE:
        matched, detail = _match_score(spec, source.structure)
        return FeatureMatch(spec, matched, _clamp(source.structure.get(spec.key, 0.0)), detail)
    raise ContractViolation(f"未知特征类型: {spec.kind}")  # pragma: no cover
