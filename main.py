import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import ReplyKeyboardMarkup

# =========================
# SIMPLE HTTP SERVER FOR RAILWAY
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"ZEDOX Bot is Running!")
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Health server on port {port}")
    server.serve_forever()

# =========================
# BOT CODE
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")

print("=" * 50)
print("ZEDOX BOT - STARTING")
print("=" * 50)
print(f"BOT_TOKEN: {'SET' if BOT_TOKEN else 'MISSING'}")
print(f"MONGO_URI: {'SET' if MONGO_URI else 'MISSING'}")

# MongoDB
db = None
if MONGO_URI:
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client["zedox_test"]
        print("✅ MongoDB Connected!")
    except Exception as e:
        print(f"⚠️ MongoDB: {e}")

# Bot
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    bot_info = bot.get_me()
    print(f"✅ Bot: @{bot_info.username}")
except Exception as e:
    print(f"❌ Bot Error: {e}")
    sys.exit(1)

# Keyboard
def menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📊 STATUS", "👤 PROFILE")
    kb.row("💾 DB TEST", "ℹ️ HELP")
    return kb

# Handlers
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    
    if db:
        try:
            db.users.update_one(
                {"_id": str(user_id)},
                {"$set": {
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                    "last_active": time.time()
                }},
                upsert=True
            )
        except:
            pass
    
    text = (
        f"✅ <b>Bot is Working!</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💾 MongoDB: {'✅ Connected' if db else '❌ Not connected'}\n"
        f"🚀 Railway: Deployed"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=menu(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📊 STATUS")
def status(message):
    s = "✅ Connected" if db else "❌ Not connected"
    bot.send_message(message.chat.id, f"📊 <b>Status</b>\n\nMongoDB: {s}\nBot: ✅ Running", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👤 PROFILE")
def profile(message):
    bot.send_message(
        message.chat.id,
        f"👤 <b>Profile</b>\n\nID: <code>{message.from_user.id}</code>\nName: {message.from_user.first_name}",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "💾 DB TEST")
def dbtest(message):
    if not db:
        bot.send_message(message.chat.id, "❌ MongoDB not connected!")
        return
    
    try:
        db.test.insert_one({"test": True})
        bot.send_message(message.chat.id, "✅ MongoDB is working!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(func=lambda m: m.text == "ℹ️ HELP")
def help_cmd(message):
    bot.send_message(message.chat.id, "ℹ️ This bot tests Railway + MongoDB deployment.\n\n/start - Start\n/ping - Ping")

@bot.message_handler(commands=["ping"])
def ping(message):
    bot.reply_to(message, "🏓 Pong!")

# =========================
# START
# =========================
if __name__ == "__main__":
    # Start health server in background
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Start bot
    print("🚀 Starting bot...")
    bot.remove_webhook()
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(5)
