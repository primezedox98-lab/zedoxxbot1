"""
ZEDOX Bot - Production Version
Reads credentials from Railway Environment Variables
"""
import os
import sys
import time
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup
from pymongo import MongoClient

# =========================
# LOAD FROM ENVIRONMENT
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
MONGO_URI = os.getenv("MONGO_URI")

print("=" * 60)
print("🔍 ZEDOX BOT - ENVIRONMENT CHECK")
print("=" * 60)

# Validate
missing = []
if not BOT_TOKEN:
    missing.append("BOT_TOKEN")
if not ADMIN_ID:
    missing.append("ADMIN_ID")
if not MONGO_URI:
    missing.append("MONGO_URI")

if missing:
    print(f"❌ Missing: {', '.join(missing)}")
    print("Add these in Railway → Variables")
    sys.exit(1)

# Convert ADMIN_ID to int
try:
    ADMIN_ID = int(ADMIN_ID)
except:
    print("❌ ADMIN_ID must be a number!")
    sys.exit(1)

print(f"✅ BOT_TOKEN: {'*' * 20}{BOT_TOKEN[-5:]}")
print(f"✅ ADMIN_ID: {ADMIN_ID}")
print(f"✅ MONGO_URI: {MONGO_URI[:30]}...")
print("=" * 60)

# =========================
# MONGODB CONNECTION
# =========================
print("\n📦 CONNECTING TO MONGODB...")

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        maxPoolSize=20,
        minPoolSize=5
    )
    
    # Test connection
    client.admin.command('ping')
    print("✅ MongoDB Atlas Connected!")
    
    db = client["zedox_complete"]
    users_col = db["users"]
    folders_col = db["folders"]
    codes_col = db["codes"]
    config_col = db["config"]
    
    # Create indexes
    users_col.create_index("points")
    users_col.create_index("vip")
    users_col.create_index("refs")
    folders_col.create_index([("cat", 1), ("parent", 1)])
    folders_col.create_index("number", unique=True, sparse=True)
    print("✅ Indexes ready")
    
    # Create test data if collections are empty
    if users_col.count_documents({}) == 0:
        print("📝 Creating test users...")
        test_users = [
            {
                "_id": str(ADMIN_ID),
                "username": "admin",
                "first_name": "Admin",
                "points": 9999,
                "vip": True,
                "refs": 0,
                "created_at": time.time(),
                "last_active": time.time()
            },
            {
                "_id": "111111",
                "username": "test_user1",
                "first_name": "Test User 1",
                "points": 500,
                "vip": False,
                "refs": 5,
                "created_at": time.time(),
                "last_active": time.time()
            },
            {
                "_id": "222222",
                "username": "test_user2",
                "first_name": "Test User 2",
                "points": 250,
                "vip": True,
                "refs": 3,
                "created_at": time.time(),
                "last_active": time.time()
            },
        ]
        users_col.insert_many(test_users)
        print(f"✅ Created {len(test_users)} test users")
    else:
        print(f"ℹ️  {users_col.count_documents({})} users in database")
    
    if folders_col.count_documents({}) == 0:
        print("📝 Creating test folders...")
        test_folders = [
            {"cat": "free", "name": "Free Netflix", "price": 0, "number": 1, "parent": None},
            {"cat": "free", "name": "Free Spotify", "price": 0, "number": 2, "parent": None},
            {"cat": "free", "name": "Free Tools", "price": 0, "number": 3, "parent": None},
            {"cat": "vip", "name": "Premium Netflix", "price": 50, "number": 4, "parent": None},
            {"cat": "vip", "name": "Premium Spotify", "price": 30, "number": 5, "parent": None},
            {"cat": "vip", "name": "Cracking Tools", "price": 100, "number": 6, "parent": None},
            {"cat": "vip", "name": "Netflix Methods", "price": 20, "number": 7, "parent": "Premium Netflix"},
            {"cat": "vip", "name": "Netflix Accounts", "price": 40, "number": 8, "parent": "Premium Netflix"},
            {"cat": "vip", "name": "Spotify Premium", "price": 25, "number": 9, "parent": "Premium Spotify"},
        ]
        folders_col.insert_many(test_folders)
        print(f"✅ Created {len(test_folders)} test folders")
    else:
        print(f"ℹ️  {folders_col.count_documents({})} folders in database")
    
    print("✅ MongoDB Setup Complete!")
    
