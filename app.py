from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "ZEDOX Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Import and run bot in separate thread
    import bot
    bot_thread = threading.Thread(target=bot.main, daemon=True)
    bot_thread.start()
    
    # Run Flask
    run_flask()
