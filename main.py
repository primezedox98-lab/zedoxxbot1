"""
ZEDOX Bot - Railway Fixed Version
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
# BOT CODE
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID", "")
MONGO_URI = os.getenv("MONGO_URI", "")

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
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    # IMPORTANT: Remove webhook first to avoid 409 error
    bot.remove_webhook()
    time.sleep(1)
    bot_info = bot.get_me()
    print(f"✅ Bot: @{bot_info.username}")
    print(f"✅ Webhook removed, ready for polling")
except Exception as e:
    print(f"❌ Bot Error: {e}")
    sys.exit(1)

# MongoDB Connection
client = None
db = None

try:
    if MONGO_URI:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client["zedox_complete"]
        print("✅ MongoDB Connected!")
except Exception as e:
    print(f"⚠️ MongoDB not available: {e}")
    print("Bot will run without database")

# =========================
# KEYBOARD
# =========================
def get_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📊 STATUS", "👤 PROFILE")
    kb.row("💾 DB TEST", "📋 DB STATS")
    kb.row("ℹ️ HELP")
    return kb

# =========================
# BOT HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def start_cmd(message):
    user_id = message.from_user.id
    
    # Save to MongoDB if available - FIXED: use 'is not None'
    if db is not None:
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
            print(f"✅ User {user_id} saved to MongoDB")
        except Exception as e:
            print(f"⚠️ DB save error: {e}")
    
    db_status = "✅ Connected" if db is not None else "❌ Not Connected"
    
    text = (
        f"✅ <b>ZEDOX Bot is Working!</b>\n\n"
        f"🆔 Your ID: <code>{user_id}</code>\n"
        f"👤 @{message.from_user.username or 'None'}\n"
        f"📅 {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"<b>System Status:</b>\n"
        f"• Bot: ✅ Running\n"
        f"• MongoDB: {db_status}\n"
        f"• Railway: ✅ Deployed\n"
        f"• Python: 3.10.13"
    )
    
    bot.send_message(message.chat.id, text, reply_markup=get_menu())
    print(f"✅ /start sent to {user_id}")

@bot.message_handler(func=lambda m: m.text == "📊 STATUS")
def status_cmd(message):
    # FIXED: use 'is not None'
    if db is not None:
        try:
            client.admin.command('ping')
            users_count = db.users.count_documents({})
            folders_count = db.folders.count_documents({}) if db.folders is not None else 0
            
            text = (
                f"📊 <b>SYSTEM STATUS</b>\n\n"
                f"🤖 Bot: ✅ Running\n"
                f"💾 MongoDB: ✅ Connected\n"
                f"👥 Users: <code>{users_count}</code>\n"
                f"📁 Folders: <code>{folders_count}</code>\n"
                f"🖥️ Platform: Railway\n"
                f"⏰ Uptime: Active"
            )
        except Exception as e:
            text = f"📊 <b>STATUS</b>\n\n✅ Bot: Running\n⚠️ MongoDB: Error\n<code>{str(e)[:100]}</code>"
    else:
        text = "📊 <b>STATUS</b>\n\n✅ Bot: Running\n⚠️ MongoDB: Not configured"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "👤 PROFILE")
def profile_cmd(message):
    user_id = message.from_user.id
    
    points = 0
    vip = False
    
    # FIXED: use 'is not None'
    if db is not None:
        try:
            user = db.users.find_one({"_id": str(user_id)})
            if user:
                points = user.get("points", 0)
                vip = user.get("vip", False)
        except:
            pass
    
    text = (
        f"👤 <b>YOUR PROFILE</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Name: {message.from_user.first_name}\n"
        f"📛 Username: @{message.from_user.username or 'None'}\n"
        f"💰 Points: <code>{points}</code>\n"
        f"💎 VIP: {'✅ Yes' if vip else '❌ No'}\n"
        f"🌐 Language: {message.from_user.language_code}\n\n"
        f"💾 Data: {'MongoDB Atlas' if db is not None else 'Local'}"
    )
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "💾 DB TEST")
def dbtest_cmd(message):
    # FIXED: use 'is not None'
    if db is None:
        bot.send_message(message.chat.id, "❌ MongoDB is not connected!\n\nCheck MONGO_URI in Railway variables.")
        return
    
    try:
        start_time = time.time()
        
        # Test 1: Ping
        client.admin.command('ping')
        ping_time = (time.time() - start_time) * 1000
        
        # Test 2: Write
        test_collection = db.test_collection
        result = test_collection.insert_one({
            "test": True,
            "timestamp": time.time(),
            "user": str(message.from_user.id)
        })
        write_ok = result.inserted_id is not None
        
        # Test 3: Read
        doc = test_collection.find_one({"_id": result.inserted_id})
        read_ok = doc is not None
        
        # Test 4: Delete
        test_collection.delete_one({"_id": result.inserted_id})
        
        # Test 5: List collections
        collections = db.list_collection_names()
        
        text = (
            f"💾 <b>MONGODB TEST RESULTS</b>\n\n"
            f"📡 Ping: ✅ ({ping_time:.1f}ms)\n"
            f"✍️ Write: {'✅' if write_ok else '❌'}\n"
            f"📖 Read: {'✅' if read_ok else '❌'}\n"
            f"🗑️ Delete: ✅\n\n"
            f"📚 Collections: <code>{', '.join(collections)}</code>\n\n"
            f"✅ All tests passed!\n"
            f"💾 MongoDB Atlas is working!"
        )
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ <b>Database Test Failed!</b>\n\n<code>{str(e)[:200]}</code>")

@bot.message_handler(func=lambda m: m.text == "📋 DB STATS")
def dbstats_cmd(message):
    # FIXED: use 'is not None'
    if db is None:
        bot.send_message(message.chat.id, "❌ MongoDB not connected!")
        return
    
    try:
        # Get counts
        total_users = db.users.count_documents({}) if db.users is not None else 0
        vip_users = db.users.count_documents({"vip": True}) if db.users is not None else 0
        
        # Get total points
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$points"}}}]
        result = list(db.users.aggregate(pipeline)) if db.users is not None else []
        total_points = result[0]["total"] if result else 0
        
        # Get database info
        server_info = client.server_info()
        
        text = (
            f"📋 <b>DATABASE STATISTICS</b>\n\n"
            f"📡 <b>Server:</b>\n"
            f"• Version: {server_info.get('version', 'Unknown')}\n"
            f"• Platform: MongoDB Atlas\n\n"
            f"👥 <b>Users:</b>\n"
            f"• Total: <code>{total_users}</code>\n"
            f"• VIP: <code>{vip_users}</code>\n"
            f"• Free: <code>{total_users - vip_users}</code>\n\n"
            f"💰 <b>Points:</b>\n"
            f"• Total: <code>{total_points:,}</code>\n\n"
            f"📚 <b>Collections:</b>\n"
            f"• <code>{', '.join(db.list_collection_names())}</code>"
        )
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error fetching stats!\n<code>{str(e)[:200]}</code>")

@bot.message_handler(func=lambda m: m.text == "ℹ️ HELP")
def help_cmd(message):
    text = (
        "ℹ️ <b>ZEDOX BOT HELP</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Start the bot\n"
        "/ping - Check if alive\n\n"
        "<b>Buttons:</b>\n"
        "📊 STATUS - System status\n"
        "👤 PROFILE - Your profile\n"
        "💾 DB TEST - Test MongoDB\n"
        "📋 DB STATS - Database statistics\n\n"
        "<b>Deployment:</b>\n"
        "✅ Railway\n"
        "✅ MongoDB Atlas"
    )
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["ping"])
def ping_cmd(message):
    bot.reply_to(message, "🏓 Pong! Bot is alive and running on Railway!")

@bot.message_handler(commands=["test"])
def test_cmd(message):
    """Quick test command"""
    bot.reply_to(
        message,
        f"✅ Bot is working!\n\n"
        f"Your ID: <code>{message.from_user.id}</code>\n"
        f"MongoDB: {'✅ Connected' if db is not None else '❌ Not connected'}"
    )

# =========================
# START BOT
# =========================
def start_bot():
    """Start bot polling"""
    print("\n" + "=" * 50)
    print("🚀 STARTING BOT POLLING")
    print("=" * 50)
    print(f"Bot: @{bot_info.username}")
    print(f"DB: {'Connected' if db is not None else 'Not connected'}")
    print("=" * 50)
    
    while True:
        try:
            print("🔄 Bot polling started...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    print("✅ Bot thread started")
    
    # Start Flask for Railway health checks
    port = int(os.getenv("PORT", 8080))
    print(f"🌐 Web server starting on port {port}")
    app.run(host='0.0.0.0', port=port)
