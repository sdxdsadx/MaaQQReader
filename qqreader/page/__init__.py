"""页面状态层：状态枚举、多特征定义与识别器。"""

from .feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from .features import (
    FeatureAttempt,
    FeatureKind,
    FeatureMatch,
    FeatureSource,
    FeatureSpec,
    MatchMode,
    match_feature,
)
from .observation import PageObservation
from .profiles import build_default_state_definitions
from .recognizer import (
    PageStateRecognizer,
    RecognitionVerdict,
    StateCandidate,
    StateDecision,
    StateDefinition,
)
from .states import (
    REQUIRED_PAGE_STATES,
    TERMINAL_RUN_STATES,
    Orientation,
    PageState,
    RunState,
)

__all__ = [
    "DEFAULT_FEATURE_KEYS",
    "FeatureAttempt",
    "FeatureKeys",
    "FeatureKind",
    "FeatureMatch",
    "FeatureSource",
    "FeatureSpec",
    "MatchMode",
    "Orientation",
    "PageObservation",
    "PageState",
    "PageStateRecognizer",
    "REQUIRED_PAGE_STATES",
    "RecognitionVerdict",
    "RunState",
    "StateCandidate",
    "StateDecision",
    "StateDefinition",
    "TERMINAL_RUN_STATES",
    "build_default_state_definitions",
    "match_feature",
]
