import pytest
import asyncio
from cogs.chat import Chat

@pytest.mark.asyncio
async def test_chat_command(mock_bot, mock_ctx, mocker):
    # Setup dependencies
    mock_backend = mocker.MagicMock()
    
    # Mock chat_stream as an async generator
    async def mock_stream(message, **kwargs):
        # We don't yield status to keep it simple and match old test expectations of one reply
        yield {"type": "final", "content": "Hello from mocked backend!"}
    
    mock_backend.chat_stream = mock_stream
    
    # We patch create_backend in cogs.chat
    mocker.patch('cogs.chat.create_backend', return_value=mock_backend)
    
    # When bot.loop.create_task is called, we just create a standard asyncio task
    mock_bot.loop.create_task.side_effect = lambda coro: asyncio.create_task(coro)

    # Initialize the Cog
    cog = Chat(mock_bot)
    
    # Call the chat command callback directly to avoid discord.py Command wrapper complexities in tests
    await cog.chat.callback(cog, mock_ctx, message="Hi there!")
    
    # Let the queue processing task run
    await asyncio.sleep(0.1) 
    
    # Check that ctx.reply was called with the mock backend's response
    # (via utilities.try_reply)
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert args[0] == "Hello from mocked backend!"
