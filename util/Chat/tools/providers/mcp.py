from __future__ import annotations

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
            qualified_name = f"{self.provider_id}.{remote_name}"
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

        if isinstance(content, list):
            flattened = []
            for item in content:
                if isinstance(item, dict):
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
            error=content_text if is_error else None,
            provider_id=self.provider_id,
            tool_name=qualified_name,
        )
