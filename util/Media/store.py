from __future__ import annotations

import asyncio
import mimetypes
import os
import tempfile
import time
import uuid
from pathlib import Path

from .types import AssetKind, AssetRef, StoredAsset


class AssetStore:
    def __init__(
        self,
        base_dir: str | None = None,
        memory_limit_bytes: int = 8 * 1024 * 1024,
        default_ttl_seconds: int = 60 * 60,
    ) -> None:
        runtime_dir = Path(base_dir or Path(tempfile.gettempdir()) / "luna-bot-assets")
        runtime_dir.mkdir(parents=True, exist_ok=True)

        self.base_dir = runtime_dir
        self.memory_limit_bytes = memory_limit_bytes
        self.default_ttl_seconds = default_ttl_seconds
        self._assets: dict[str, StoredAsset] = {}
        self._lock = asyncio.Lock()

    async def put_bytes(
        self,
        data: bytes,
        mime_type: str,
        *,
        kind: AssetKind = "image",
        filename: str | None = None,
        source: str | None = None,
        metadata: dict | None = None,
        asset_id: str | None = None,
    ) -> AssetRef:
        asset_id = asset_id or self._make_asset_id(kind)
        now = time.time()
        metadata = dict(metadata or {})

        ref = AssetRef(
            asset_id=asset_id,
            kind=kind,
            mime_type=mime_type,
            filename=filename,
            source=source,
            metadata=metadata.copy(),
        )
        stored = StoredAsset(
            ref=ref,
            created_at=now,
            last_accessed_at=now,
            size_bytes=len(data),
            metadata=metadata.copy(),
        )

        if len(data) <= self.memory_limit_bytes:
            stored.data = data
        else:
            stored.path = await asyncio.to_thread(self._write_asset_file, asset_id, filename, mime_type, data)

        async with self._lock:
            self._assets[asset_id] = stored

        return ref

    async def get(self, asset_id: str) -> StoredAsset | None:
        async with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                return None
            asset.last_accessed_at = time.time()
            return asset

    async def resolve_bytes(self, asset_id: str) -> bytes:
        asset = await self.get(asset_id)
        if asset is None:
            raise KeyError(f"Asset '{asset_id}' not found.")
        if asset.data is not None:
            return asset.data
        if asset.path is None:
            raise RuntimeError(f"Asset '{asset_id}' has no in-memory data or file path.")
        return await asyncio.to_thread(Path(asset.path).read_bytes)

    async def resolve_path(self, asset_id: str) -> str:
        asset = await self.get(asset_id)
        if asset is None:
            raise KeyError(f"Asset '{asset_id}' not found.")
        if asset.path is not None:
            return asset.path
        if asset.data is None:
            raise RuntimeError(f"Asset '{asset_id}' has no materializable content.")

        path = await asyncio.to_thread(
            self._write_asset_file,
            asset.ref.asset_id,
            asset.ref.filename,
            asset.ref.mime_type,
            asset.data,
        )
        async with self._lock:
            current = self._assets.get(asset_id)
            if current is not None:
                current.path = path
                current.last_accessed_at = time.time()
        return path

    async def pin(self, asset_id: str) -> None:
        async with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                raise KeyError(f"Asset '{asset_id}' not found.")
            asset.pin_count += 1
            asset.last_accessed_at = time.time()

    async def unpin(self, asset_id: str) -> None:
        async with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                raise KeyError(f"Asset '{asset_id}' not found.")
            if asset.pin_count > 0:
                asset.pin_count -= 1
            asset.last_accessed_at = time.time()

    async def delete(self, asset_id: str, *, force: bool = False) -> bool:
        async with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                return False
            if asset.is_pinned() and not force:
                return False
            self._assets.pop(asset_id, None)

        if asset.path:
            await asyncio.to_thread(self._remove_file, asset.path)
        return True

    async def prune(
        self,
        *,
        referenced_asset_ids: set[str] | None = None,
        older_than_seconds: int | None = None,
        include_pinned: bool = False,
    ) -> list[str]:
        referenced_asset_ids = referenced_asset_ids or set()
        cutoff_seconds = older_than_seconds if older_than_seconds is not None else self.default_ttl_seconds
        now = time.time()

        async with self._lock:
            candidates = []
            for asset_id, asset in self._assets.items():
                if asset_id in referenced_asset_ids:
                    continue
                if asset.is_pinned() and not include_pinned:
                    continue
                age = now - asset.last_accessed_at
                if age >= cutoff_seconds:
                    candidates.append((asset_id, asset.path))

            for asset_id, _ in candidates:
                self._assets.pop(asset_id, None)

        for _, path in candidates:
            if path:
                await asyncio.to_thread(self._remove_file, path)

        return [asset_id for asset_id, _ in candidates]

    async def contains(self, asset_id: str) -> bool:
        async with self._lock:
            return asset_id in self._assets

    def _make_asset_id(self, kind: AssetKind) -> str:
        prefix = {"image": "img", "file": "fil"}[kind]
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _write_asset_file(self, asset_id: str, filename: str | None, mime_type: str | None, data: bytes) -> str:
        suffix = self._guess_suffix(filename, mime_type)
        path = self.base_dir / f"{asset_id}{suffix}"
        path.write_bytes(data)
        return str(path)

    def _guess_suffix(self, filename: str | None, mime_type: str | None) -> str:
        if filename:
            suffix = Path(filename).suffix
            if suffix:
                return suffix
        guessed = mimetypes.guess_extension(mime_type or "")
        if guessed:
            return guessed
        return ".bin"

    def _remove_file(self, path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            return


def get_or_create_asset_store(bot, *, base_dir: str | None = None) -> AssetStore:
    asset_store = getattr(bot, "asset_store", None)
    if asset_store is None:
        asset_store = AssetStore(base_dir=base_dir)
        setattr(bot, "asset_store", asset_store)
    return asset_store