except Exception as e:
    print(f"❌ MongoDB Error: {e}")
    print("\n💡 Check:")
    print("1. MongoDB Atlas cluster is running")
    print("2. Add 0.0.0.0/0 in MongoDB Network Access")
    print("3. Verify MONGO_URI in Railway variables")
    sys.exit(1)

# =========================
# BOT INITIALIZATION
# =========================
print("\n🤖 STARTING TELEGRAM BOT...")

try:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    bot_info = bot.get_me()
    print(f"✅ Bot: @{bot_info.username}")
    print(f"✅ Name: {bot_info.first_name}")
except Exception as e:
    print(f"❌ Bot Error: {e}")
    sys.exit(1)

# =========================
# KEYBOARDS
# =========================
def main_menu(is_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📂 FREE METHODS", "💎 VIP METHODS")
    kb.row("📊 DB STATS", "👤 MY PROFILE")
    kb.row("🔍 TEST DB", "📋 ALL DATA")
    kb.row("💰 POINTS", "🎁 REFERRAL")
    if is_admin:
        kb.row("⚙️ ADMIN PANEL")
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📊 FULL STATS", "👥 LIST USERS")
    kb.row("💰 ADD POINTS", "💎 MAKE VIP")
    kb.row("📁 LIST FOLDERS", "🔙 BACK")
    return kb

# =========================
# BOT HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = str(message.from_user.id)
    
    try:
        existing = users_col.find_one({"_id": user_id})
        
        if existing:
            users_col.update_one(
                {"_id": user_id},
                {"$set": {
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                    "last_active": time.time()
                }}
            )
            welcome = f"👋 Welcome back, {message.from_user.first_name or 'User'}!"
        else:
            users_col.insert_one({
                "_id": user_id,
                "username": message.from_user.username,
                "first_name": message.from_user.first_name,
                "points": 10,
                "vip": False,
                "refs": 0,
                "created_at": time.time(),
                "last_active": time.time()
            })
            welcome = f"🎉 Welcome! You got 10 free points!"
        
        is_admin_user = (message.from_user.id == ADMIN_ID)
        
        text = (
            f"{welcome}\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"💾 Database: MongoDB Atlas ✅"
        )
        
        bot.send_message(message.chat.id, text, reply_markup=main_menu(is_admin_user))
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "📂 FREE METHODS")
def show_free(message):
    try:
        folders = list(folders_col.find({"cat": "free", "parent": None}).sort("number", 1))
        
        if not folders:
            bot.send_message(message.chat.id, "📂 No free methods yet!")
            return
        
        text = f"📂 <b>FREE METHODS</b>\n\n"
        for f in folders:
            text += f"📄 [{f['number']}] {f['name']}\n"
        
        text += f"\n📊 Total: <b>{len(folders)}</b> in MongoDB"
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "💎 VIP METHODS")
def show_vip(message):
    try:
        folders = list(folders_col.find({"cat": "vip", "parent": None}).sort("number", 1))
        
        if not folders:
            bot.send_message(message.chat.id, "💎 No VIP methods yet!")
            return
        
        text = f"💎 <b>VIP METHODS</b>\n\n"
        for f in folders:
            subs = folders_col.count_documents({"cat": "vip", "parent": f["name"]})
            text += f"📄 [{f['number']}] {f['name']}\n"
            text += f"   💰 {f['price']} pts"
            if subs > 0:
                text += f" | 📁 {subs} sub-folders"
            text += "\n\n"
        
        text += f"📊 Total: <b>{len(folders)}</b> in MongoDB"
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "📊 DB STATS")
def show_stats(message):
    try:
        total_users = users_col.count_documents({})
        vip_users = users_col.count_documents({"vip": True})
        free_users = total_users - vip_users
        
        total_free = folders_col.count_documents({"cat": "free"})
        total_vip = folders_col.count_documents({"cat": "vip"})
        
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$points"}}}]
        result = list(users_col.aggregate(pipeline))
        total_points = result[0]["total"] if result else 0
        
        top_users = list(users_col.find({}).sort("points", -1).limit(3))
        
        text = (
            f"📊 <b>DATABASE STATS</b>\n\n"
            f"👥 Users: <code>{total_users}</code> (VIP: {vip_users}, Free: {free_users})\n"
            f"📁 Folders: Free <code>{total_free}</code> | VIP <code>{total_vip}</code>\n"
            f"💰 Total Points: <code>{total_points:,}</code>\n\n"
            f"🏆 <b>Top Users:</b>\n"
        )
        
        for i, u in enumerate(top_users, 1):
            name = u.get('first_name') or 'Unknown'
            text += f"{i}. {name}: <code>{u.get('points', 0):,}</code> pts\n"
        
        text += f"\n📡 MongoDB Atlas ✅"
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "👤 MY PROFILE")
def show_profile(message):
    try:
        user = users_col.find_one({"_id": str(message.from_user.id)})
        
        if not user:
            bot.send_message(message.chat.id, "❌ Not registered! Send /start")
            return
        
        vip = "💎 VIP" if user.get("vip") else "🆓 Free"
        created = datetime.fromtimestamp(user.get("created_at", time.time()))
        
        text = (
            f"👤 <b>PROFILE</b>\n\n"
            f"🆔 <code>{user['_id']}</code>\n"
            f"👤 {user.get('first_name', 'Unknown')}\n"
            f"📛 @{user.get('username', 'None')}\n"
            f"💰 Points: <code>{user.get('points', 0):,}</code>\n"
            f"💎 Status: {vip}\n"
            f"👥 Referrals: {user.get('refs', 0)}\n"
            f"📅 Joined: {created.strftime('%Y-%m-%d')}\n\n"
            f"💾 Data: MongoDB Atlas ✅"
        )
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "🔍 TEST DB")
def test_db(message):
    try:
        start = time.time()
        client.admin.command('ping')
        ping_ms = (time.time() - start) * 1000
        
        server_info = client.server_info()
        
        text = (
            f"🔍 <b>CONNECTION TEST</b>\n\n"
            f"📡 Status: ✅ Connected\n"
            f"⚡ Ping: <code>{ping_ms:.1f}ms</code>\n"
            f"📚 DB: <code>zedox_complete</code>\n"
            f"📋 MongoDB: {server_info.get('version', 'Unknown')}\n"
            f"👥 Users: <code>{users_col.count_documents({})}</code>\n"
            f"📁 Folders: <code>{folders_col.count_documents({})}</code>\n\n"
            f"🔗 URI: <code>{MONGO_URI[:30]}...</code>"
        )
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Failed!\n<code>{str(e)[:200]}</code>")

