"""
Railway Entry Point - Must be named main.py
"""
from flask import Flask, jsonify
import threading
import os
import sys
import time

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot": "ZEDOX",
        "timestamp": time.time()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def start_bot():
    """Start the bot in background"""
    try:
        # Import bot after Flask starts
        from bot import start_bot_polling
        start_bot_polling()
    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask (Railway needs this)
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
