import pytest
import os
import json
from util.Paint.comfyui import ComfyUIBackend
from unittest.mock import MagicMock, patch, mock_open

@pytest.fixture
def sample_workflow():
    return {
        "1": {
            "inputs": {"text": "positive prompt"},
            "_meta": {"title": "[VAR] PositivePrompt"}
        },
        "2": {
            "inputs": {"text": "negative prompt"},
            "_meta": {"title": "[VAR] NegativePrompt"}
        },
        "3": {
            "inputs": {"seed": 123},
            "_meta": {"title": "[OUTPUT:image]"}
        }
    }

def test_comfyui_init_and_workflow_parsing(sample_workflow, mocker):
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(sample_workflow)))
    
    backend = ComfyUIBackend(workflow_file="test_workflow.json")
    
    assert "PositivePrompt" in backend.workflow_vars
    assert "NegativePrompt" in backend.workflow_vars
    assert "3" in backend.output_nodes
    assert backend.output_nodes["3"] == "image"

def test_get_variables(sample_workflow, mocker):
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(sample_workflow)))
    
    backend = ComfyUIBackend(workflow_file="test_workflow.json")
    vars = backend.get_variables()
    
    assert vars["PositivePrompt"] == "positive prompt"
    assert vars["NegativePrompt"] == "negative prompt"

def test_list_workflows(mocker):
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.path.dirname', return_value="/mock/dir")
    mocker.patch('os.listdir', return_value=["wf1.json", "wf2.json", "not_a_wf.txt"])
    # Mock open for __init__
    mocker.patch('builtins.open', mock_open(read_data="{}"))
    
    backend = ComfyUIBackend(workflow_file="test_workflow.json")
    workflows = backend.list_workflows()
    
    assert "wf1.json" in workflows
    assert "wf2.json" in workflows
    assert "not_a_wf.txt" not in workflows

@pytest.mark.asyncio
async def test_generate_payload(sample_workflow, mocker):
    mocker.patch('os.path.exists', return_value=True)
    # Mock open for __init__ and for _generate_workflow_payload
    mocker.patch('builtins.open', mock_open(read_data=json.dumps(sample_workflow)))
    
    backend = ComfyUIBackend(workflow_file="test_workflow.json")
    
    payload = backend._generate_workflow_payload(
        "test_workflow.json", 
        PositivePrompt="new prompt", 
        NegativePrompt="new neg"
    )
    
    assert payload["1"]["inputs"]["text"] == "new prompt"
    assert payload["2"]["inputs"]["text"] == "new neg"
