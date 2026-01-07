from dataclasses import dataclass
from discord.ext import commands
from config.config import Config
from utilities import try_reply

class Paint(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(help="Generate image/video using configured backend")
    async def paint(self, ctx, *, prompt):
        pass

async def setup(bot):
    await bot.add_cog(Paint(bot))
