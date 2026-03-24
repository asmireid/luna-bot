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
        configs = Config()
        params = {
            'temperature': configs.temperature, 
            'top_p': configs.top_p, 
            'top_k': configs.top_k,
            'max_new_tokens': configs.max_new_tokens,
            'author_name': ctx.author.nick or ctx.author.name,
            'images': images,
            'timeout': configs.timeout
        }
        # print(params)
        await self.chat_queue.put((message, params, ctx))
        
        if self.processing_task is None or self.processing_task.done():
            self.processing_task = self.bot.loop.create_task(self.process_chat_queue())

    async def process_chat_queue(self):
        while not self.chat_queue.empty():
            message, params, ctx = await self.chat_queue.get()
            params['ctx'] = ctx  # Inject ctx for tools that might need it
            
            status_msg = None
            tool_logs = ""

            try:
                async with ctx.typing():
                    async for update in self.backend.chat_stream(message, **params):
                        
                        if update["type"] == "status" and not status_msg:
                            # Send initial thinking message
                            status_msg = await try_reply(ctx, f"🤔 Thinking...")
                            
                        elif update["type"] == "tool_start":
                            tool_logs += f"\n🛠️ Using `{update['tool_name']}`..."
                            if status_msg:
                                await status_msg.edit(content=f"🤔 Thinking...{tool_logs}")
                                
                        elif update["type"] == "tool_end":
                            tool_logs += " ✅"
                            if status_msg:
                                await status_msg.edit(content=f"🤔 Thinking...{tool_logs}")
                                
                        elif update["type"] == "final":
                            final_text = update["content"]
                            # If we have tool logs, keep them above the final message. 
                            # Otherwise, just edit to the final text.
                            if tool_logs:
                                final_content = f"{tool_logs}\n\n{final_text}"
                            else:
                                final_content = final_text
                                
                            if status_msg:
                                await status_msg.edit(content=final_content)
                            else:
                                await try_reply(ctx, final_content)

            except asyncio.TimeoutError:
                timeout_s = params.get('timeout')
                error_msg = f"Error: timed out after {timeout_s}s (retried once)."
                if status_msg:
                    await status_msg.edit(content=error_msg)
                else:
                    await try_reply(ctx, error_msg)
            except Exception as e:
                logging.error(f"Chat Error: {repr(e)}", exc_info=True)
                error_msg = f"Error: {str(e)}"
                if status_msg:
                    await status_msg.edit(content=error_msg)
                else:
                    await try_reply(ctx, error_msg)

    @commands.command(aliases=['清空', "忘记一切"], help="clears chat history")
    async def reset_chat(self, ctx):
        self.backend.reset_context()
        self.backend.reset_memory()
        await try_reply(ctx, "阿巴阿巴！我忘记了一切！")

    @commands.command(help="displays the context")
    async def display_context(self, ctx):
        if not self.backend.context and not self.backend.memory:
            await try_reply(ctx, f"No context yet.")
            return

        msg_embed = make_embed(ctx, title=f"{Config().bot_name}'s Chat History", descr=f"Displaying stored context.")

        if self.backend.memory:
            msg_embed.add_field(name="🧠 Memory", value=trim_embed_value(self.backend.memory), inline=False)

        for m in self.backend.context:
            role = m.get('role')
            name = m.get('name') or role
            content = m.get('content', '')
            images = m.get('images', [])
            
            field_name = name
            field_value = content
            
            if role == 'tool_call':
                field_name = f"🛠️ Tool Call: {name}"
                field_value = f"Arguments: {content}"
            elif role == 'tool_result':
                field_name = f"✅ Tool Result: {name}"
                field_value = f"Output: {content}"
            elif role == 'model':
                field_name = f"🤖 {name}"
            elif role == 'user':
                field_name = f"👤 {name}"
            
            if images:
                image_info = ", ".join([img.get('name', 'image') for img in images])
                field_value = f"🖼️ [{len(images)} Image(s): {image_info}]\n{field_value}"
            
            if len(msg_embed.fields) >= 25:
                msg_embed.set_footer(text=f"{Config().embed_footer} | (Context truncated to last 25 items)")
                break
                
            msg_embed.add_field(name=field_name, value=trim_embed_value(field_value) if field_value else "(No content)", inline=False)

        await try_reply(ctx, msg_embed)

    def _switch_backend(self, backend_name: str, model: str = None):
        self.backend = create_backend(Config(), backend_name, model)


async def setup(bot):
    await bot.add_cog(Chat(bot))
