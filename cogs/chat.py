import os
import logging
import asyncio
import mimetypes
from discord.ext import commands

from utilities import *
from util.Chat.backend_factory import create_backend

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_queue = asyncio.Queue()
        self.processing_task = None

        configs = Config()
        self.backend = create_backend(configs, configs.chat_backend, configs.model)
        print(f"Chat initialized with {configs.chat_backend.capitalize()} Backend.")

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
    async def chat(self, ctx, *, message=None):
        if message is None:
            message = ""

        images = []
        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                mime_type = attachment.content_type or mimetypes.guess_type(attachment.filename)[0]

                if mime_type and mime_type.startswith('image/'):
                    images.append({
                        'name': attachment.filename,
                        'data': await attachment.read(),
                        'mime_type': mime_type,
                    })

        params = {
            'temperature': Config().temperature, 
            'top_p': Config().top_p, 
            'top_k': Config().top_k,
            'max_new_tokens': Config().max_new_tokens,
            'author_name': ctx.author.nick or ctx.author.name,
            'images': images
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
                    response = await self.backend.chat(message, **params)
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
        if not self.backend.context and not self.backend.memory:
            await try_reply(ctx, f"No context yet.")
            return

        msg_embed = make_embed(ctx, title=f"{Config().bot_name}'s Chat", descr=f"Displaying stored context.")

        if self.backend.memory:
            msg_embed.add_field(name="Memory", value=trim_embed_value(self.backend.memory), inline=False)

        for m in self.backend.context:
            name = m.get("name") or m.get("role", "unknown")
            content = m.get("content", "")
            msg_embed.add_field(name=name, value=trim_embed_value(content), inline=False)

        await try_reply(ctx, msg_embed)

    def _switch_backend(self, backend_name: str, model: str = None):
        self.backend = create_backend(Config(), backend_name, model)


async def setup(bot):
    await bot.add_cog(Chat(bot))
