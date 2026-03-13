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
import requests
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
        self.comfyui_workflow_folder = comfyui_workflow_folder

        # Resolve workflow file path
        # 1. Try relative to the project root (CWD)
        # 2. Try relative to this file's directory (internal/default)
        root_path = os.path.join(os.getcwd(), comfyui_workflow_folder, workflow_file)
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), comfyui_workflow_folder, workflow_file)

        if os.path.exists(root_path):
            self.workflow_file = root_path
        elif os.path.exists(local_path):
            self.workflow_file = local_path
        else:
            self.workflow_file = workflow_file

        self.workflow_vars, self.output_nodes, self.file_nodes = self._get_workflow_details(self.workflow_file)

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
            return {}, {}, {}

        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)

        variables = {}
        output_nodes = {}
        file_nodes = {}
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
                file_match = re.match(r'^\[FILE:([^:]+):(\d+)\]', title or '', flags=re.IGNORECASE)
                if output_match:
                    output_nodes[id] = output_match.group(1).strip().lower() or 'any'
                elif file_match:
                    expected_type = file_match.group(1).strip().lower()
                    order = int(file_match.group(2).strip())
                    
                    keys = []
                    if node.get('inputs'):
                        for key in node['inputs'].keys():
                            keys.append(key)
                    file_nodes[order] = (id, keys, expected_type)
        return variables, output_nodes, file_nodes

    def get_variables(self) -> Dict[str, Any]:
        variables = {}
        for name, (_, _, vals) in self.workflow_vars.items():
            variables[name] = vals[0] if len(vals) == 1 else vals
        return variables

    def list_workflows(self) -> List[str]:
        directory = os.path.dirname(self.workflow_file)
        if not directory or not os.path.exists(directory):
            # Fallback search paths
            for base in [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]:
                test_dir = os.path.join(base, self.comfyui_workflow_folder)
                if os.path.exists(test_dir):
                    directory = test_dir
                    break

        if directory and os.path.exists(directory):
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

    def _upload_file(self, file_data: bytes, filename: str, fixed_name: str = None) -> str:
        """Uploads a file to ComfyUI's input directory."""
        url = f"http://{self.server_address}/upload/image"
        
        upload_name = fixed_name if fixed_name else filename
        ext = os.path.splitext(filename)[1].lower()
        content_type = 'application/octet-stream'
        if ext in ['.png', '.jpg', '.jpeg', '.webp']:
            content_type = f'image/{ext.lstrip(".")}'
            if ext == '.jpg': content_type = 'image/jpeg'
        elif ext in ['.mp4', '.webm', '.mov']:
            content_type = f'video/{ext.lstrip(".")}'
            
        files = {
            'image': (upload_name, file_data, content_type)
        }
        data = {'overwrite': 'true'}
        
        try:
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                res_json = response.json()
                return res_json.get('name', upload_name)
            else:
                print(f"ComfyUI File Upload Error: {response.text}")
                return upload_name
        except Exception as e:
            print(f"ComfyUI File Upload Exception: {e}")
            return upload_name

    def _process_input_files(self, prompt_workflow: Dict, input_files: List[Dict]) -> None:
        if not input_files or not hasattr(self, 'file_nodes') or not self.file_nodes:
            return
            
        for order, (node_id, keys, expected_type) in self.file_nodes.items():
            if order < len(input_files):
                file_info = input_files[order]
                ext = os.path.splitext(file_info['filename'])[1].lower()
                fixed_name = f"lunabot_input_{order}{ext}"
                uploaded_filename = self._upload_file(file_info['data'], file_info['filename'], fixed_name=fixed_name)
                
                if node_id in prompt_workflow and 'inputs' in prompt_workflow[node_id]:
                    node_inputs = prompt_workflow[node_id]['inputs']
                    target_key = None
                    if 'image' in node_inputs:
                        target_key = 'image'
                    elif 'video' in node_inputs:
                        target_key = 'video'
                    elif len(keys) > 0:
                        target_key = keys[0]
                        
                    if target_key:
                        prompt_workflow[node_id]['inputs'][target_key] = uploaded_filename

    def _generate_sync(self, prompt: str, negative_prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        gen_kwargs = kwargs.copy()

        # Map standard prompts to workflow variables if they exist
        if 'PositivePrompt' in self.workflow_vars:
            gen_kwargs['PositivePrompt'] = [prompt]
        if negative_prompt and 'NegativePrompt' in self.workflow_vars:
            gen_kwargs['NegativePrompt'] = [negative_prompt]

        prompt_workflow = self._generate_workflow_payload(self.workflow_file, **gen_kwargs)

        input_files = gen_kwargs.get('input_files', [])
        self._process_input_files(prompt_workflow, input_files)

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
