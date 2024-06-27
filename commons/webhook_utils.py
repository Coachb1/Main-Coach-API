from flask import Flask, request, jsonify
import hmac
import hashlib
import requests
import json


WEBHOOK_SECRET = 'your-webhook-secret'

def generate_signature(payload):
    return hmac.new(WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

# @app.route('/send-webhook', methods=['POST'])
def invoke_webhook(event,data):
    base_url = "http://127.0.0.1:5000"
    # endpoint = "send-webhook"
    endpoint = "endpoint"
    url = f"{base_url}/{endpoint}"
    # url = 'https://webhook.receiver.url/endpoint'
    payload = {"event": event, "data": str(data)}
    payload = json.dumps(payload)
    headers = {
        'Content-Type': 'application/json',
        'X-Signature': generate_signature(payload)
    }
    response = requests.post(url, data=payload, headers=headers)
    # return jsonify({"status": response.status_code})
    print(response.json())
    