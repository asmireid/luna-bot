import inspect
import asyncio
import logging
from typing import Callable, Dict, Any, Tuple, Optional

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: list[Dict[str, Any]] = []

    def register(self, name: str, description: str, parameters: dict):
        """
        Decorator to register a tool with the Chat backends.
        
        :param name: The name of the tool (must match the function name ideally, and be unique).
        :param description: A clear description of what the tool does for the LLM.
        :param parameters: A JSON schema dict defining the arguments.
                           Example: {"type": "object", "properties": {"loc": {"type": "string"}}}
        """
        def decorator(func: Callable):
            if name in self._tools:
                logging.warning(f"Tool '{name}' is being overwritten in the registry.")
            
            self._tools[name] = func
            
            # Ensure required fields are present for standard JSON schema formatting
            schema = {
                "name": name,
                "description": description,
                "parameters": parameters if parameters else {"type": "object", "properties": {}}
            }
            
            # Replace existing schema if overwriting, else append
            existing_index = next((i for i, s in enumerate(self._schemas) if s["name"] == name), -1)
            if existing_index >= 0:
                self._schemas[existing_index] = schema
            else:
                self._schemas.append(schema)
                
            return func
        return decorator

    def get_schemas(self) -> list[Dict[str, Any]]:
        """Returns the list of registered tool schemas to pass to the LLM API."""
        return self._schemas

    def get_tool(self, name: str) -> Optional[Callable]:
        """Retrieves the function reference for a given tool name."""
        return self._tools.get(name)

    async def execute_tool(self, name: str, kwargs: dict, context_kwargs: dict = None) -> Any:
        """
        Executes a registered tool.
        
        :param name: The name of the tool to execute.
        :param kwargs: The arguments provided by the LLM.
        :param context_kwargs: Optional extra arguments to inject (like `ctx` or `bot`) 
                               that the LLM doesn't provide but the function might need.
        """
        func = self.get_tool(name)
        if not func:
            raise ValueError(f"Tool '{name}' not found in registry.")

        # Merge LLM args with backend context args if the tool signature requires them
        call_args = kwargs.copy()
        if context_kwargs:
            sig = inspect.signature(func)
            for param_name in sig.parameters:
                if param_name in context_kwargs and param_name not in call_args:
                    call_args[param_name] = context_kwargs[param_name]

        try:
            if inspect.iscoroutinefunction(func):
                return await func(**call_args)
            else:
                return func(**call_args)
        except Exception as e:
            logging.error(f"Error executing tool '{name}': {e}", exc_info=True)
            return f"Error executing tool: {str(e)}"

# Global instance to be imported and used across the application
chat_tools = ToolRegistry()
