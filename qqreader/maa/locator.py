"""逻辑特征定位：把 ``tap_feature(key)`` 变成屏幕坐标。"""

from __future__ import annotations

from typing import Dict, Optional, Protocol, Tuple

from ..page.features import FeatureKind
from .catalog import FeatureAsset, FeatureCatalog
from .client import Box, MaaClient, RecoResult, Screenshot


class FeatureLocator(Protocol):
    """把逻辑特征键定位成屏幕矩形。"""

    def locate(self, key: str) -> Optional[Box]:
        ...

    def center(self, key: str) -> Optional[Tuple[int, int]]:
        ...


class MaaFeatureLocator:
    """通过 Maa OCR / 模板匹配定位特征。"""

    def __init__(
        self,
        client: MaaClient,
        catalog: FeatureCatalog,
        *,
        observer: object = None,
    ) -> None:
        self._client = client
        self._catalog = catalog
        self._observer = observer
        self._cache: Dict[str, Optional[Box]] = {}
        self._cache_screenshot: Optional[Screenshot] = None

    def invalidate(self) -> None:
        self._cache.clear()
        self._cache_screenshot = None

    def screenshot(self) -> Screenshot:
        if self._observer is not None:
            last = getattr(self._observer, "last_screenshot", None)
            if last is not None:
                return last
        return self._client.screencap()

    def locate(self, key: str) -> Optional[Box]:
        shot = self.screenshot()
        # A hit (or miss) belongs to one observed frame, never to the task.
        if shot is not self._cache_screenshot:
            self._cache.clear()
            self._cache_screenshot = shot
        if key in self._cache:
            return self._cache[key]
        asset = self._catalog.get(key)
        if asset is None:
            return None
        box = self._locate_asset(asset, shot)
        self._cache[key] = box
        return box

    def center(self, key: str) -> Optional[Tuple[int, int]]:
        box = self.locate(key)
        if box is None:
            return None
        x, y, w, h = box
        return x + w // 2, y + h // 2

    def _locate_asset(self, asset: FeatureAsset, shot: Screenshot) -> Optional[Box]:
        if asset.kind is FeatureKind.OCR:
            if not asset.text:
                return None
            params = {"expected": asset.text, "threshold": asset.threshold}
            if asset.roi:
                params["roi"] = list(asset.roi)
            result = self._client.recognize("OCR", params, shot)
        elif asset.kind in (FeatureKind.TEMPLATE, FeatureKind.ICON):
            if asset.template is None:
                return None
            params = {"template": str(asset.template), "threshold": asset.threshold}
            if asset.roi:
                params["roi"] = list(asset.roi)
            result = self._client.recognize("TemplateMatch", params, shot)
        else:
            return None
        return result.box if result.hit else None
