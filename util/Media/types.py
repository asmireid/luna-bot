from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AssetKind = Literal["image", "file"]


@dataclass(slots=True)
class AssetRef:
    asset_id: str
    kind: AssetKind
    mime_type: str
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StoredAsset:
    ref: AssetRef
    created_at: float
    last_accessed_at: float
    data: bytes | None = None
    path: str | None = None
    size_bytes: int = 0
    pin_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_pinned(self) -> bool:
        return self.pin_count > 0
