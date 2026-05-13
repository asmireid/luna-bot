from __future__ import annotations

import asyncio
import mimetypes
import os
import json
import time
import uuid
from pathlib import Path
from utilities import EnhancedJSONEncoder

from .types import AssetKind, AssetRef, StoredAsset


class AssetStore:
    def __init__(
        self,
        base_dir: str | None = "data/assets",
        default_ttl_seconds: int = 60 * 60 * 24 * 7, # Default to 1 week
    ) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.base_dir / "index.json"
        self.default_ttl_seconds = default_ttl_seconds
        self._assets: dict[str, StoredAsset] = {}
        self._lock = asyncio.Lock()
        self._load_index()

    def _load_index(self):
        if not self.index_path.exists():
            return
        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for asset_id, item in data.items():
                    ref = AssetRef(
                        asset_id=item['ref']['asset_id'],
                        kind=item['ref']['kind'],
                        mime_type=item['ref']['mime_type'],
                        filename=item['ref']['filename'],
                        source=item['ref']['source'],
                        metadata=item['ref']['metadata'],
                    )
                    stored = StoredAsset(
                        ref=ref,
                        created_at=item['created_at'],
                        last_accessed_at=item['last_accessed_at'],
                        size_bytes=item['size_bytes'],
                        metadata=item['metadata'],
                        path=item.get('path'),
                        pin_count=item.get('pin_count', 0)
                    )
                    # Verify file still exists on disk
                    if stored.path and os.path.exists(stored.path):
                        self._assets[asset_id] = stored
        except Exception as e:
            print(f"AssetStore: Failed to load index: {e}")

    def _save_index(self):
        data = {}
        for asset_id, asset in self._assets.items():
            data[asset_id] = {
                'ref': {
                    'asset_id': asset.ref.asset_id,
                    'kind': asset.ref.kind,
                    'mime_type': asset.ref.mime_type,
                    'filename': asset.ref.filename,
                    'source': asset.ref.source,
                    'metadata': asset.ref.metadata,
                },
                'created_at': asset.created_at,
                'last_accessed_at': asset.last_accessed_at,
                'size_bytes': asset.size_bytes,
                'metadata': asset.metadata,
                'path': asset.path,
                'pin_count': asset.pin_count
            }
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, cls=EnhancedJSONEncoder)
        except Exception as e:
            print(f"AssetStore: Failed to save index: {e}")

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

        # Always write to disk for persistence
        path = await asyncio.to_thread(self._write_asset_file, asset_id, filename, mime_type, data)

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
            path=path
        )

        async with self._lock:
            self._assets[asset_id] = stored
            self._save_index()

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
            self._save_index()

    async def unpin(self, asset_id: str) -> None:
        async with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                raise KeyError(f"Asset '{asset_id}' not found.")
            if asset.pin_count > 0:
                asset.pin_count -= 1
            asset.last_accessed_at = time.time()
            self._save_index()

    async def delete(self, asset_id: str, *, force: bool = False) -> bool:
        async with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                return False
            if asset.is_pinned() and not force:
                return False
            self._assets.pop(asset_id, None)
            self._save_index()

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
            
            if candidates:
                self._save_index()

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
