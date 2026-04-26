import pytest
from discord.ext import commands
from cogs.ping import Ping
import discord

@pytest.mark.asyncio
async def test_ping_command(mock_bot, mock_ctx, mocker):
    mock_bot.latency = 0.05  # 50ms
    cog = Ping(mock_bot)
    
    await cog.ping(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert isinstance(embed, discord.Embed)
    assert "50 ms" in embed.description

@pytest.mark.asyncio
async def test_server_time_command(mock_bot, mock_ctx):
    cog = Ping(mock_bot)
    
    await cog.server_time(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert isinstance(embed, discord.Embed)
    assert "The server's current time is" in embed.description

@pytest.mark.asyncio
async def test_time_command(mock_bot, mock_ctx):
    import datetime
    mock_ctx.message.created_at = datetime.datetime(2023, 1, 1, 12, 0, 0)
    cog = Ping(mock_bot)
    
    await cog.time(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert isinstance(embed, discord.Embed)
    assert "2023-01-01 12:00:00" in embed.description
