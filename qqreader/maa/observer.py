"""把 MaaFramework 识别能力适配成 :class:`~qqreader.runtime.observer.PageObserver`。

一次观测 = 截图 + OCR 全量文本 + 已标定模板分数 + 前台 App + 屏幕方向。
未标定模板的特征会被安全跳过；缺失证据只会让状态判为 ``UNKNOWN``，不会
推导为「目标不存在」。
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..page.features import FeatureKind
from ..page.observation import PageObservation
from ..page.states import Orientation
from .catalog import FeatureCatalog
from .client import MaaClient, Screenshot


class MaaPageObserver:
    """MaaFramework 观测器。"""

    def __init__(
        self,
        client: MaaClient,
        catalog: FeatureCatalog,
        *,
        foreground_probe: Any = None,
        structure_probe: Any = None,
        target_package: Optional[str] = None,
        clock: Any = None,
    ) -> None:
        self._client = client
        self._catalog = catalog
        self._foreground = foreground_probe
        self._structure = structure_probe
        self._target_package = target_package
        self._clock = clock
        self._last_screenshot: Optional[Screenshot] = None
        self._last_observation: Optional[PageObservation] = None

    @property
    def last_screenshot(self) -> Optional[Screenshot]:
        return self._last_screenshot

    @property
    def last_observation(self) -> Optional[PageObservation]:
        return self._last_observation

    @property
    def catalog(self) -> FeatureCatalog:
        return self._catalog

    def observe(self, context: Any = None, *, deep: bool = False) -> PageObservation:
        shot = self._client.screencap()
        self._last_screenshot = shot

        ocr_result = self._client.recognize("OCR", {}, shot)
        ocr_texts = ocr_result.all_texts() if ocr_result.hit or ocr_result.detail else ()

        templates: Dict[str, float] = {}
        icons: Dict[str, float] = {}
        for asset in self._catalog.assets.values():
            if asset.kind not in (FeatureKind.TEMPLATE, FeatureKind.ICON):
                continue
            if asset.template is None:
                continue
            result = self._client.recognize(
                "TemplateMatch",
                {"template": str(asset.template), "threshold": asset.threshold},
                shot,
            )
            if not result.hit or result.score is None:
                continue
            if asset.kind is FeatureKind.ICON:
                icons[asset.key] = result.score
            else:
                templates[asset.key] = result.score

        structure: Mapping[str, float] = {}
        if self._structure is not None:
            structure = self._structure.probe(shot, deep=deep) or {}

        current_app = None
        app_installed = None
        if self._foreground is not None:
            current_app = self._foreground.probe()
            if self._target_package and hasattr(self._foreground, "is_installed"):
                app_installed = self._foreground.is_installed(self._target_package)

        observation = PageObservation(
            current_app=current_app,
            orientation=(
                Orientation.LANDSCAPE if shot.landscape else Orientation.PORTRAIT
            ),
            title=None,
            ocr_texts=ocr_texts,
            icons=icons,
            templates=templates,
            structure=structure,
            device_online=True,
            app_installed=app_installed,
            captured_at=shot.captured_at or (self._clock.now() if self._clock else None),
            screenshot_path=None,
        )
        self._last_observation = observation
        return observation

    def save_last_screenshot(self, path: Any) -> Optional[Any]:
        if self._last_screenshot is None:
            return None
        return self._last_screenshot.save(path)
