from __future__ import annotations

from .transports.base import MCPTransport


class MCPClient:
    def __init__(self, transport: MCPTransport) -> None:
        self.transport = transport
        self.server_info: dict | None = None
        self.capabilities: dict = {}
        self.is_connected = False
        self._initialized = False

    async def connect(self) -> None:
        if self.is_connected:
            return
        await self.transport.open()
        self.is_connected = True
        await self.initialize()

    async def close(self) -> None:
        if not self.is_connected:
            return
        await self.transport.close()
        self.is_connected = False
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        response = await self.transport.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "luna-bot",
                    "version": "0.1.0",
                },
            },
        )
        self.server_info = response.get("serverInfo")
        self.capabilities = response.get("capabilities", {})
        await self.transport.notify("notifications/initialized", {})
        self._initialized = True

    async def list_tools(self) -> list[dict]:
        tools: list[dict] = []
        cursor = None
        while True:
            params = {"cursor": cursor} if cursor else {}
            response = await self.transport.request("tools/list", params)
            tools.extend(response.get("tools", []))
            cursor = response.get("nextCursor")
            if not cursor:
                break
        return tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        return await self.transport.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )

    async def list_resources(self) -> list[dict]:
        resources: list[dict] = []
        cursor = None
        while True:
            params = {"cursor": cursor} if cursor else {}
            response = await self.transport.request("resources/list", params)
            resources.extend(response.get("resources", []))
            cursor = response.get("nextCursor")
            if not cursor:
                break
        return resources

    async def read_resource(self, uri: str) -> dict:
        return await self.transport.request("resources/read", {"uri": uri})
