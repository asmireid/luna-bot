import pytest
import asyncio
from cogs.chat import Chat

@pytest.mark.asyncio
async def test_chat_command(mock_bot, mock_ctx, mocker):
    # Setup dependencies
    mock_backend = mocker.MagicMock()
    mock_backend.chat = mocker.AsyncMock(return_value="Hello from mocked backend!")
    
    # We patch create_backend in cogs.chat
    mocker.patch('cogs.chat.create_backend', return_value=mock_backend)
    
    # When bot.loop.create_task is called, we just create a standard asyncio task
    mock_bot.loop.create_task.side_effect = lambda coro: asyncio.create_task(coro)

    # Initialize the Cog
    cog = Chat(mock_bot)
    
    # Call the chat command
    await cog.chat(cog, mock_ctx, message="Hi there!")
    
    # Let the queue processing task run
    await asyncio.sleep(0.01) 
    
    # Check that the backend was called with correct parameters
    mock_backend.chat.assert_called_once_with(
        "Hi there!", 
        temperature=0.7, 
        top_p=0.9, 
        top_k=40, 
        max_new_tokens=512, 
        author_name="TestNick", 
        images=[], 
        timeout=30
    )
    
    # Check that ctx.reply was called with the mock backend's response
    # (via utilities.try_reply)
    mock_ctx.reply.assert_called_once()
    args, kwargs = mock_ctx.reply.call_args
    assert args[0] == "Hello from mocked backend!"
