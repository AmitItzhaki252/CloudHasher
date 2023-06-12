import json
from flask import Flask, request
import uuid
from flask import Flask
from flasgger import Swagger, swag_from
import base64
from workersManager import get_public_ip, message_added, decrease_workers
import queue

app = Flask(__name__)

swagger = Swagger(app)

global input_queue
global results
input_queue = queue.Queue()
results = queue.Queue()

global destination_ip
global manager_ip

with open("public_ips.json", "r") as file:
    ips_json = file.read()

# Parse the JSON content
ips = json.loads(ips_json)

# Access the IP1 and IP2 values
ip1 = ips["IP1"]
ip2 = ips["IP2"]
manager_ip = ips["MY"]

if get_public_ip() == ip1:
    destination_ip = ip2
else:
    destination_ip = ip1


@app.route("/enqueue", methods=['PUT'])
@swag_from({
    'consumes': ['application/octet-stream'],
    'parameters': [
        {
            'name': 'iterations',
            'in': 'query',
            'type': 'integer',
            'required': True,
            'description': 'Number of iterations'
        },
        {
            'name': 'body',
            'in': 'body',
            'schema': {
                'type': 'string',
                'type': 'binary'
            },
            'description': 'data'
        }
    ],
    'responses': {
        200: {
            'description': 'Successfully enqueued data',
        }
    }
})
def enqueue():
    global input_queue
    global destination_ip
    global manager_ip

    iterations = request.args['iterations']
    data = request.get_data()
    work_id = uuid.uuid4()

    if data is None:
        data = []
        print('received empty data')
        return 'data was empty'

    data = base64.b64encode(data).decode('utf-8')

    input_queue.put({"workId": work_id, "iterations": iterations,
                     "data": data, "destinationIp": destination_ip, "gotData": True})

    message_added(input_queue.qsize(), manager_ip)

    return 'Enqueued successfuly'


@app.route("/dequeue", methods=['GET'])
@swag_from({
    'responses': {
        200: {
            'description': 'Successfully enqueued data',
            'scheme': {
                'type': 'object'
            }
        }
    }
})
def dequeue():
    global input_queue

    try:
        data = input_queue.get(timeout=10)
    except:
        print('No data is waiting for work')
        return json.dumps({"gotData": False}, indent=4, sort_keys=True, default=str)

    return json.dumps(data, indent=4, sort_keys=True, default=str)


@app.route("/completed", methods=['POST'])
@swag_from({
    'consumes': ['application/json'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'schema': {
                'type': 'object'
            },
            'description': 'data'
        }
    ],
    'responses': {
        200: {
            'description': 'Successfully enqueued data',
        }
    }
})
def completed():
    global results

    data = request.get_json()
    results.put(data)

    return 'Successfully enqueued data'


@app.route("/pullCompleted", methods=['POST'])
@swag_from({
    'parameters': [
        {
            'name': 'top',
            'in': 'query',
            'type': 'integer',
            'required': True,
            'description': 'Number of messages to pop'
        }
    ],
    'responses': {
        200: {
            'description': 'Pulled data',
            'scheme': {
                'type': 'object'
            }
        }
    }
})
def pullCompleted():
    global results

    top = int(request.args['top'])

    return_results = []
    for _ in range(top):
        try:
            result = results.get(timeout=1)
            return_results.append(result)
        except:
            print("Requested more items then ready")
            return json.dumps(return_results, indent=4, sort_keys=True, default=str)

    return json.dumps(return_results, indent=4, sort_keys=True, default=str)


@app.route("/killWorker", methods=['POST'])
@swag_from({
    'responses': {
        200: {
            'description': 'Successfully killed worker',
        }
    }
})
def kill_worker():
    decrease_workers()

    return 'Successfully killed worker'


if __name__ == "__main__":
    app.run(debug=True)