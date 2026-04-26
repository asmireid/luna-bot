from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ProviderConfigType = Literal["local", "mcp"]


@dataclass(slots=True)
class ProviderConfig:
    id: str
    type: ProviderConfigType
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


def load_provider_configs(config_path: str | Path) -> list[ProviderConfig]:
    path = Path(config_path)
    if not path.exists():
        return [ProviderConfig(id="local", type="local", enabled=True, settings={})]

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    providers = []
    for item in payload.get("providers", []):
        providers.append(
            ProviderConfig(
                id=item["id"],
                type=item["type"],
                enabled=item.get("enabled", True),
                settings=item.get("settings", {}),
            )
        )

    if not any(provider.id == "local" for provider in providers):
        providers.insert(0, ProviderConfig(id="local", type="local", enabled=True, settings={}))

    return providers