@bot.message_handler(func=lambda m: m.text == "📋 ALL DATA")
def show_all(message):
    try:
        users = list(users_col.find({}).limit(5))
        folders = list(folders_col.find({}).limit(5))
        
        text = f"📋 <b>MONGODB DATA</b>\n\n<b>Users:</b>\n"
        for u in users:
            vip = "💎" if u.get("vip") else "🆓"
            text += f"• {vip} <code>{u['_id']}</code> - {u.get('first_name','?')} - {u.get('points',0)} pts\n"
        
        text += f"\n<b>Folders:</b>\n"
        for f in folders:
            parent = f" (in {f['parent']})" if f.get('parent') else ""
            text += f"• [{f['number']}] {f['name']} - {f['cat']}{parent}\n"
        
        bot.send_message(message.chat.id, text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "💰 POINTS")
def show_points(message):
    try:
        user = users_col.find_one({"_id": str(message.from_user.id)})
        if user:
            text = (
                f"💰 <b>YOUR POINTS</b>\n\n"
                f"Balance: <code>{user.get('points', 0):,}</code> pts\n"
                f"VIP: {'✅' if user.get('vip') else '❌'}\n\n"
                f"💡 Earn more by referring friends!"
            )
        else:
            text = "❌ Send /start first!"
        
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "🎁 REFERRAL")
def show_referral(message):
    try:
        user = users_col.find_one({"_id": str(message.from_user.id)})
        if not user:
            bot.send_message(message.chat.id, "❌ Send /start first!")
            return
        
        ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
        
        text = (
            f"🎁 <b>REFERRAL</b>\n\n"
            f"🔗 Link:\n<code>{ref_link}</code>\n\n"
            f"📊 Referrals: {user.get('refs', 0)}\n"
            f"💰 Reward: +5 pts each"
        )
        
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

