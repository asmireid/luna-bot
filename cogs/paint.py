import os
import asyncio
import logging
import io
import discord
from discord.ext import commands

from utilities import *
from config.config import Config
from util.Paint.comfyui import ComfyUIBackend

class Paint(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.paint_queue = asyncio.Queue()

        self.configs = Config()
        self._load_backend()
        self.worker_task = asyncio.create_task(self._paint_worker())

    def _load_backend(self):
        # Default to ComfyUI if not specified
        backend_name = getattr(self.configs, 'paint_backend', 'comfyui')
        print(f"Paint initialized with {backend_name.capitalize()} Backend.")
        
        if backend_name.lower() == 'comfyui':
            self.backend = ComfyUIBackend(
                server_address=getattr(self.configs, 'comfyui_url', "127.0.0.1:8188"),
                comfyui_workflow_folder=getattr(self.configs, 'comfyui_workflow_folder', "comfyui_workflows"),
                workflow_file=getattr(self.configs, 'workflow', "SDXL_example.json")
            )
        else:
            # Fallback or placeholder for other backends like NovelAI
            raise NotImplementedError(f"Backend '{backend_name}' not implemented.")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{os.path.basename(__file__)} is ready.")

    def cog_unload(self):
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()

    @commands.command(help="Generate image/video using configured backend")
    async def paint(self, ctx, *, prompt=None):
        if not prompt and not ctx.message.attachments:
            await try_reply(ctx, "Please provide a prompt or an attachment.")
            return

        prompt_text, kwargs = self._parse_prompt_and_kwargs(prompt or "")
        
        # Inject timeout from config if not present
        if 'timeout' not in kwargs:
            kwargs['timeout'] = getattr(self.configs, 'paint_timeout', 600)

        # Handle file attachments
        if ctx.message.attachments:
            input_files = []
            for attachment in ctx.message.attachments:
                try:
                    file_data = await attachment.read()
                    input_files.append({
                        'filename': attachment.filename,
                        'data': file_data,
                        'content_type': attachment.content_type  # Discord Attachment uses content_type
                    })
                except discord.HTTPException as e:
                    logging.error(f"Failed to download attachment {attachment.filename}: {e}")
                    await try_reply(ctx, f"Failed to download attachment {attachment.filename}.")
                    return
            kwargs['input_files'] = input_files

        await self.paint_queue.put((ctx, prompt_text, kwargs))

    async def _paint_worker(self):
        try:
            while True:
                ctx, prompt, kwargs = await self.paint_queue.get()
                try:
                    await self._handle_paint(ctx, prompt, kwargs)
                except asyncio.TimeoutError:
                    timeout_s = kwargs.get('timeout')
                    await try_reply(ctx, f"Error: timed out after {timeout_s}s.")
                except Exception as e:
                    logging.error(f"Paint Error: {repr(e)}", exc_info=True)
                    await try_reply(ctx, f"Error: {str(e)}")
                finally:
                    self.paint_queue.task_done()
        except asyncio.CancelledError:
            logging.info("Paint worker task cancelled.")
            raise

    async def _handle_paint(self, ctx, prompt, kwargs):
        async with ctx.typing():
            results = await self.backend.paint(prompt, **kwargs)
            
            files = []
            for i, res in enumerate(results):
                data = res.get('data')
                ext = res.get('ext', 'png')
                if data:
                    files.append(discord.File(io.BytesIO(data), filename=f"generation_{i}.{ext}"))
            
            if files:
                await try_reply(ctx, f"Generated for: `{prompt[:50]}...`", files=files)
            else:
                await try_reply(ctx, "No output generated.")

    def _parse_prompt_and_kwargs(self, raw_input: str):
        parts = raw_input.split(' --')
        prompt = parts[0].strip()
        kwargs = {}
        
        for part in parts[1:]:
            part = part.strip()
            if not part: continue
            
            if ' ' in part:
                key, value = part.split(' ', 1)
                key = key.strip()
                value = value.strip()
                
                # Try to convert numeric values
                if value.isdigit():
                    value = int(value)
                else:
                    try:
                        value = float(value)
                    except ValueError:
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                kwargs[key] = value
            else:
                # Boolean flag
                kwargs[part] = True
        
        # Map common aliases
        if 'negative' in kwargs:
            kwargs['negative_prompt'] = kwargs.pop('negative')
        if 'neg' in kwargs:
            kwargs['negative_prompt'] = kwargs.pop('neg')
        return prompt, kwargs

    @commands.command(aliases=['plv', 'pvars', 'paint_vars'], help="Lists available variables and notes for the current paint backend")
    async def list_paint_vars(self, ctx):
        variables = self.backend.get_variables()
        notes = self.backend.get_workflow_notes()
        
        descr = "Available variables and their defaults:"
        if notes:
            descr = f"📝 {notes[:500]}\n\n{descr}"
        
        if not variables and not notes:
            await try_reply(ctx, "No customizable variables or notes found.")
            return

        msg_embed = make_embed(ctx, title="Paint Variables", descr=descr)
        for var, default in variables.items():
            msg_embed.add_field(name=var, value=f"{default}", inline=False)
        
        await try_reply(ctx, msg_embed)

    @commands.command(aliases=['plw', 'pwfs', 'paint_workflows'], help="Lists available workflows for the current paint backend")
    async def list_workflows(self, ctx):
        workflows = self.backend.list_workflows()
        if not workflows:
            await try_reply(ctx, "No workflows found.")
            return

        msg_embed = make_embed(ctx, title="Paint Workflows", descr="Available workflows:")
        msg_embed.add_field(name="Files", value="\n".join(workflows), inline=False)
        
        await try_reply(ctx, msg_embed)

async def setup(bot):
    await bot.add_cog(Paint(bot))
