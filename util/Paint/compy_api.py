# import websocket
# import uuid
# import json
# import urllib.request, urllib.parse
# import os
# from PIL import Image
# import io
# import random

# def open_websocket_connection():
#     server_address='127.0.0.1:8188'
#     client_id=str(uuid.uuid4())
#     ws = websocket.WebSocket()
#     ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
#     return ws, server_address, client_id

# def queue_prompt(prompt, client_id, server_address):
#     p = {"prompt": prompt, "client_id": client_id}
#     headers = {'Content-Type': 'application/json'}
#     data = json.dumps(p).encode('utf-8')
#     req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data, headers=headers)
#     return json.loads(urllib.request.urlopen(req).read())

# def get_history(prompt_id, server_address):
#     with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
#         return json.loads(response.read())

# def get_image(filename, subfolder, folder_type, server_address):
#     data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
#     url_values = urllib.parse.urlencode(data)
#     with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
#         return response.read()
    
# def get_images(prompt_id, server_address):
#     output_images = []

#     history = get_history(prompt_id, server_address)[prompt_id]
#     print(history)
#     for node_id in history['outputs']:
#         node_output = history['outputs'][node_id]
#         output_data = {}
#         if 'images' in node_output:
#             images = []
#             for image in node_output['images']:
#                 print(image["filename"])
#                 if image['type'] == 'output':
#                     image_data = get_image(image['filename'], image['subfolder'], image['type'], server_address)
#                     output_images.append({'image_data': image_data, 'file_name':image['filename'], 'type':image['type']})
#     return output_images

# def save_images(images, output_path):
#   for itm in images:
#       directory = output_path
#       os.makedirs(directory, exist_ok=True)
#       try:
#           image = Image.open(io.BytesIO(itm['image_data']))
#           image.save(os.path.join(directory, itm['file_name']))
#       except Exception as e:
#           print(f"Failed to save image {itm['file_name']}: {e}")  

# def track_progress(prompt, ws, prompt_id):
#     node_ids = list(prompt.keys())
#     finished_nodes = []

#     while True:
#         out = ws.recv()
#         if isinstance(out, str):
#             message = json.loads(out)
#             if message['type'] == 'progress':
#                 data = message['data']
#                 current_step = data['value']
#                 print('In K-Sampler -> Step: ', current_step, ' of: ', data['max'])
#             if message['type'] == 'execution_cached':
#                 data = message['data']
#                 for itm in data['nodes']:
#                     if itm not in finished_nodes:
#                         finished_nodes.append(itm)
#                         print('Progess: ', len(finished_nodes), '/', len(node_ids), ' Tasks done')
#             if message['type'] == 'executing':
#                 data = message['data']
#                 if data['node'] not in finished_nodes:
#                     finished_nodes.append(data['node'])
#                     print('Progess: ', len(finished_nodes), '/', len(node_ids), ' Tasks done')

#                 if data['node'] is None and data['prompt_id'] == prompt_id:
#                     break #Execution is done
#         else:
#             continue
#     return
  
# def load_workflow(workflow_path):
#     try:
#         with open(workflow_path, 'r') as file:
#             workflow = json.load(file)
#             return json.dumps(workflow)
#     except FileNotFoundError:
#         print(f"The file {workflow_path} was not found.")
#         return None
#     except json.JSONDecodeError:
#         print(f"The file {workflow_path} contains invalid JSON.")
#         return None
  
# def generate_image_by_prompt(prompt, output_path):
#     try:
#         ws, server_address, client_id = open_websocket_connection()
#         prompt_id = queue_prompt(prompt, client_id, server_address)['prompt_id']
#         track_progress(prompt, ws, prompt_id)
#         images = get_images(prompt_id, server_address)
#         return images
#         # for image in images:
#         #     print(image["file_name"])
#         # save_images(images, output_path)
#     finally:
#         ws.close()

# def prompt_to_image(workflow, model, positive_prompt, negative_prompt, width, height, batch_size, sampler_name, steps, seed):
#     prompt = json.loads(workflow)
#     id_to_class_type = {id: details['class_type'] for id, details in prompt.items()}
#     k_sampler = [key for key, value in id_to_class_type.items() if value == 'KSampler'][0]
#     if seed == -1:
#         prompt.get(k_sampler)['inputs']['seed'] = random.randint(10**14, 10**15 - 1)
#     else:
#         prompt.get(k_sampler)['inputs']['seed'] = seed

#     prompt.get(k_sampler)['inputs']['sampler_name'] = sampler_name
#     prompt.get(k_sampler)['inputs']['steps'] = steps

#     model_input_id = prompt.get(k_sampler)['inputs']['model'][0]
#     prompt.get(model_input_id)['inputs']['ckpt_name'] = model

#     latent_image_input_id = prompt.get(k_sampler)['inputs']['latent_image'][0]
#     prompt.get(latent_image_input_id)['inputs']['width'] = width
#     prompt.get(latent_image_input_id)['inputs']['height'] = height
#     prompt.get(latent_image_input_id)['inputs']['batch_size'] = batch_size

#     postive_input_id = prompt.get(k_sampler)['inputs']['positive'][0]
#     prompt.get(postive_input_id)['inputs']['text'] = positive_prompt

#     negative_input_id = prompt.get(k_sampler)['inputs']['negative'][0]
#     prompt.get(negative_input_id)['inputs']['text'] = negative_prompt

#     return generate_image_by_prompt(prompt, './output/')