from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .config import load_provider_configs
from .provider import ToolProvider
from .providers.local import LocalToolProvider
from .providers.registry import ProviderFactory
from .types import ToolExecutionContext, ToolResult, ToolSpec


class ToolManager:
    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path or str(Path("config") / "tool_providers.json")
        self._providers: dict[str, ToolProvider] = {}
        self._tool_specs: dict[str, ToolSpec] = {}
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._local_provider = LocalToolProvider(provider_id="local")
        self._providers[self._local_provider.provider_id] = self._local_provider

    def register(self, name: str, description: str, parameters: dict | None):
        return self._local_provider.register(name=name, description=description, parameters=parameters)

    async def ensure_ready(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return
            await self.load_from_config()
            self._initialized = True

    async def load_from_config(self) -> None:
        configs = load_provider_configs(self.config_path)
        next_providers: dict[str, ToolProvider] = {
            self._local_provider.provider_id: self._local_provider,
        }

        for config in configs:
            if not config.enabled:
                continue
            if config.type == "local":
                continue
            provider = ProviderFactory.build(config)
            next_providers[provider.provider_id] = provider

        self._providers = next_providers

        for provider in self._providers.values():
            await provider.startup()

        await self.refresh_tools()

    async def shutdown(self) -> None:
        for provider in self._providers.values():
            await provider.shutdown()
        self._initialized = False

    async def add_provider(self, provider: ToolProvider) -> None:
        self._providers[provider.provider_id] = provider
        await provider.startup()
        await self.refresh_tools()

    async def remove_provider(self, provider_id: str) -> None:
        provider = self._providers.get(provider_id)
        if not provider or provider_id == self._local_provider.provider_id:
            return
        await provider.shutdown()
        self._providers.pop(provider_id, None)
        await self.refresh_tools()

    async def refresh_tools(self) -> None:
        refreshed: dict[str, ToolSpec] = {}
        for provider in self._providers.values():
            for spec in await provider.list_tools():
                if spec.name in refreshed:
                    raise ValueError(f"Duplicate tool name registered: {spec.name}")
                refreshed[spec.name] = spec
        self._tool_specs = refreshed

    def get_schemas(self) -> list[dict]:
        return [
            spec.to_model_schema()
            for spec in self._tool_specs.values()
            if spec.enabled and spec.visibility == "model"
        ]

    def get_tool(self, name: str) -> ToolSpec | None:
        return self._tool_specs.get(name)

    async def execute_tool(self, name: str, kwargs: dict, context_kwargs: dict | None = None) -> ToolResult:
        await self.ensure_ready()

        spec = self.get_tool(name)
        if not spec:
            return ToolResult(ok=False, content=None, error=f"Tool '{name}' not found.", tool_name=name)

        provider = self._providers.get(spec.provider_id)
        if not provider:
            return ToolResult(
                ok=False,
                content=None,
                error=f"Provider '{spec.provider_id}' is not available.",
                provider_id=spec.provider_id,
                tool_name=name,
            )

        context_kwargs = context_kwargs or {}
        discord_ctx = context_kwargs.get("ctx")
        asset_store = context_kwargs.get("asset_store")
        if asset_store is None and discord_ctx is not None:
            asset_store = getattr(getattr(discord_ctx, "bot", None), "asset_store", None)
        execution_context = ToolExecutionContext(
            discord_ctx=discord_ctx,
            author_name=context_kwargs.get("author_name"),
            asset_store=asset_store,
            raw_context=context_kwargs,
        )
        return await provider.call_tool(spec.qualified_name, kwargs, execution_context)

    async def health_report(self) -> dict[str, dict]:
        report: dict[str, dict] = {}
        for provider_id, provider in self._providers.items():
            try:
                health = await provider.health()
                report[provider_id] = {
                    "ok": health.ok,
                    "message": health.message,
                    "details": health.details,
                }
            except Exception as exc:
                logging.error("Health check failed for provider '%s': %s", provider_id, exc, exc_info=True)
                report[provider_id] = {
                    "ok": False,
                    "message": str(exc),
                    "details": {},
                }
        return report
