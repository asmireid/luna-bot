from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

from ..discovery import discover_local_tool_modules
from ..provider import ToolProvider
from ..types import ProviderHealth, ToolExecutionContext, ToolResult, ToolSpec
from util.Media.types import AssetRef


class LocalToolProvider(ToolProvider):
    provider_type = "local"

    def __init__(self, provider_id: str = "local") -> None:
        self.provider_id = provider_id
        self._functions: dict[str, Callable[..., Any]] = {}
        self._specs: dict[str, ToolSpec] = {}
        self._discovered = False

    def register(self, name: str, description: str, parameters: dict | None):
        def decorator(func: Callable[..., Any]):
            qualified_name = f"{self.provider_id}-{name}"
            self._functions[qualified_name] = func
            self._specs[qualified_name] = ToolSpec(
                name=qualified_name,
                qualified_name=qualified_name,
                description=description,
                input_schema=parameters or {"type": "object", "properties": {}},
                provider_id=self.provider_id,
                provider_type="local",
                remote_name=name,
            )
            return func

        return decorator

    async def startup(self) -> None:
        if not self._discovered:
            discover_local_tool_modules()
            self._discovered = True

    async def shutdown(self) -> None:
        return None

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ok=True, message="Local tools available.")

    async def list_tools(self) -> list[ToolSpec]:
        await self.startup()
        return list(self._specs.values())

    async def call_tool(
        self,
        qualified_name: str,
        arguments: dict,
        ctx: ToolExecutionContext,
    ) -> ToolResult:
        func = self._functions.get(qualified_name)
        if not func:
            return ToolResult(
                ok=False,
                content=None,
                error=f"Tool '{qualified_name}' not found.",
                provider_id=self.provider_id,
                tool_name=qualified_name,
            )

        call_args = dict(arguments)
        sig = inspect.signature(func)
        for param_name in sig.parameters:
            if param_name == "tool_ctx" and param_name not in call_args:
                call_args[param_name] = ctx
            elif param_name == "execution_context" and param_name not in call_args:
                call_args[param_name] = ctx
            elif param_name == "asset_store" and ctx.asset_store is not None and param_name not in call_args:
                call_args[param_name] = ctx.asset_store
            elif ctx.raw_context:
                if param_name == "ctx" and ctx.discord_ctx is not None and param_name not in call_args:
                    call_args[param_name] = ctx.discord_ctx
                elif param_name in ctx.raw_context and param_name not in call_args:
                    call_args[param_name] = ctx.raw_context[param_name]

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**call_args)
            else:
                result = func(**call_args)
            return self._normalize_result(result, qualified_name)
        except Exception as exc:
            logging.error("Error executing tool '%s': %s", qualified_name, exc, exc_info=True)
            return ToolResult(
                ok=False,
                content=None,
                error=f"Error executing tool: {exc}",
                provider_id=self.provider_id,
                tool_name=qualified_name,
            )

    def _normalize_result(self, result: Any, qualified_name: str) -> ToolResult:
        if isinstance(result, ToolResult):
            if result.provider_id is None:
                result.provider_id = self.provider_id
            if result.tool_name is None:
                result.tool_name = qualified_name
            return result

        if isinstance(result, AssetRef):
            return ToolResult(
                ok=True,
                content=f"Stored file asset '{result.asset_id}'.",
                files=[result],
                provider_id=self.provider_id,
                tool_name=qualified_name,
            )

        if isinstance(result, list) and all(isinstance(item, AssetRef) for item in result):
            asset_refs = list(result)
            return ToolResult(
                ok=True,
                content=f"Stored {len(asset_refs)} file(s).",
                files=asset_refs,
                provider_id=self.provider_id,
                tool_name=qualified_name,
            )

        if isinstance(result, dict) and {"ok", "content", "error", "structured_content", "files", "metadata"} & set(result.keys()):
            return ToolResult(
                ok=result.get("ok", True),
                content=result.get("content"),
                structured_content=result.get("structured_content"),
                files=list(result.get("files", [])),
                error=result.get("error"),
                provider_id=self.provider_id,
                tool_name=qualified_name,
                metadata=dict(result.get("metadata", {})),
            )

        return ToolResult(
            ok=True,
            content=result,
            provider_id=self.provider_id,
            tool_name=qualified_name,
        )
