import pytest
from util.Chat.gemini import GeminiBackend

@pytest.mark.asyncio
async def test_gemini_generate_reply(mocker):
    # Setup the mocks
    mock_client_class = mocker.patch('util.Chat.gemini.genai.Client')
    mock_client = mock_client_class.return_value
    
    mock_response = mocker.MagicMock()
    mock_response.text = "This is a mocked Gemini response"
    mock_client.models.generate_content.return_value = mock_response
    
    # Initialize backend
    backend = GeminiBackend(api_key="fake-key", context_limit=5)
    
    # Test generation
    context = [
        {"role": "user", "name": "User", "content": "Hello Gemini!"}
    ]
    
    # generate_content runs in an executor, but we mocked genai.Client
    reply = await backend._generate_reply(context=context, use_system_prompt=False)
    
    assert reply == "This is a mocked Gemini response"
    
    # Verify the mock was called correctly
    mock_client.models.generate_content.assert_called_once()
    
    args, kwargs = mock_client.models.generate_content.call_args
    assert kwargs['model'] == "gemini-3-flash-preview"
    assert len(kwargs['contents']) == 1  # 1 message in context
    
    # The part contains the text
    part_text = kwargs['contents'][0]['parts'][0].text
    assert "Hello Gemini!" in part_text
    assert "User" in part_text
