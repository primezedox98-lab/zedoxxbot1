"""
ZEDOX Bot - Railway Ready
"""
import os
import sys
import time
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup
from pymongo import MongoClient

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
MONGO_URI = os.getenv("MONGO_URI")

# Validate
print("=" * 50)
print("🔍 ENVIRONMENT CHECK")
print("=" * 50)

if not BOT_TOKEN:
    print("❌ BOT_TOKEN missing!")
    sys.exit(1)
if not ADMIN_ID:
    print("❌ ADMIN_ID missing!")
    sys.exit(1)
if not MONGO_URI:
    print("❌ MONGO_URI missing!")
    sys.exit(1)

print(f"✅ BOT_TOKEN: {'*' * 10}")
print(f"✅ ADMIN_ID: {ADMIN_ID}")
print(f"✅ MONGO_URI: {MONGO_URI[:20]}...")

try:
    ADMIN_ID = int(ADMIN_ID)
except:
    print("❌ ADMIN_ID must be a number!")
    sys.exit(1)

# =========================
# MONGODB
# =========================
print("\n📦 MONGODB CONNECTION")
print("-" * 50)

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        maxPoolSize=20,
        minPoolSize=5
    )
    client.admin.command('ping')
    print("✅ MongoDB Connected!")
    
    db = client["zedox_test"]
    users_col = db["users"]
    folders_col = db["folders"]
    
    # Create test data if empty
    if users_col.count_documents({}) == 0:
        users_col.insert_many([
            {"_id": "111", "username": "test1", "points": 100, "vip": True, "created_at": time.time()},
            {"_id": "222", "username": "test2", "points": 50, "vip": False, "created_at": time.time()},
            {"_id": "333", "username": "test3", "points": 200, "vip": True, "created_at": time.time()},
        ])
        print("✅ Test users created")
    
    if folders_col.count_documents({}) == 0:
        folders_col.insert_many([
            {"cat": "free", "name": "Free Method 1", "price": 0, "number": 1, "parent": None},
            {"cat": "free", "name": "Free Method 2", "price": 0, "number": 2, "parent": None},
            {"cat": "vip", "name": "VIP Method 1", "price": 50, "number": 3, "parent": None},
            {"cat": "vip", "name": "VIP Method 2", "price": 100, "number": 4, "parent": None},
            {"cat": "vip", "name": "Sub Method", "price": 30, "number": 5, "parent": "VIP Method 1"},
        ])
        print("✅ Test folders created")
    
except Exception as e:
    print(f"❌ MongoDB Error: {e}")
    sys.exit(1)

# =========================
# BOT SETUP
# =========================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📂 FREE METHODS", "💎 VIP METHODS")
    kb.row("📊 DB STATS", "👤 MY PROFILE")
    kb.row("🔍 TEST DB", "📋 ALL DATA")
    return kb

# =========================
# HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    
    try:
        user = users_col.find_one({"_id": user_id})
        if user:
            users_col.update_one(
                {"_id": user_id},
                {"$set": {
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                    "last_active": time.time()
                }}
            )
            msg = f"👋 Welcome back, {message.from_user.first_name or 'User'}!"
        else:
            users_col.insert_one({
                "_id": user_id,
                "username": message.from_user.username,
                "first_name": message.from_user.first_name,
                "points": 10,
                "vip": False,
                "created_at": time.time(),
                "last_active": time.time()
            })
            msg = f"🎉 Welcome! You got 10 free points!"
        
        bot.send_message(
            message.chat.id,
            f"{msg}\n\n🆔 <code>{user_id}</code>\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            reply_markup=main_menu()
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "📂 FREE METHODS")
def free_methods(message):
    try:
        folders = list(folders_col.find({"cat": "free", "parent": None}))
        text = "📂 <b>FREE METHODS</b>\n\n"
        for f in folders:
            text += f"📄 [{f['number']}] {f['name']}\n"
        text += f"\n📊 Total: <code>{len(folders)}</code> in MongoDB"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ MongoDB Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "💎 VIP METHODS")