# =========================
# ADMIN PANEL
# =========================
@bot.message_handler(func=lambda m: m.text == "⚙️ ADMIN PANEL")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    bot.send_message(
        message.chat.id,
        "⚙️ <b>ADMIN PANEL</b>",
        reply_markup=admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📊 FULL STATS")
def full_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        total_users = users_col.count_documents({})
        vip_users = users_col.count_documents({"vip": True})
        
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$points"}}}]
        result = list(users_col.aggregate(pipeline))
        total_points = result[0]["total"] if result else 0
        
        top_users = list(users_col.find({}).sort("points", -1).limit(5))
        
        text = (
            f"📊 <b>FULL STATS</b>\n\n"
            f"👥 Users: <code>{total_users}</code> (VIP: {vip_users})\n"
            f"💰 Points: <code>{total_points:,}</code>\n"
            f"📁 Free: <code>{folders_col.count_documents({'cat':'free'})}</code>\n"
            f"📁 VIP: <code>{folders_col.count_documents({'cat':'vip'})}</code>\n\n"
            f"🏆 <b>Top Users:</b>\n"
        )
        
        for i, u in enumerate(top_users, 1):
            text += f"{i}. {u.get('first_name','?')}: <code>{u.get('points',0):,}</code> pts\n"
        
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "👥 LIST USERS")
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        users = list(users_col.find({}).sort("points", -1).limit(15))
        
        text = f"👥 <b>USERS</b> ({len(users)})\n\n"
        for u in users:
            vip = "💎" if u.get("vip") else "🆓"
            text += f"• {vip} <code>{u['_id']}</code> - {u.get('first_name','?')} - {u.get('points',0)} pts\n"
        
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "📁 LIST FOLDERS")
def list_folders(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        folders = list(folders_col.find({}).sort("number", 1))
        
        text = f"📁 <b>FOLDERS</b> ({len(folders)})\n\n"
        for f in folders:
            parent = f" → {f['parent']}" if f.get('parent') else ""
            text += f"• [{f['number']}] {f['name']} ({f['cat']}{parent}) - {f['price']} pts\n"
        
        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(func=lambda m: m.text == "🔙 BACK")
def back_button(message):
    is_admin_user = (message.from_user.id == ADMIN_ID)
    bot.send_message(
        message.chat.id,
        "✅ Main Menu",
        reply_markup=main_menu(is_admin_user)
    )

# =========================
# START BOT
# =========================
def start_bot_polling():
    """Start bot with error handling"""
    print("\n" + "=" * 60)
    print("🚀 ZEDOX BOT RUNNING")
    print("=" * 60)
    print(f"✅ Bot: @{bot_info.username}")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"💾 MongoDB: Connected")
    print(f"👥 Users: {users_col.count_documents({})}")
    print(f"📁 Folders: {folders_col.count_documents({})}")
    print("=" * 60)
    print("📱 Send /start on Telegram!")
    print("=" * 60)
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot_polling()
