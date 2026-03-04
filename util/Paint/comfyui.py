import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
from PIL import Image
import os
import io
import uuid
import json
import urllib.request
import urllib.parse
import asyncio
import re
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
        self.workflow_vars, self.output_nodes = self._get_workflow_details(self.workflow_file)

    def _queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def _get_file(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def _get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def _get_outputs(self, ws, prompt):
        prompt_id = self._queue_prompt(prompt)['prompt_id']
        print(f"ComfyUI: Prompt ID {prompt_id}")

        outputs = {}
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

        history = self._get_history(prompt_id)
        history_outputs = history.get(prompt_id, {}).get('outputs', {})
        if not history_outputs:
            return outputs

        if self.output_nodes:
            node_ids = [node_id for node_id in self.output_nodes if node_id in history_outputs]
        else:
            node_ids = list(history_outputs.keys())

        for node_id in node_ids:
            node_output = history_outputs.get(node_id, {})
            expected_type = self.output_nodes.get(node_id, 'any')
            node_files = self._extract_files_from_node_output(node_output, expected_type)
            if node_files:
                outputs[node_id] = node_files

        # If tagged nodes were configured but produced no matches, fallback to scanning every output node.
        if not outputs and self.output_nodes:
            for node_id, node_output in history_outputs.items():
                node_files = self._extract_files_from_node_output(node_output, 'any')
                if node_files:
                    outputs[node_id] = node_files

        return outputs

    def _extract_files_from_node_output(self, node_output: Dict[str, Any], expected_type: str) -> List[Dict[str, Any]]:
        files = []
        for value in node_output.values():
            if not isinstance(value, list):
                continue

            for item in value:
                if not isinstance(item, dict):
                    continue
                if not all(k in item for k in ('filename', 'subfolder', 'type')):
                    continue

                filename = item['filename']
                ext = os.path.splitext(filename)[1].lstrip('.').lower()
                if not self._matches_expected_type(expected_type, ext):
                    continue

                file_data = self._get_file(filename, item['subfolder'], item['type'])
                final_ext = ext or self._infer_ext(file_data)
                files.append({
                    'data': file_data,
                    'ext': final_ext,
                    'type': self._media_type_from_ext(final_ext)
                })

        return files

    def _matches_expected_type(self, expected_type: str, ext: str) -> bool:
        expected = (expected_type or 'any').strip().lower()
        if expected in {'any', '*'}:
            return True
        if expected in {'image', 'images', 'img'}:
            return ext in {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff', 'heif', 'heic'}
        if expected in {'video', 'videos', 'vid', 'gif', 'gifs', 'animation', 'movie'}:
            return ext in {'mp4', 'webm', 'mov', 'mkv', 'avi', 'gif'}
        return ext == expected.lstrip('.')

    def _media_type_from_ext(self, ext: str) -> str:
        ext = (ext or '').lower()
        if ext in {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff', 'heif', 'heic'}:
            return 'image'
        if ext in {'mp4', 'webm', 'mov', 'mkv', 'avi', 'gif'}:
            return 'video'
        return 'file'

    def _infer_ext(self, file_data: bytes) -> str:
        try:
            img = Image.open(io.BytesIO(file_data))
            return (img.format or 'png').lower()
        except Exception:
            return 'bin'

    def _get_workflow_details(self, workflow_path):
        if not os.path.exists(workflow_path):
            print(f"Workflow file not found: {workflow_path}")
            return {}, {}

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        variables = {}
        output_nodes = {}
        for id, node in workflow_data.items():
            title = node.get('_meta', {'title': ''}).get('title', '')
            if title and title.startswith('[VAR]'):
                var_name = title.replace('[VAR]', '').strip()
                vals, keys = [], []
                if node.get('inputs'):
                    for key, val in node['inputs'].items():
                        vals.append(val)
                        keys.append(key)
                val = (id, keys, vals)
                variables[var_name] = val
            else:
                output_match = re.match(r'^\[OUTPUT:([^\]]+)\]', title or '', flags=re.IGNORECASE)
                if output_match:
                    output_nodes[id] = output_match.group(1).strip().lower() or 'any'
        return variables, output_nodes

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
            outputs_map = self._get_outputs(ws, prompt_workflow)
        finally:
            ws.close()

        results = []
        for _, files in outputs_map.items():
            for file in files:
                if file.get('data'):
                    results.append({
                        'type': file.get('type', 'file'),
                        'data': file.get('data'),
                        'ext': file.get('ext', 'bin')
                    })

        return results

    async def _generate(self, prompt: str, negative_prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._generate_sync, prompt, negative_prompt, **kwargs)
