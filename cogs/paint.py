import random
import os
import io
from dataclasses import dataclass

# import discord
from discord.ext import commands

# from util.compy_api import prompt_to_image, load_workflow

# from novelai_api.ImagePreset import ImageModel, ImagePreset, ImageResolution, UCPreset, ImageSampler
# from util.boilerplate import API

# from transformers import GPT2Tokenizer, GPT2LMHeadModel, pipeline

# from pathlib import Path

# from utilities import *

# import logging


@dataclass
class Session:
    is_active: bool = False


painting = Session()
prompt_generating = Session()


class Paint(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # @commands.Cog.listener()
    # async def on_ready(self):
    #     print(f"{os.path.basename(__file__)} is ready.")

    # @commands.command(help="image generation with NAI V3")
    # async def paint(self, ctx, *, prompt):
    #     configs = Config()
    #     print(configs.width)
    #     if painting.is_active:
    #         await try_reply(ctx, configs.wait_message)
    #         return
        
    #     painting.is_active = True
    #     prompt = prompt.lower()

    #     images = prompt_to_image(load_workflow(configs.work_flow), 
    #                              configs.paint_model, 
    #                              prompt, 
    #                              configs.negative, 
    #                              configs.width, 
    #                              configs.height, 
    #                              configs.batch_size, 
    #                              configs.sampler_name, 
    #                              configs.steps, 
    #                              configs.seed)
    #     # for image in images:
    #     # await try_reply(ctx, "Painted!", file=discord.File(io.BytesIO(image['image_data']), filename=image['file_name']))
    #     files = [discord.File(io.BytesIO(image['image_data']), filename=image['file_name']) for image in images]
    #     print(files)
    #     # somehow capitalized letters stuck the image generation
    #     await try_reply(ctx, "Painted!", files=files)
    #     painting.is_active = False


async def setup(bot):
    await bot.add_cog(Paint(bot))
