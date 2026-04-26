from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MCPTransport(ABC):
    @abstractmethod
    async def open(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def request(self, method: str, params: dict | None = None) -> Any:
        pass

    @abstractmethod
    async def notify(self, method: str, params: dict | None = None) -> None:
        pass
