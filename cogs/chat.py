import os
import logging
import asyncio
from discord.ext import commands

from utilities import *
from util.Chat.local import LocalBackend
from util.Chat.gemini import GeminiBackend


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend = GeminiBackend(
            api_key="gg-gcli-kf0L00pj2hUGCkdTmLIDVjEr_qEmvDi0E719sPnpXGE",
            proxy_url="https://gcli.ggchan.dev/",
            bot_name=Config().bot_name
        )
        self.chat_queue = asyncio.Queue()
        self.processing_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{os.path.basename(__file__)} is ready.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return  # ignore bot's own response

        if self.bot.user in message.mentions:
            ctx = await self.bot.get_context(message)
            await self.chat(ctx, message=message.content)

    @commands.command(aliases=['说话'], help="chats with user")
    async def chat(self, ctx, *, message):
        params = {
            'temperature': Config().temperature, 
            'top_p': Config().top_p, 
            'top_k': Config().top_k,
            'max_new_tokens': Config().max_new_tokens,
            'author_name': ctx.author.nick or ctx.author.name
        }
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

    @commands.command(name="switch_backend")
    async def switch_backend(self, ctx, backend_name: str):
        if backend_name.lower() == "gemini":
            # Note: You should move these keys to your Config
            self.backend = GeminiBackend(
                api_key="gg-gcli-kf0L00pj2hUGCkdTmLIDVjEr_qEmvDi0E719sPnpXGE",
                proxy_url="https://gcli.ggchan.dev/",
                bot_name=Config().bot_name
            )
            await try_reply(ctx, "Switched to Gemini Backend.")
        else:
            self.backend = LocalBackend(
                api_url=Config().api_url,
                system_prompt=Config().system_prompt,
                bot_name=Config().bot_name
            )
            await try_reply(ctx, "Switched to Local Backend.")

async def setup(bot):
    await bot.add_cog(Chat(bot))
