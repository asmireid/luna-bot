from __future__ import annotations

from ..mcp.client import MCPClient
from ..provider import ToolProvider
from ..types import ProviderHealth, ToolExecutionContext, ToolResult, ToolSpec
from util.Media.adapter import normalize_tool_result, resolve_tool_arguments


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

        resolved_arguments = await resolve_tool_arguments(arguments, ctx.asset_store, self.provider_type)
        response = await self.client.call_tool(spec.remote_name, resolved_arguments)
        normalized = await normalize_tool_result(
            {
                "ok": not bool(response.get("isError")),
                "content": response.get("content"),
                "structured_content": response if isinstance(response, dict) else None,
                "error": response.get("content") if bool(response.get("isError")) else None,
            },
            asset_store=ctx.asset_store,
            provider_id=self.provider_id,
            tool_name=qualified_name,
            source=f"{self.provider_id}:{spec.remote_name}",
        )
        if isinstance(normalized.content, list):
            flattened = []
            for item in normalized.content:
                if isinstance(item, dict) and "text" in item:
                    flattened.append(str(item["text"]))
                else:
                    flattened.append(str(item))
            normalized.content = "\n".join(flattened)
        elif normalized.content is None:
            normalized.content = ""
        elif not isinstance(normalized.content, str):
            normalized.content = str(normalized.content)
        if normalized.error is not None and not isinstance(normalized.error, str):
            normalized.error = str(normalized.error)
        return normalized
