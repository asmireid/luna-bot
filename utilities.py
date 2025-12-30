import asyncio
import discord
from config.config import Config


async def try_delete_invocation(msg):
    if Config().delete_invocation:
        await msg.delete()


async def try_delete_confirmation(msg):
    if Config().delete_confirmation:
        await asyncio.sleep(Config().wait_time)
        await msg.delete()


async def try_reply(ctx, msg, file=None, **kwargs):
    await try_delete_invocation(ctx.message)
    if isinstance(msg, discord.Embed):
        return (
            await ctx.reply(embed=msg, file=file, mention_author=Config().mention_author, ephemeral=Config().ephemeral, **kwargs)
            if Config().reply
            else await ctx.send(embed=msg, file=file, ephemeral=Config().ephemeral, **kwargs))
    return (await ctx.reply(msg, file=file, mention_author=Config().mention_author, ephemeral=Config().ephemeral, **kwargs)
            if Config().reply
            else await ctx.send(msg, file=file, ephemeral=Config().ephemeral, **kwargs))


async def try_display_confirmation(ctx, msg):
    if Config().display_confirmation:
        conf = await try_reply(ctx, msg)
        await try_delete_confirmation(conf)


def make_embed(ctx, title, descr=None, color=discord.Color.dark_embed()) -> discord.Embed:
    msg_embed = discord.Embed(title=title, description=descr, color=color)
    msg_embed.set_author(name=f"Requested by {ctx.author.nick or ctx.author.name}",
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    msg_embed.set_footer(text=Config().embed_footer)

    return msg_embed

def trim_embed_value(text):
    # Discord embed field value length limit
    return text[:1021] + "..." if len(text) > 1024 else text