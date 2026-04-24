from __future__ import annotations

import base64

from ..mcp.client import MCPClient
from ..provider import ToolProvider
from ..types import ProviderHealth, ToolExecutionContext, ToolResult, ToolSpec


class MCPToolProvider(ToolProvider):
    provider_type = "mcp"

    def __init__(self, provider_id: str, client: MCPClient) -> None:
        self.provider_id = provider_id
        self.client = client
        self._tool_cache: dict[str, ToolSpec] = {}

    async def startup(self) -> None:
        await self.client.connect()
        await self.refresh()

    async def shutdown(self) -> None:
        await self.client.close()

    async def refresh(self) -> None:
        remote_tools = await self.client.list_tools()
        refreshed: dict[str, ToolSpec] = {}
        for tool in remote_tools:
            remote_name = tool["name"]
            qualified_name = f"{self.provider_id}-{remote_name}"
            refreshed[qualified_name] = ToolSpec(
                name=qualified_name,
                qualified_name=qualified_name,
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {"type": "object", "properties": {}}),
                provider_id=self.provider_id,
                provider_type="mcp",
                remote_name=remote_name,
                metadata={"mcp_tool_name": remote_name},
            )
        self._tool_cache = refreshed

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ok=self.client.is_connected, message="Connected." if self.client.is_connected else "Disconnected.")

    async def list_tools(self) -> list[ToolSpec]:
        return list(self._tool_cache.values())

    async def call_tool(
        self,
        qualified_name: str,
        arguments: dict,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        spec = self._tool_cache.get(qualified_name)
        if not spec or not spec.remote_name:
            return ToolResult(
                ok=False,
                content=None,
                error=f"Tool '{qualified_name}' not found.",
                provider_id=self.provider_id,
                tool_name=qualified_name,
            )

        response = await self.client.call_tool(spec.remote_name, arguments)
        is_error = bool(response.get("isError"))
        content = response.get("content")

        files = []
        if isinstance(content, list):
            flattened = []
            for item in content:
                if isinstance(item, dict):
                    file_ref = await self._extract_asset_ref(item, ctx)
                    if file_ref is not None:
                        files.append(file_ref)
                        flattened.append(f"[Attached file: {file_ref.filename or file_ref.asset_id}]")
                        continue
                    text = item.get("text")
                    if text is not None:
                        flattened.append(text)
                    else:
                        flattened.append(str(item))
                else:
                    flattened.append(str(item))
            content_text = "\n".join(flattened)
        else:
            content_text = "" if content is None else str(content)

        return ToolResult(
            ok=not is_error,
            content=content_text,
            structured_content=response if isinstance(response, dict) else None,
            files=files,
            error=content_text if is_error else None,
            provider_id=self.provider_id,
            tool_name=qualified_name,
        )

    async def _extract_asset_ref(self, item: dict, ctx: ToolExecutionContext):
        asset_store = ctx.asset_store
        if asset_store is None:
            return None

        item_type = item.get("type")
        if item_type == "image" and item.get("data"):
            mime_type = item.get("mimeType") or "image/png"
            data = base64.b64decode(item["data"])
            return await asset_store.put_bytes(
                data,
                mime_type,
                kind="image",
                filename=item.get("filename"),
                source="mcp",
            )

        if item_type == "resource":
            resource = item.get("resource") or {}
            blob = resource.get("blob")
            if blob is None:
                return None
            mime_type = resource.get("mimeType") or "application/octet-stream"
            kind = "image" if mime_type.startswith("image/") else "file"
            data = base64.b64decode(blob)
            return await asset_store.put_bytes(
                data,
                mime_type,
                kind=kind,
                filename=resource.get("filename"),
                source=resource.get("uri") or "mcp",
                metadata={"uri": resource.get("uri")},
            )

        return None
