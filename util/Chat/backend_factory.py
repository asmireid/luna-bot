from typing import Optional
from config.config import Config
from util.Chat.gemini import GeminiBackend
from util.Chat.local import LocalBackend
from util.Chat.openai_like import OpenAILikeBackend

OPENAI_LIKE_NAMES = {"openai", "openai-like", "deepseek"}

def create_backend(configs: Config, backend_name: str, model: Optional[str] = None):
    name = (backend_name or "").lower().strip()
    model = (model or configs.model).strip()

    if name == "gemini":
        return GeminiBackend(
            api_key=configs.gemini_api_key,
            proxy_url=configs.gemini_proxy_url,
            model=model,
            system_prompt=configs.system_prompt,
            summarize_prompt=configs.summarize_prompt,
            context_limit=configs.context_limit,
            context_keep=configs.context_keep,
            bot_name=configs.bot_name,
        )

    if name in OPENAI_LIKE_NAMES:
        return OpenAILikeBackend(
            api_key=configs.openai_like_api_key,
            base_url=configs.openai_like_base_url,
            model=model,
            system_prompt=configs.system_prompt,
            summarize_prompt=configs.summarize_prompt,
            context_limit=configs.context_limit,
            context_keep=configs.context_keep,
            bot_name=configs.bot_name,
        )

    # default: local
    return LocalBackend(
        api_url=configs.local_api_url,
        system_prompt=configs.system_prompt,
        summarize_prompt=configs.summarize_prompt,
        context_limit=configs.context_limit,
        context_keep=configs.context_keep,
        bot_name=configs.bot_name,
    )
