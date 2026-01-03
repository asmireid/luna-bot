import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
from PIL import Image
import os
import io
import uuid
import json
import urllib.request
import urllib.parse

server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break # Execution is done
        else:
            continue # Previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    current_node = ""
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['prompt_id'] == prompt_id:
                    if data['node'] is None:
                        break #Execution is done
                    else:
                        current_node = data['node']
        else:
            if current_node == 'save_image_websocket_node':
                images_output = output_images.get(current_node, [])
                images_output.append(out[8:])
                output_images[current_node] = images_output

    return output_images

def get_workflow_variables(workflow_path):
    if not os.path.exists(workflow_path):
        print(f"Workflow file not found: {workflow_path}")
        return {}

    with open(workflow_path, "r") as f:
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

def generate_workflow_payload(workflow_path, **kwargs):
    # Load defaults from the workflow file
    vars = get_workflow_variables(workflow_path)
    
    with open(workflow_path, "r") as f:
        prompt_workflow = json.load(f)

    for key, args in kwargs.items():
        if key in vars:
            id, keys, _ = vars[key]
            for i, arg in enumerate(args):
                prompt_workflow[id]['inputs'][keys[i]]=arg

    return prompt_workflow



if __name__ == "__main__":
    workflow_file = "SDXL_ImageGen.json"

    variables = get_workflow_variables(workflow_file)
    print(variables)

    # Example usage: Overwriting some values
    prompt = generate_workflow_payload(
        workflow_file, 
        PositivePrompt=[r"(azz0422:0.8), (ask \(askzy\):0.7), (ratatatat74:0.6),(tianliang duohe fangdongye:0.4), 1girl, solo, nian \(arknights\), flat color, shiny skin, very awa, masterpiece, best quality, newest, absurdres, year 2025,"]
    )
    
    if prompt:
        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
        
        print("Queueing prompt...")
        images = get_images(ws, prompt)
        
        ws.close() 
        for node_id in images:
            print(node_id)
            for image_data in images[node_id]:
                print(image_data)
                image = Image.open(io.BytesIO(image_data))
                image.save("test.png")
    else:
        print("Failed to load workflow.")
