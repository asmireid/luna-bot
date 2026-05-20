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
    """
    Normalizes a tool result into a strict ToolResult object.
    Does NOT perform recursive deep-searching or filesystem guesswork on raw strings.
    Only explicit media representations (AssetRefs, bytes, explicit MCP dicts, explicit path dicts) are stored.
    """
    # 0. Check if the result ITSELF is a direct media representation
    ref = await _store_explicit_media(result, asset_store=asset_store, source=source)
    if ref is not None:
         return ToolResult(
             ok=True,
             content=f"Stored 1 file(s).",
             files=[ref],
             provider_id=provider_id,
             tool_name=tool_name,
         )

    # 1. Already a ToolResult
    if isinstance(result, ToolResult):
        normalized_files = []
        for file_item in result.files or []:
            ref = await _store_explicit_media(file_item, asset_store=asset_store, source=source)
            if ref:
                normalized_files.append(ref)
        result.files = normalized_files
        
        # Process MCP-style content array if present
        if isinstance(result.content, list):
            text_parts = []
            for item in result.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") in ("image", "resource"):
                        ref = await _store_explicit_media(item, asset_store=asset_store, source=source)
                        if ref:
                            result.files.append(ref)
                            text_parts.append(f"[Attached file: {ref.filename or ref.asset_id}]")
                elif isinstance(item, str):
                    text_parts.append(item)
                else:
                    text_parts.append(str(item))
            result.content = "\n".join(text_parts)
            
        if provider_id is not None and result.provider_id is None:
            result.provider_id = provider_id
        if tool_name is not None and result.tool_name is None:
            result.tool_name = tool_name
        return result

    # 2. Dictionary that looks like a ToolResult or MCP content
    if isinstance(result, dict):
        if "content" in result or "files" in result:
            content = result.get("content", "")
            files_raw = result.get("files", [])
            normalized_files = []
            
            for file_item in files_raw:
                ref = await _store_explicit_media(file_item, asset_store=asset_store, source=source)
                if ref:
                    normalized_files.append(ref)
                    
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                        elif item.get("type") in ("image", "resource"):
                            ref = await _store_explicit_media(item, asset_store=asset_store, source=source)
                            if ref:
                                normalized_files.append(ref)
                                text_parts.append(f"[Attached file: {ref.filename or ref.asset_id}]")
                    elif isinstance(item, str):
                        text_parts.append(item)
                    else:
                        text_parts.append(str(item))
                content = "\n".join(text_parts)
            elif not isinstance(content, str):
                content = str(content)
                
            return ToolResult(
                ok=result.get("ok", True),
                content=content,
                structured_content=result.get("structured_content"),
                files=normalized_files,
                error=result.get("error"),
                metadata=dict(result.get("metadata", {})),
                provider_id=provider_id,
                tool_name=tool_name,
            )
            
        if result.get("type") in ("image", "resource", "text"):
             result = [result] # Fall through to list handling

    # 3. List of items (MCP content or raw media)
    if isinstance(result, list):
        text_parts = []
        normalized_files = []
        for item in result:
            # First try to store it if it's an explicit media representation (dict or bytes)
            ref = await _store_explicit_media(item, asset_store=asset_store, source=source)
            if ref:
                normalized_files.append(ref)
                text_parts.append(f"[Attached file: {ref.filename or ref.asset_id}]")
                continue

            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                else:
                    text_parts.append(str(item))
            elif isinstance(item, str):
                text_parts.append(item)
            else:
                text_parts.append(str(item))
                
        if text_parts or normalized_files:
             return ToolResult(
                ok=True,
                content="\n".join(text_parts) if text_parts else f"Stored {len(normalized_files)} file(s).",
                files=normalized_files,
                provider_id=provider_id,
                tool_name=tool_name,
            )

    # 4. Everything else (including raw strings) is just text content
    return ToolResult(
        ok=True,
        content=str(result) if not isinstance(result, str) else result,
        provider_id=provider_id,
        tool_name=tool_name,
    )


async def _store_explicit_media(item: Any, *, asset_store: Any | None, source: str | None) -> AssetRef | None:
    """Stores media explicitly passed in standard formats, without guessing from raw strings."""
    if asset_store is None:
        return None
        
    if isinstance(item, AssetRef):
        return item
        
    if isinstance(item, (bytes, bytearray)):
        return await asset_store.put_bytes(bytes(item), "application/octet-stream", kind="file", source=source)
        
    if isinstance(item, dict):
        # 1. Local raw media dict with 'data'
        if "data" in item and ("mime_type" in item or "kind" in item or "filename" in item):
            mime_type = item.get("mime_type") or "application/octet-stream"
            kind = item.get("kind", "image" if mime_type.startswith("image/") else "file")
            data = item.get("data")
            if data is not None:
                return await asset_store.put_bytes(
                    bytes(data),
                    mime_type,
                    kind=kind,
                    filename=item.get("filename"),
                    source=item.get("source") or source,
                    metadata=dict(item.get("metadata", {})),
                )
                
        # 2. Local explicit 'path' dictionary
        if "path" in item:
            path = Path(item["path"])
            if path.exists() and path.is_file():
                mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                kind = "image" if mime_type.startswith("image/") else "file"
                data = path.read_bytes()
                return await asset_store.put_bytes(
                    data,
                    mime_type,
                    kind=kind,
                    filename=item.get("filename") or path.name,
                    source=item.get("source") or source or str(path),
                    metadata=dict(item.get("metadata", {})),
                )
            
        # 3. MCP Image
        if item.get("type") == "image" and item.get("data"):
            try:
                data = base64.b64decode(item["data"])
                mime_type = item.get("mimeType") or "image/png"
                return await asset_store.put_bytes(
                    data,
                    mime_type,
                    kind="image",
                    filename=item.get("filename"),
                    source=source,
                )
            except Exception:
                return None
                
        # 4. MCP Resource
        if item.get("type") == "resource" and "resource" in item:
            resource = item.get("resource", {})
            blob = resource.get("blob")
            if blob:
                try:
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
                except Exception:
                    pass
            
            text_data = resource.get("text")
            if text_data:
                try:
                    data = text_data.encode('utf-8')
                    mime_type = resource.get("mimeType") or "text/plain"
                    return await asset_store.put_bytes(
                        data,
                        mime_type,
                        kind="file",
                        filename=resource.get("filename"),
                        source=resource.get("uri") or source,
                        metadata={"uri": resource.get("uri")},
                    )
                except Exception:
                    pass

    return None


async def _resolve_value(value: Any, asset_store: Any, provider_type: str) -> Any:
    """Recursively resolves AssetRefs into raw data for the tool arguments."""
    if isinstance(value, AssetRef):
        return await _materialize_asset_ref(value, asset_store, provider_type)

    if isinstance(value, list):
        return [await _resolve_value(item, asset_store, provider_type) for item in value]

    if isinstance(value, str):
        # Auto-detect asset IDs passed as strings (e.g. "img_1234abcd")
        if value.startswith(("img_", "fil_")):
            stored = await asset_store.get(value)
            if stored:
                return await _materialize_asset_ref(stored.ref, asset_store, provider_type)

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


async def _materialize_asset_ref(ref: AssetRef, asset_store: Any, provider_type: str) -> str:
    data = await asset_store.resolve_bytes(ref.asset_id)
    b64_data = base64.b64encode(data).decode("utf-8")
    return f"data:{ref.mime_type};base64,{b64_data}"


def _is_asset_descriptor(value: dict[str, Any]) -> bool:
    return "asset_id" in value and set(value.keys()).issubset(ASSET_DESCRIPTOR_KEYS)
