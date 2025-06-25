from flask import Flask, jsonify
import subprocess

app = Flask(__name__)

@app.route('/')
def home():
    return '✅ Stoic Quote Generator is running on Render!'

@app.route('/generate', methods=['GET'])
def generate_quote_video():
    try:
        result = subprocess.run(["python", "main.py"], check=True, capture_output=True, text=True)
        return jsonify({"status": "success", "output": result.stdout})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "output": e.stderr}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
