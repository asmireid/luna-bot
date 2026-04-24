from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from util.Chat.tools.types import ToolResult

from .types import AssetRef


RAW_MEDIA_DESCRIPTOR_KEYS = {"asset_id", "kind", "mime_type", "filename", "data", "path", "source", "metadata"}
ASSET_DESCRIPTOR_KEYS = {"asset_id", "kind", "mime_type", "filename", "source", "metadata"}


async def resolve_tool_arguments(arguments: dict[str, Any], asset_store: Any | None, provider_type: str) -> dict[str, Any]:
    if asset_store is None:
        return dict(arguments)
    return await _resolve_value(arguments, asset_store, provider_type)


async def normalize_tool_result(
    result: Any,
    *,
    asset_store: Any | None,
    provider_id: str | None = None,
    tool_name: str | None = None,
    source: str | None = None,
) -> ToolResult:
    normalized = await _normalize_result_value(result, asset_store=asset_store, source=source)

    if isinstance(normalized, ToolResult):
        if provider_id is not None and normalized.provider_id is None:
            normalized.provider_id = provider_id
        if tool_name is not None and normalized.tool_name is None:
            normalized.tool_name = tool_name
        return normalized

    refs, text_parts = await _extract_media_refs(normalized, asset_store=asset_store, source=source)
    if refs:
        text = "\n".join(text_parts) if text_parts else f"Stored {len(refs)} file(s)."
        return ToolResult(
            ok=True,
            content=text,
            files=refs,
            provider_id=provider_id,
            tool_name=tool_name,
        )

    return ToolResult(
        ok=True,
        content=normalized,
        provider_id=provider_id,
        tool_name=tool_name,
    )


async def _resolve_value(value: Any, asset_store: Any, provider_type: str) -> Any:
    if isinstance(value, AssetRef):
        return await _materialize_asset_ref(value, asset_store, provider_type)

    if isinstance(value, list):
        return [await _resolve_value(item, asset_store, provider_type) for item in value]

    if isinstance(value, dict):
        if _is_asset_descriptor(value):
            stored = await asset_store.get(value["asset_id"])
            ref = stored.ref if stored is not None else AssetRef(
                asset_id=value["asset_id"],
                kind=value.get("kind", "image" if str(value.get("mime_type", "")).startswith("image/") else "file"),
                mime_type=value.get("mime_type") or "application/octet-stream",
                filename=value.get("filename"),
                source=value.get("source"),
                metadata=dict(value.get("metadata", {})),
            )
            return await _materialize_asset_ref(ref, asset_store, provider_type)
        return {
            key: await _resolve_value(item, asset_store, provider_type)
            for key, item in value.items()
        }

    return value


async def _materialize_asset_ref(ref: AssetRef, asset_store: Any, provider_type: str) -> dict[str, Any]:
    data = await asset_store.resolve_bytes(ref.asset_id)

    if provider_type == "mcp":
        if ref.kind == "image" or ref.mime_type.startswith("image/"):
            payload = {
                "type": "image",
                "data": base64.b64encode(data).decode("utf-8"),
                "mimeType": ref.mime_type,
            }
            if ref.filename:
                payload["filename"] = ref.filename
            return payload

        resource = {
            "uri": f"asset://{ref.asset_id}",
            "mimeType": ref.mime_type,
            "blob": base64.b64encode(data).decode("utf-8"),
        }
        if ref.filename:
            resource["filename"] = ref.filename
        return {"type": "resource", "resource": resource}

    return {
        "asset_id": ref.asset_id,
        "kind": ref.kind,
        "mime_type": ref.mime_type,
        "filename": ref.filename,
        "data": data,
        "source": ref.source,
        "metadata": dict(ref.metadata),
    }


async def _normalize_result_value(result: Any, *, asset_store: Any | None, source: str | None) -> Any:
    if isinstance(result, ToolResult):
        refs, text_parts = await _extract_media_refs(result.files, asset_store=asset_store, source=source)
        result.files = refs
        content_refs, content_text = await _extract_media_refs(result.content, asset_store=asset_store, source=source)
        if content_refs:
            result.files.extend(content_refs)
            result.content = "\n".join(content_text) if content_text else f"Stored {len(content_refs)} file(s)."
        if text_parts and not result.content:
            result.content = "\n".join(text_parts)
        return result

    if isinstance(result, dict) and _looks_like_tool_result(result):
        refs, text_parts = await _extract_media_refs(result.get("files", []), asset_store=asset_store, source=source)
        content = result.get("content")
        content_refs, content_text = await _extract_media_refs(content, asset_store=asset_store, source=source)
        if content_refs:
            refs.extend(content_refs)
            content = "\n".join(content_text) if content_text else f"Stored {len(content_refs)} file(s)."
        if not content and text_parts:
            content = "\n".join(text_parts)
        return ToolResult(
            ok=result.get("ok", True),
            content=content,
            structured_content=result.get("structured_content"),
            files=refs,
            error=result.get("error"),
            metadata=dict(result.get("metadata", {})),
        )

    return result


