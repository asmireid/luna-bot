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
        self.processing_task = None

        self.configs = Config()
        self._load_backend()

    def _load_backend(self):
        self.configs = Config()
        # Default to ComfyUI if not specified
        backend_name = getattr(self.configs, 'paint_backend', 'comfyui')
        print(f"Paint initialized with {backend_name.capitalize()} Backend.")
        
        if backend_name.lower() == 'comfyui':
            self.backend = ComfyUIBackend(
                server_address=getattr(self.configs, 'comfyui_url', "127.0.0.1:8188"),
                comfyui_workflow_folder=getattr(self.configs, 'comfyui_workflow_folder', "comfyui_workflows"),
                workflow_file=getattr(self.configs, 'workflow', "SDXL_ImageGen.json")
            )
        else:
            # Fallback or placeholder for other backends like NovelAI
            self.backend = ComfyUIBackend()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{os.path.basename(__file__)} is ready.")

    @commands.command(help="Generate image/video using configured backend")
    async def paint(self, ctx, *, prompt=None):
        if not prompt:
            await try_reply(ctx, "Please provide a prompt.")
            return

        prompt_text, kwargs = self._parse_prompt_and_kwargs(prompt)
        
        # Inject timeout from config if not present
        if 'timeout' not in kwargs:
            kwargs['timeout'] = getattr(self.configs, 'paint_timeout', 120)

        await self.paint_queue.put((ctx, prompt_text, kwargs))

        if self.processing_task is None or self.processing_task.done():
            self.processing_task = self.bot.loop.create_task(self.process_paint_queue())

    async def process_paint_queue(self):
        while not self.paint_queue.empty():
            ctx, prompt, kwargs = await self.paint_queue.get()

            try:
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

            except asyncio.TimeoutError:
                timeout_s = kwargs.get('timeout')
                await try_reply(ctx, f"Error: timed out after {timeout_s}s.")
            except Exception as e:
                logging.error(f"Paint Error: {repr(e)}", exc_info=True)
                await try_reply(ctx, f"Error: {str(e)}")

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

    @commands.command(aliases=['plv', 'pvars', 'paint_vars'], help="Lists available variables for the current paint backend")
    async def list_paint_vars(self, ctx):
        variables = self.backend.get_variables()
        if not variables:
            await try_reply(ctx, "No customizable variables found.")
            return

        msg_embed = make_embed(ctx, title="Paint Variables", descr="Available variables and their defaults:")
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
