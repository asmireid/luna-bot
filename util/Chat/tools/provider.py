from __future__ import annotations

from abc import ABC, abstractmethod

from .types import ProviderHealth, ToolExecutionContext, ToolResult, ToolSpec


class ToolProvider(ABC):
    provider_id: str
    provider_type: str

    @abstractmethod
    async def startup(self) -> None:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass

    @abstractmethod
    async def health(self) -> ProviderHealth:
        pass

    @abstractmethod
    async def list_tools(self) -> list[ToolSpec]:
        pass

    @abstractmethod
    async def call_tool(
        self,
        qualified_name: str,
        arguments: dict,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        pass
