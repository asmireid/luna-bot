import asyncio
import os
import discord
import time
import platform
import argparse
from discord.ext import commands
from config.config import Config
from util.Media import get_or_create_asset_store

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=Config().command_prefix.split(' '), intents=intents)


# bot.remove_command('help')


async def update():
    for guild in bot.guilds:
        server = bot.get_guild(guild.id)
        bot_member = server.get_member(bot.user.id)
        await bot_member.edit(nick=Config().bot_name)

    activity = Config().bot_activity
    await bot.change_presence(activity=discord.CustomActivity(name=activity))


@bot.event
async def on_ready():
    time_prefix = time.strftime('%H:%M:%S', time.localtime())
    print(f"{time_prefix} Logged in as {bot.user.name}")
    print(f"{time_prefix} Bot ID {bot.user.id}")
    print(f"{time_prefix} Discord.py Version {discord.__version__}")
    print(f"{time_prefix} Python Version {platform.python_version()}")
    get_or_create_asset_store(bot)
    await update()


async def load():
    excluded_files = []
    parser = argparse.ArgumentParser(description="Load bot extensions")
    parser.add_argument("-i", "--ignore", nargs="+", help="Exclude specific files")
    args = parser.parse_args()

    if args.ignore:
        excluded_files = args.ignore

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename[:-3] not in excluded_files:
            await bot.load_extension(f"cogs.{filename[:-3]}")


async def main():
    async with bot:
        await load()
        await bot.start(Config().bot_token)


asyncio.run(main())
