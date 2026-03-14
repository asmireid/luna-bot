import pytest
import discord
import asyncio
from cogs.paint import Paint
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_paint_command_queue(mock_bot, mock_ctx, mock_config, mocker):
    # Mock ComfyUIBackend
    mock_backend_class = mocker.patch('cogs.paint.ComfyUIBackend')
    mock_backend = mock_backend_class.return_value
    mock_backend.paint = AsyncMock(return_value=[{'data': b'fakeimage', 'ext': 'png'}])
    
    # Setup Config
    mock_config.paint_backend = 'comfyui'
    mock_config.paint_timeout = 60
    
    cog = Paint(mock_bot)
    
    # Stop the worker task so we can control execution
    cog.worker_task.cancel()
    
    await cog.paint(cog, mock_ctx, prompt="A beautiful sunset")
    
    assert cog.paint_queue.qsize() == 1
    item = await cog.paint_queue.get()
    assert item[1] == "A beautiful sunset"

@pytest.mark.asyncio
async def test_handle_paint(mock_bot, mock_ctx, mock_config, mocker):
    # Setup backend mock
    mock_backend_class = mocker.patch('cogs.paint.ComfyUIBackend')
    mock_backend = mock_backend_class.return_value
    mock_backend.paint = AsyncMock(return_value=[{'data': b'fakeimage', 'ext': 'png'}])
    
    mock_config.paint_backend = 'comfyui'
    
    cog = Paint(mock_bot)
    cog.backend = mock_backend
    
    await cog._handle_paint(mock_ctx, "A beautiful sunset", {"timeout": 60})
    
    mock_backend.paint.assert_called_once()
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert "Generated for:" in args[0]
    assert len(kwargs.get('files')) == 1

@pytest.mark.asyncio
async def test_list_paint_vars(mock_bot, mock_ctx, mock_config, mocker):
    mock_backend_class = mocker.patch('cogs.paint.ComfyUIBackend')
    mock_backend = mock_backend_class.return_value
    mock_backend.get_variables.return_value = {"var1": "default1"}
    
    mock_config.paint_backend = 'comfyui'
    
    cog = Paint(mock_bot)
    cog.backend = mock_backend
    
    await cog.list_paint_vars(cog, mock_ctx)
    
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    embed = kwargs.get('embed')
    assert embed.fields[0].name == "var1"
