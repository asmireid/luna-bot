from __future__ import annotations

import aiohttp

from .base import MCPTransport


class MCPHTTPTransport(MCPTransport):
    def __init__(self, url: str, headers: dict | None = None) -> None:
        self.url = url
        self.headers = headers or {}
        self._request_id = 0
        self._session: aiohttp.ClientSession | None = None

    async def open(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=self.headers)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def request(self, method: str, params: dict | None = None):
        if self._session is None:
            raise RuntimeError("MCP HTTP transport is not open.")

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        async with self._session.post(self.url, json=payload) as response:
            response.raise_for_status()
            body = await response.json()
        if "error" in body:
            raise RuntimeError(f"MCP request failed: {body['error']}")
        return body.get("result", {})

    async def notify(self, method: str, params: dict | None = None) -> None:
        if self._session is None:
            raise RuntimeError("MCP HTTP transport is not open.")

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        async with self._session.post(self.url, json=payload) as response:
            response.raise_for_status()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
