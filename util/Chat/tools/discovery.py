from __future__ import annotations

import importlib
import logging
import os


def discover_local_tool_modules() -> None:
    current_dir = os.path.dirname(__file__)
    tools_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "tools"))

    if not os.path.exists(tools_dir):
        logging.warning("Tools directory not found: %s", tools_dir)
        return

    for filename in os.listdir(tools_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"util.tools.{filename[:-3]}"
            try:
                importlib.import_module(module_name)
                logging.info("Loaded tool module: %s", module_name)
            except Exception as exc:
                logging.error("Failed to load tool module %s: %s", module_name, exc)
