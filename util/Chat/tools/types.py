from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from util.Media.types import AssetRef

ProviderType = Literal["local", "mcp"]
ToolVisibility = Literal["model", "host", "hidden"]


@dataclass(slots=True)
class ToolSpec:
    name: str
    qualified_name: str
    description: str
    input_schema: dict[str, Any]
    provider_id: str
    provider_type: ProviderType
    remote_name: str | None = None
    visibility: ToolVisibility = "model"
    enabled: bool = True
    supports_parallel: bool = False
    side_effecting: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_model_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema or {"type": "object", "properties": {}},
        }


@dataclass(slots=True)
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass(slots=True)
class ToolResult:
    ok: bool
    content: Any
    structured_content: dict[str, Any] | None = None
    files: list[AssetRef] = field(default_factory=list)
    error: str | None = None
    provider_id: str | None = None
    tool_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        if self.ok:
            return "" if self.content is None else str(self.content)
        return self.error or "Tool execution failed."


@dataclass(slots=True)
class ToolExecutionContext:
    discord_ctx: Any | None = None
    author_name: str | None = None
    request_id: str | None = None
    asset_store: Any | None = None
    raw_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderHealth:
    ok: bool
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