def vip_methods(message):
    try:
        folders = list(folders_col.find({"cat": "vip", "parent": None}))
        text = "💎 <b>VIP METHODS</b>\n\n"
        for f in folders:
            subs = folders_col.count_documents({"cat": "vip", "parent": f["name"]})
            text += f"📄 [{f['number']}] {f['name']} - {f['price']} pts"
            if subs > 0:
                text += f" (📁{subs})"
            text += "\n"
        text += f"\n📊 Total: <code>{len(folders)}</code> in MongoDB"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ MongoDB Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "📊 DB STATS")
def db_stats(message):
    try:
        total_users = users_col.count_documents({})
        vip_users = users_col.count_documents({"vip": True})
        total_free = folders_col.count_documents({"cat": "free"})
        total_vip = folders_col.count_documents({"cat": "vip"})
        
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$points"}}}]
        result = list(users_col.aggregate(pipeline))
        total_points = result[0]["total"] if result else 0
        
        text = (
            f"📊 <b>MONGODB STATISTICS</b>\n\n"
            f"👥 Users: <code>{total_users}</code> (VIP: {vip_users})\n"
            f"📁 Methods: Free <code>{total_free}</code> | VIP <code>{total_vip}</code>\n"
            f"💰 Points: <code>{total_points:,}</code>\n\n"
            f"📡 Status: ✅ Connected to MongoDB Atlas"
        )
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "👤 MY PROFILE")
def my_profile(message):
    try:
        user = users_col.find_one({"_id": str(message.from_user.id)})
        if user:
            vip = "💎 VIP" if user.get("vip") else "🆓 Free"
            created = datetime.fromtimestamp(user.get("created_at", time.time()))
            text = (
                f"👤 <b>YOUR PROFILE</b>\n\n"
                f"🆔 <code>{user['_id']}</code>\n"
                f"👤 @{user.get('username', 'None')}\n"
                f"💰 Points: <code>{user.get('points', 0)}</code>\n"
                f"💎 Status: {vip}\n"
                f"📅 Joined: {created.strftime('%Y-%m-%d')}\n\n"
                f"✅ Data from MongoDB Atlas"
            )
        else:
            text = "❌ Not in database! Send /start"
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "🔍 TEST DB")
def test_db(message):
    try:
        start_time = time.time()
        client.admin.command('ping')
        ping_ms = (time.time() - start_time) * 1000
        
        text = (
            f"🔍 <b>MONGODB CONNECTION TEST</b>\n\n"
            f"📡 Status: ✅ Connected\n"
            f"⚡ Ping: <code>{ping_ms:.1f}ms</code>\n"
            f"📚 Database: <code>zedox_test</code>\n"
            f"👥 Users: <code>{users_col.count_documents({})}</code>\n"
            f"📁 Folders: <code>{folders_col.count_documents({})}</code>\n\n"
            f"🔗 URI: <code>{MONGO_URI[:30]}...</code>"
        )
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Connection Failed!\n<code>{str(e)[:200]}</code>")

@bot.message_handler(func=lambda m: m.text == "📋 ALL DATA")
def all_data(message):
    try:
        users = list(users_col.find({}).limit(5))
        folders = list(folders_col.find({}).limit(5))
        
        text = "📋 <b>ALL MONGODB DATA</b>\n\n<b>👥 Users:</b>\n"
        for u in users:
            text += f"• <code>{u['_id']}</code> - {u.get('first_name','?')} - {u.get('points',0)} pts\n"
        
        text += "\n<b>📁 Folders:</b>\n"
        for f in folders:
            parent = f" (in {f['parent']})" if f.get('parent') else ""
            text += f"• [{f['number']}] {f['name']} - {f['cat']}{parent}\n"
        
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

# =========================
# START FUNCTION
# =========================
def start_bot_polling():
    """Start bot polling"""
    print("\n" + "=" * 50)
    print("🚀 BOT STARTING")
    print("=" * 50)
    print(f"✅ Bot: @{bot.get_me().username}")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"💾 MongoDB: Connected")
    print(f"👥 Users: {users_col.count_documents({})}")
    print(f"📁 Folders: {folders_col.count_documents({})}")
    print("=" * 50)
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Bot error: {e}")
            time.sleep(5)

# For direct run
if __name__ == "__main__":
    start_bot_polling()
