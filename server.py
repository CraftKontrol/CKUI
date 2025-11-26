from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# API key stored server-side only (never sent to client)
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', 'your-api-key-here')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # Get request data from frontend
        data = request.get_json()
        
        # Forward request to Mistral AI with server's API key
        response = requests.post(
            'https://api.mistral.ai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {MISTRAL_API_KEY}'
            },
            json=data
        )
        
        # Return Mistral's response to frontend
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
