import pytest
import discord
from cogs.control import Control
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_shutdown_command(mock_bot, mock_ctx, mocker):
    mock_bot.close = AsyncMock()
    cog = Control(mock_bot)
    
    # Mock Config().display_confirmation
    mock_conf = mocker.patch('cogs.control.Config').return_value
    mock_conf.display_confirmation = True
    
    await cog.shutdown(cog, mock_ctx)
    
    mock_bot.close.assert_called_once()
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_connect_command_success(mock_bot, mock_ctx, mocker):
    mock_ctx.author.voice = mocker.MagicMock()
    mock_ctx.author.voice.channel.name = "Test Voice"
    mock_ctx.author.voice.channel.connect = AsyncMock()
    mock_ctx.voice_client = None
    
    mock_conf = mocker.patch('cogs.control.Config').return_value
    mock_conf.display_confirmation = True
    
    cog = Control(mock_bot)
    await cog.connect(cog, mock_ctx)
    
    mock_ctx.author.voice.channel.connect.assert_called_once()
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_disconnect_command_success(mock_bot, mock_ctx, mocker):
    mock_ctx.voice_client = mocker.MagicMock()
    mock_ctx.voice_client.channel.name = "Test Voice"
    mock_ctx.voice_client.disconnect = AsyncMock()
    
    mock_conf = mocker.patch('cogs.control.Config').return_value
    mock_conf.display_confirmation = True
    
    cog = Control(mock_bot)
    await cog.disconnect(cog, mock_ctx)
    
    mock_ctx.voice_client.disconnect.assert_called_once()
    mock_ctx.reply.assert_called_once()
