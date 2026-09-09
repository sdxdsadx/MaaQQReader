"""逻辑特征 → 实际识别资源。

``FeatureKeys`` 里的值是**逻辑名/OCR 文案**；本模块把每个键解析成可执行的
识别资源（OCR 文案 / 模板文件 / ROI）。模板文件需要 QQR-6 / QQR-14 / QQR-15
用真实截图重新标定后再填入，未配置模板的特征会被安全跳过，不会盲点。
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from ..page.feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from ..page.features import FeatureKind

Box = Tuple[int, int, int, int]


@dataclass(frozen=True)
class FeatureAsset:
    """一个逻辑特征的识别资源。"""

    key: str
    kind: FeatureKind
    text: Optional[str] = None
    template: Optional[Path] = None
    roi: Optional[Box] = None
    threshold: float = 0.8
    description: str = ""

    @property
    def usable(self) -> bool:
        if self.kind is FeatureKind.OCR:
            return bool(self.text)
        if self.kind in (FeatureKind.TEMPLATE, FeatureKind.ICON):
            return self.template is not None
        return True

    def describe(self) -> str:
        if self.kind is FeatureKind.OCR:
            return f"{self.key} → OCR {self.text!r}"
        if self.template is not None:
            return f"{self.key} → {self.kind.value} {self.template.name}"
        return f"{self.key} → {self.kind.value}（模板未标定）"


@dataclass(frozen=True)
class FeatureCatalog:
    """逻辑特征键 → :class:`FeatureAsset`。"""

    assets: Mapping[str, FeatureAsset]

    def get(self, key: str) -> Optional[FeatureAsset]:
        return self.assets.get(key)

    def require(self, key: str) -> FeatureAsset:
        asset = self.get(key)
        if asset is None:
            raise KeyError(f"特征目录中没有 {key!r}")
        return asset

    def of_kind(self, kind: FeatureKind) -> Tuple[FeatureAsset, ...]:
        return tuple(a for a in self.assets.values() if a.kind is kind)

    @property
    def ocr_texts(self) -> Tuple[str, ...]:
        return tuple(
            a.text for a in self.assets.values() if a.kind is FeatureKind.OCR and a.text
        )

    @property
    def usable_templates(self) -> Tuple[FeatureAsset, ...]:
        return tuple(a for a in self.of_kind(FeatureKind.TEMPLATE) if a.usable)

    def with_templates(
        self, templates: Mapping[str, object], *, thresholds: Optional[Mapping[str, float]] = None
    ) -> "FeatureCatalog":
        """用真实模板路径/阈值覆盖目录（QQR-6/14/15 标定后调用）。"""
        updated: Dict[str, FeatureAsset] = {}
        for key, asset in self.assets.items():
            template = templates.get(key)
            if template is not None:
                asset = replace(asset, template=Path(template))
            if thresholds and key in thresholds:
                asset = replace(asset, threshold=float(thresholds[key]))
            updated[key] = asset
        return FeatureCatalog(updated)

    @classmethod
    def from_feature_keys(
        cls,
        keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
        *,
        templates: Optional[Mapping[str, object]] = None,
        thresholds: Optional[Mapping[str, float]] = None,
        rois: Optional[Mapping[str, object]] = None,
    ) -> "FeatureCatalog":
        """按值形态解析 ``FeatureKeys``：

        * 含 ``.`` 的值是逻辑键（模板/结构）；``*_package`` 是 App；
        * 其余非空字符串是 OCR 文案；``*_regex`` 只给识别器用，不做定位资源。
        * ``rois`` 可按字段名指定 OCR/模板 ROI（例如只在下半屏找「在线玩」）。
        """
        assets: Dict[str, FeatureAsset] = {}
        template_map = dict(templates or {})
        threshold_map = dict(thresholds or {})
        roi_map = dict(rois or {})

        def _roi(name: str):
            value = roi_map.get(name)
            return tuple(int(v) for v in value) if value is not None else None
        for field in fields(keys):
            name = field.name
            value = getattr(keys, name)
            if name.endswith("_regex"):
                continue
            if name.endswith("_package"):
                if value:
                    assets[name] = FeatureAsset(
                        key=name, kind=FeatureKind.CURRENT_APP, text=str(value)
                    )
                continue
            if not isinstance(value, str) or not value:
                continue
            if "." in value:
                if any(
                    token in name
                    for token in ("structure", "overlay", "marker", "bottom_nav", "hud", "surface")
                ):
                    kind = FeatureKind.STRUCTURE
                elif any(
                    token in name
                    for token in ("icon", "nav", "header", "close", "menu", "button", "entry", "skip")
                ):
                    kind = FeatureKind.ICON
                else:
                    kind = FeatureKind.TEMPLATE
                assets[name] = FeatureAsset(
                    key=name,
                    kind=kind,
                    text=value,
                    template=Path(template_map[name]) if name in template_map else None,
                    roi=_roi(name),
                    threshold=float(threshold_map.get(name, 0.8)),
                )
            else:
                assets[name] = FeatureAsset(
                    key=name,
                    kind=FeatureKind.OCR,
                    text=value,
                    roi=_roi(name),
                    threshold=float(threshold_map.get(name, 0.8)),
                )
        return cls(assets)

    def describe(self) -> str:
        lines = ["特征目录:"]
        for asset in self.assets.values():
            lines.append("  " + asset.describe())
        return "\n".join(lines)
