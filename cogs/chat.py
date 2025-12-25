import os
import logging
import asyncio
from discord.ext import commands
from config.config import Config

from utilities import *
from util.Chat.local import LocalBackend
from util.Chat.gemini import GeminiBackend
from util.Chat.openai_like import OpenAILikeBackend


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_queue = asyncio.Queue()
        self.processing_task = None

        backend = Config().chat_backend.lower()
        if backend == "gemini":
            self.backend = GeminiBackend(
                api_key=Config().gemini_api_key,
                proxy_url=Config().gemini_proxy_url,
                model=Config().model,
                system_prompt=Config().system_prompt,
                context_limit=Config().context_limit,
                bot_name=Config().bot_name
            )
            print("Chat initialized with Gemini Backend.")
        elif backend == "openai" or "openai-like" or "deepseek":
            self.backend = OpenAILikeBackend(
                api_key=Config().openai_like_api_key,
                base_url=Config().openai_like_base_url,
                model=Config().model,
                system_prompt=Config().system_prompt,
                context_limit=Config().context_limit,
                bot_name=Config().bot_name
            )
            print("Chat initialized with OpenAI-like Backend.")
        else:
            self.backend = LocalBackend(
                api_url=Config().local_api_url,
                system_prompt=Config().system_prompt,
                context_limit=Config().context_limit,
                bot_name=Config().bot_name
            )
            print("Chat initialized with Local Backend.")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{os.path.basename(__file__)} is ready.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return  # ignore bot's own response

        if self.bot.user in message.mentions:
            ctx = await self.bot.get_context(message)
            cleaned = message.clean_content.replace(f"@{Config().bot_name}", "").strip()
            await self.chat(ctx, message=cleaned)

    @commands.command(aliases=['说话'], help="chats with user")
    async def chat(self, ctx, *, message):
        params = {
            'temperature': Config().temperature, 
            'top_p': Config().top_p, 
            'top_k': Config().top_k,
            'max_new_tokens': Config().max_new_tokens,
            'author_name': ctx.author.nick or ctx.author.name
        }
        # print(params)
        await self.chat_queue.put((message, params, ctx))
        
        if self.processing_task is None or self.processing_task.done():
            self.processing_task = self.bot.loop.create_task(self.process_chat_queue())

    async def process_chat_queue(self):
        while not self.chat_queue.empty():
            message, params, ctx = await self.chat_queue.get()
            try:
                async with ctx.typing():
                    response = await self.backend.generate_reply(message, **params)
                    await try_reply(ctx, response)
            except Exception as e:
                logging.error(f"Chat Error: {repr(e)}", exc_info=True)
                await try_reply(ctx, f"Error: {str(e)}")

    @commands.command(aliases=['清空', "忘记一切"], help="clears chat history")
    async def reset_chat(self, ctx):
        self.backend.reset_context()
        await try_reply(ctx, "阿巴阿巴! 我忘记了一切!")

    @commands.command(help="displays the context")
    async def display_context(self, ctx):
        if not self.backend.context:
            await try_reply(ctx, f"No context yet.")
            return

        msg_embed = make_embed(ctx, title=f"{Config().bot_name}'s Chat", descr=f"Displaying stored context.")
        for m in self.backend.context:
            name = m.get("name") or m.get("role", "unknown")
            content = m.get("content", "")
            # Discord embed field value length limit
            if len(content) > 1024:
                content = content[:1021] + "..."
            msg_embed.add_field(name=name, value=content, inline=False)

        await try_reply(ctx, msg_embed)

    @commands.command(name="switch_backend")
    async def switch_backend(self, ctx, backend_name: str):
        name = backend_name.lower()

        if name == "gemini":
            self.backend = GeminiBackend(
                api_key=Config().gemini_api_key,
                proxy_url=Config().gemini_proxy_url,
                model=Config().model,
                system_prompt=Config().system_prompt,
                context_limit=Config().context_limit,
                bot_name=Config().bot_name
            )
            await try_reply(ctx, "Switched to Gemini Backend.")

        elif name == "openai" or "openai-like" or "deepseek":
            self.backend = OpenAILikeBackend(
                api_key=Config().openai_like_api_key,
                base_url=Config().openai_like_base_url,
                model=Config().model,
                system_prompt=Config().system_prompt,
                context_limit=Config().context_limit,
                bot_name=Config().bot_name
            )
            await try_reply(ctx, "Switched to OpenAI-like Backend.")

        else:
            self.backend = LocalBackend(
                api_url=Config().local_api_url,
                system_prompt=Config().system_prompt,
                context_limit=Config().context_limit,
                bot_name=Config().bot_name
            )
            await try_reply(ctx, "Switched to Local Backend.")


async def setup(bot):
    await bot.add_cog(Chat(bot))
