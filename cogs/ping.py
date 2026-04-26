import os
import time
from discord.ext import commands

from utilities import *
from util.Chat.tools import chat_tools


@chat_tools.register(
    name="get_bot_latency",
    description="Gets the current latency/ping of the bot to the Discord server.",
    parameters=None
)
def get_bot_latency(ctx):
    latency = round(ctx.bot.latency * 1000)
    return f"The current bot latency is {latency} ms."


@chat_tools.register(
    name="get_server_time",
    description="Gets the server's current local time.",
    parameters=None
)
def get_server_time():
    server_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    return f"The server's current time is {server_time}."


@chat_tools.register(
    name="get_current_gmt_time",
    description="Gets the current GMT time based on the user's message.",
    parameters=None
)
def get_current_gmt_time(ctx):
    user_time = ctx.message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    return f"The current GMT time is {user_time}."


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{os.path.basename(__file__)} is ready.")

    @commands.command(help="returns the current latency of the bot")
    async def ping(self, ctx):
        try:
            descr = get_bot_latency(ctx)
            msg_embed = make_embed(ctx,
                                   title=f"{Config().bot_name}'s Clock",
                                   descr=descr)
            await try_reply(ctx, msg_embed)
        except Exception as e:
            print(f"An error occurred: {e}")

    @commands.command(help="returns the server's current time")
    async def server_time(self, ctx):
        try:
            descr = get_server_time()
            msg_embed = make_embed(ctx,
                                   title=f"{Config().bot_name}'s Clock",
                                   descr=descr)
            await try_reply(ctx, msg_embed)
        except Exception as e:
            print(f"An error occurred: {e}")

    @commands.command(help="returns the current time of user in GMT time")
    async def time(self, ctx):
        try:
            descr = get_current_gmt_time(ctx)
            msg_embed = make_embed(ctx,
                                   title=f"{Config().bot_name}'s Clock",
                                   descr=descr)
            await try_reply(ctx, msg_embed)
        except Exception as e:
            print(f"An error occurred: {e}")


async def setup(bot):
    await bot.add_cog(Ping(bot))

