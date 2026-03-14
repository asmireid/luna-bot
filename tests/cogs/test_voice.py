import pytest
import discord
import asyncio
from cogs.voice import Voice
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
async def test_ensure_voice_fail(mock_bot, mock_ctx, mocker):
    mock_ctx.voice_client = None
    cog = Voice(mock_bot)
    
    # Mock Config().display_confirmation
    mock_conf = mocker.patch('cogs.voice.Config').return_value
    mock_conf.display_confirmation = True
    
    result = await cog.ensure_voice(mock_ctx)
    assert result is False
    mock_ctx.reply.assert_called_once()
    assert mock_ctx.reply.call_args[0][0] == "I'm not connected to a voice channel."

@pytest.mark.asyncio
async def test_play_local_file(mock_bot, mock_ctx, mocker):
    mock_ctx.voice_client = mocker.MagicMock()
    mock_ctx.voice_client.is_playing.return_value = True
    
    mocker.patch('os.path.isfile', return_value=True)
    mocker.patch('os.path.isdir', return_value=False)
    
    mock_conf = mocker.patch('cogs.voice.Config').return_value
    mock_conf.display_confirmation = True
    
    cog = Voice(mock_bot)
    await cog.play_local(cog, mock_ctx, path="test.mp3")
    
    assert cog.audio_queue.qsize() == 1
    item = await cog.audio_queue.get()
    assert item == "test.mp3"
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_pause_command(mock_bot, mock_ctx, mocker):
    mock_ctx.voice_client = mocker.MagicMock()
    mock_ctx.voice_client.is_playing.return_value = True
    mock_ctx.voice_client.source.title = "Test Song"
    
    mock_conf = mocker.patch('cogs.voice.Config').return_value
    mock_conf.display_confirmation = True
    
    cog = Voice(mock_bot)
    await cog.pause(cog, mock_ctx)
    
    mock_ctx.voice_client.pause.assert_called_once()
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_resume_command(mock_bot, mock_ctx, mocker):
    mock_ctx.voice_client = mocker.MagicMock()
    mock_ctx.voice_client.is_paused.return_value = True
    mock_ctx.voice_client.source.title = "Test Song"
    
    mock_conf = mocker.patch('cogs.voice.Config').return_value
    mock_conf.display_confirmation = True
    
    cog = Voice(mock_bot)
    await cog.resume(cog, mock_ctx)
    
    mock_ctx.voice_client.resume.assert_called_once()
    mock_ctx.reply.assert_called_once()

@pytest.mark.asyncio
async def test_tts_command(mock_bot, mock_ctx, mocker):
    cog = Voice(mock_bot)
    
    # Mock Config().display_confirmation
    mock_conf = mocker.patch('cogs.voice.Config').return_value
    mock_conf.display_confirmation = True
    
    # Mock bot.loop.create_task to not actually run the processor
    mock_bot.loop.create_task = MagicMock()
    
    await cog.tts(cog, mock_ctx, text="Hello")
    
    assert cog.tts_queue.qsize() == 1
    mock_ctx.reply.assert_called_once()
    mock_bot.loop.create_task.assert_called_once()
