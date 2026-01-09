import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
from PIL import Image
import os
import io
import uuid
import json
import urllib.request
import urllib.parse
import asyncio
from typing import List, Dict, Any, Optional
from .base import PaintBackend

class ComfyUIBackend(PaintBackend):
    def __init__(self, server_address="127.0.0.1:8188", 
                 comfyui_workflow_folder="comfyui_workflows", 
                 workflow_file="SDXL_ImageGen.json", 
                 **kwargs):
        super().__init__(**kwargs)
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        
        # Resolve workflow file path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        potential_path = os.path.join(current_dir, comfyui_workflow_folder, workflow_file)
        if os.path.exists(potential_path):
            workflow_file = potential_path
        
        self.workflow_file = workflow_file
        self.workflow_vars = self._get_workflow_variables(self.workflow_file)

    def _queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def _get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def _get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def _get_images(self, ws, prompt):
        prompt_id = self._queue_prompt(prompt)['prompt_id']
        print(f"ComfyUI: Prompt ID {prompt_id}")

        output_images = {}
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break  # Execution is done
            else:
                continue  # previews are binary data

        history = self._get_history(prompt_id)[prompt_id]
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = self._get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
                output_images[node_id] = images_output

        return output_images

    def _get_workflow_variables(self, workflow_path):
        if not os.path.exists(workflow_path):
            print(f"Workflow file not found: {workflow_path}")
            return {}

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)
        
        variables = {}
        for id, node in workflow_data.items():
            title = node.get('_meta', {'title': ''}).get('title', '')
            if title and title.startswith('[VAR]'):
                var_name = title.replace('[VAR]', '').strip()
                vals, keys = [], []
                if node.get("inputs"):
                    for key, val in node['inputs'].items():
                        vals.append(val)
                        keys.append(key)
                val = (id, keys, vals)
                variables[var_name] = val
        return variables

    def get_variables(self) -> Dict[str, Any]:
        variables = {}
        for name, (_, _, vals) in self.workflow_vars.items():
            variables[name] = vals[0] if len(vals) == 1 else vals
        return variables

    def list_workflows(self) -> List[str]:
        directory = os.path.dirname(self.workflow_file)
        if not directory or not os.path.exists(directory):
            directory = os.path.dirname(os.path.abspath(__file__))

        if os.path.exists(directory):
            return sorted([f for f in os.listdir(directory) if f.endswith('.json')])
        return []

    def _generate_workflow_payload(self, workflow_path, **kwargs):
        with open(workflow_path, "r", encoding="utf-8") as f:
            prompt_workflow = json.load(f)

        vars = self.workflow_vars

        for key, args in kwargs.items():
            if key in vars:
                id, keys, _ = vars[key]
                # Ensure args is a list/tuple for enumeration
                values_to_assign = args if isinstance(args, (list, tuple)) else [args]
                for i, arg in enumerate(values_to_assign):
                    if i < len(keys):
                        prompt_workflow[id]['inputs'][keys[i]] = arg

        return prompt_workflow

    def _generate_sync(self, prompt: str, negative_prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        gen_kwargs = kwargs.copy()
        
        # Map standard prompts to workflow variables if they exist
        if 'PositivePrompt' in self.workflow_vars:
            gen_kwargs['PositivePrompt'] = [prompt]
        if negative_prompt and 'NegativePrompt' in self.workflow_vars:
            gen_kwargs['NegativePrompt'] = [negative_prompt]

        prompt_workflow = self._generate_workflow_payload(self.workflow_file, **gen_kwargs)

        ws = websocket.WebSocket()
        try:
            ws.connect("ws://{}/ws?clientId={}".format(self.server_address, self.client_id))
            images_map = self._get_images(ws, prompt_workflow)
        finally:
            ws.close()

        results = []
        for node_id, images in images_map.items():
            for image_data in images:
                try:
                    img = Image.open(io.BytesIO(image_data))
                    ext = img.format.lower() if img.format else 'png'
                    results.append({
                        'type': 'image',
                        'data': image_data,
                        'ext': ext
                    })
                except Exception as e:
                    print(f"ComfyUI: Failed to process image: {e}")
        
        return results

    async def _generate(self, prompt: str, negative_prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._generate_sync, prompt, negative_prompt, **kwargs)
