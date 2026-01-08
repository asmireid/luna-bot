import os
import asyncio
import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

class PaintBackend(ABC):
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    async def _generate(self, prompt: str, negative_prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Internal method to generate media based on the prompt.
        Must be implemented by subclasses.

        Args:
            prompt (str): The positive prompt.
            negative_prompt (Optional[str]): The negative prompt.
            **kwargs: Backend-specific arguments (e.g., width, height, seed, steps).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a generated item.
            Expected keys:
                - 'type': str ('image' or 'video')
                - 'data': bytes (The raw binary data)
                - 'ext': str (e.g., 'png', 'mp4', 'gif')
        """
        pass

    async def paint(self, prompt: str, negative_prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Generates media (images or videos) based on the provided prompts.
        Handles timeouts and logging.
        """
        print(f"Paint: generating for prompt: {prompt[:50]}...")

        timeout = kwargs.get('timeout')
        
        # Prepare kwargs for the internal generator, removing wrapper-specific args
        gen_kwargs = kwargs.copy()
        if 'timeout' in gen_kwargs:
            del gen_kwargs['timeout']

        if timeout:
            try:
                results = await asyncio.wait_for(self._generate(prompt, negative_prompt, **gen_kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"Paint: Backend timeout after {timeout}s.")
                raise
        else:
            results = await self._generate(prompt, negative_prompt, **gen_kwargs)

        return results

    def _load_resource(self, path: str) -> str:
        """
        Helper to load resource files (like workflow JSONs or style presets).
        """
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                warnings.warn(
                    f"Could not read resource file '{path}'. ({e})",
                    category=RuntimeWarning,
                    stacklevel=2,
                )
        return path