async def _extract_media_refs(value: Any, *, asset_store: Any | None, source: str | None) -> tuple[list[AssetRef], list[str]]:
    if value is None:
        return [], []

    if isinstance(value, AssetRef):
        return [value], []

    if isinstance(value, (bytes, bytearray)):
        if asset_store is None:
            return [], [f"<{len(value)} bytes of binary data>"]
        ref = await asset_store.put_bytes(bytes(value), "application/octet-stream", kind="file", source=source)
        return [ref], [f"[Attached file: {ref.filename or ref.asset_id}]"]

    if isinstance(value, str):
        path = Path(value)
        if path.exists() and path.is_file():
            ref = await _store_path(path, asset_store=asset_store, source=source)
            if ref is not None:
                return [ref], [f"[Attached file: {ref.filename or ref.asset_id}]"]
        return [], [value]

    if isinstance(value, list):
        refs: list[AssetRef] = []
        text_parts: list[str] = []
        for item in value:
            item_refs, item_text = await _extract_media_refs(item, asset_store=asset_store, source=source)
            refs.extend(item_refs)
            text_parts.extend(item_text)
        return refs, text_parts

    if isinstance(value, dict):
        media_ref = await _store_media_dict(value, asset_store=asset_store, source=source)
        if media_ref is not None:
            return [media_ref], [f"[Attached file: {media_ref.filename or media_ref.asset_id}]"]
        if "text" in value:
            return [], [str(value["text"])]
        return [], [str(value)]

    return [], [str(value)]


async def _store_media_dict(value: dict[str, Any], *, asset_store: Any | None, source: str | None) -> AssetRef | None:
    if asset_store is None:
        return None

    if _is_local_raw_media(value):
        mime_type = value.get("mime_type") or "application/octet-stream"
        kind = value.get("kind", "image" if mime_type.startswith("image/") else "file")
        data = value.get("data")
        if data is None:
            path = value.get("path")
            if path:
                return await _store_path(Path(path), asset_store=asset_store, source=source)
            return None
        return await asset_store.put_bytes(
            bytes(data),
            mime_type,
            kind=kind,
            filename=value.get("filename"),
            source=value.get("source") or source,
            metadata=dict(value.get("metadata", {})),
        )

    item_type = value.get("type")
    if item_type == "image" and value.get("data"):
        data = base64.b64decode(value["data"])
        mime_type = value.get("mimeType") or "image/png"
        return await asset_store.put_bytes(
            data,
            mime_type,
            kind="image",
            filename=value.get("filename"),
            source=source,
        )

    if item_type == "resource":
        resource = value.get("resource") or {}
        blob = resource.get("blob")
        if blob is None:
            return None
        data = base64.b64decode(blob)
        mime_type = resource.get("mimeType") or "application/octet-stream"
        kind = "image" if mime_type.startswith("image/") else "file"
        return await asset_store.put_bytes(
            data,
            mime_type,
            kind=kind,
            filename=resource.get("filename"),
            source=resource.get("uri") or source,
            metadata={"uri": resource.get("uri")},
        )

    return None


async def _store_path(path: Path, *, asset_store: Any | None, source: str | None) -> AssetRef | None:
    if asset_store is None or not path.exists() or not path.is_file():
        return None
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    kind = "image" if mime_type.startswith("image/") else "file"
    data = path.read_bytes()
    return await asset_store.put_bytes(
        data,
        mime_type,
        kind=kind,
        filename=path.name,
        source=source or str(path),
    )


def _is_asset_descriptor(value: dict[str, Any]) -> bool:
    return "asset_id" in value and set(value.keys()).issubset(ASSET_DESCRIPTOR_KEYS)


def _is_local_raw_media(value: dict[str, Any]) -> bool:
    return (
        "data" in value
        and ("mime_type" in value or "kind" in value or "filename" in value)
        and set(value.keys()).issubset(RAW_MEDIA_DESCRIPTOR_KEYS)
    ) or (
        "path" in value
        and set(value.keys()).issubset(RAW_MEDIA_DESCRIPTOR_KEYS)
    )


def _looks_like_tool_result(value: dict[str, Any]) -> bool:
    return bool({"ok", "content", "error", "structured_content", "files", "metadata"} & set(value.keys()))
