"""
Railway Entry Point - ZEDOX Bot
"""
from flask import Flask, jsonify
import threading
import os
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
    """Start bot in background thread"""
    try:
        from bot import start_bot_polling
        start_bot_polling()
    except Exception as e:
        print(f"Bot startup error: {e}")

if __name__ == "__main__":
    # Start bot in background
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask for Railway health checks
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
