"""
ZEDOX Bot - Railway Entry Point
"""
import os
import sys
import threading
import time
import telebot
from telebot.types import ReplyKeyboardMarkup
from flask import Flask

# =========================
# FLASK APP FOR RAILWAY
# =========================
app = Flask(__name__)

@app.route('/')
def home():
    return "ZEDOX Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

# =========================
# BOT CODE (in same file to avoid import issues)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")
MONGO_URI = os.getenv("MONGO_URI", "")

# Print config for debugging
print("=" * 50)
print("ZEDOX BOT - STARTING")
print("=" * 50)
print(f"BOT_TOKEN: {'SET' if BOT_TOKEN else 'MISSING'} ({len(BOT_TOKEN)} chars)")
print(f"ADMIN_ID: {ADMIN_ID}")
print(f"MONGO_URI: {'SET' if MONGO_URI else 'MISSING'}")
print("=" * 50)

# Initialize bot
bot = None
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    bot_info = bot.get_me()
    print(f"✅ Bot: @{bot_info.username}")
except Exception as e:
    print(f"❌ Bot Error: {e}")

# Try MongoDB (optional)
db = None
try:
    if MONGO_URI:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client["zedox_test"]
        print("✅ MongoDB Connected!")
except Exception as e:
    print(f"⚠️ MongoDB: {e}")

# =========================
# KEYBOARD
# =========================
def get_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📊 STATUS", "👤 PROFILE")
    kb.row("💾 DB TEST", "ℹ️ HELP")
    return kb

# =========================
# BOT HANDLERS
# =========================
if bot:
    @bot.message_handler(commands=["start"])
    def start_cmd(message):
        user_id = message.from_user.id
        
        # Save to MongoDB if available
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
            f"👤 @{message.from_user.username or 'None'}\n"
            f"📅 {time.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"<b>Status:</b>\n"
            f"• Bot: ✅ Running\n"
            f"• MongoDB: {'✅ Connected' if db else '❌ Not connected'}\n"
            f"• Railway: ✅ Deployed"
        )
        
        bot.send_message(message.chat.id, text, reply_markup=get_menu(), parse_mode="HTML")
        print(f"✅ /start from {user_id}")

    @bot.message_handler(func=lambda m: m.text == "📊 STATUS")
    def status_cmd(message):
        if db:
            try:
                client.admin.command('ping')
                users = db.users.count_documents({})
                text = f"📊 <b>STATUS</b>\n\n✅ MongoDB: Connected\n👥 Users: {users}\n✅ Bot: Running"
            except:
                text = "📊 <b>STATUS</b>\n\n✅ Bot: Running\n❌ MongoDB: Disconnected"
        else:
            text = "📊 <b>STATUS</b>\n\n✅ Bot: Running\n⚠️ MongoDB: Not configured"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "👤 PROFILE")
    def profile_cmd(message):
        user_id = message.from_user.id
        
        text = (
            f"👤 <b>PROFILE</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 {message.from_user.first_name}\n"
            f"📛 @{message.from_user.username or 'None'}\n"
            f"💬 Language: {message.from_user.language_code}\n"
            f"🤖 Is Bot: {message.from_user.is_bot}"
        )
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "💾 DB TEST")
    def dbtest_cmd(message):
        if not db:
            bot.send_message(message.chat.id, "❌ MongoDB not connected!")
            return
        
        try:
            # Test write
            test = db.test.insert_one({"test": True, "time": time.time()})
            # Test read
            doc = db.test.find_one({"_id": test.inserted_id})
            # Test delete
            db.test.delete_one({"_id": test.inserted_id})
            
            text = "💾 <b>DB TEST</b>\n\n✅ Write: Success\n✅ Read: Success\n✅ Delete: Success\n\nMongoDB is working perfectly!"
            bot.send_message(message.chat.id, text, parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB Test Failed!\n{str(e)[:200]}", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "ℹ️ HELP")
    def help_cmd(message):
        text = (
            "ℹ️ <b>HELP</b>\n\n"
            "Commands:\n"
            "/start - Start bot\n"
            "/ping - Check if alive\n\n"
            "Buttons test MongoDB and Railway deployment."
        )
        bot.send_message(message.chat.id, text, parse_mode="HTML")

    @bot.message_handler(commands=["ping"])
    def ping_cmd(message):
        bot.reply_to(message, "🏓 Pong! Bot is alive!")

# =========================
# START BOT IN BACKGROUND
# =========================
def start_bot():
    """Start bot polling in background"""
    if bot is None:
        print("❌ Bot not initialized!")
        return
    
    print("\n🚀 Starting bot polling...")
    bot.remove_webhook()
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)

# =========================
# MAIN - START EVERYTHING
# =========================
if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    print("✅ Bot thread started")
    
    # Start Flask for Railway
    port = int(os.getenv("PORT", 8080))
    print(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port)
