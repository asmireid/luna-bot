from __future__ import annotations

from ..config import ProviderConfig
from ..mcp.client import MCPClient
from ..mcp.transports.http import MCPHTTPTransport
from ..mcp.transports.stdio import MCPStdioTransport
from .local import LocalToolProvider
from .mcp import MCPToolProvider


class ProviderFactory:
    @staticmethod
    def build(config: ProviderConfig):
        if config.type == "local":
            return LocalToolProvider(provider_id=config.id)

        if config.type != "mcp":
            raise ValueError(f"Unsupported provider type: {config.type}")

        settings = config.settings
        transport_type = settings.get("transport", "stdio")

        if transport_type == "stdio":
            command = settings.get("command")
            if not command:
                raise ValueError(f"MCP provider '{config.id}' is missing a stdio command.")
            transport = MCPStdioTransport(
                command=command,
                env=settings.get("env"),
                cwd=settings.get("cwd"),
            )
        elif transport_type == "http":
            url = settings.get("url")
            if not url:
                raise ValueError(f"MCP provider '{config.id}' is missing an HTTP url.")
            transport = MCPHTTPTransport(
                url=url,
                headers=settings.get("headers"),
            )
        else:
            raise ValueError(f"Unsupported MCP transport: {transport_type}")

        return MCPToolProvider(provider_id=config.id, client=MCPClient(transport=transport))
