"""
ZEDOX Bot - Minimal Test Version
Tests MongoDB connection and environment variables
"""

import os
import sys
import time
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# =========================
# ENVIRONMENT VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
MONGO_URI = os.getenv("MONGO_URI")

print("=" * 50)
print("🔍 CHECKING ENVIRONMENT")
print("=" * 50)
print(f"BOT_TOKEN: {'✅ SET' if BOT_TOKEN else '❌ MISSING'} (length: {len(BOT_TOKEN) if BOT_TOKEN else 0})")
print(f"ADMIN_ID: {'✅ SET' if ADMIN_ID else '❌ MISSING'}")
print(f"MONGO_URI: {'✅ SET' if MONGO_URI else '❌ MISSING'}")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID not set!")
if not MONGO_URI:
    raise ValueError("MONGO_URI not set!")

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID must be a number!")

# =========================
# MONGODB CONNECTION
# =========================
print("\n📦 MONGODB CONNECTION")
print("-" * 50)
try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000
    )
    # Test connection
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully!")
    
    db = client["zedox_test"]
    users_col = db["users"]
    folders_col = db["folders"]
    config_col = db["config"]
    
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"❌ MongoDB Connection Failed: {e}")
    print("\n💡 TIPS:")
    print("1. Check if MONGO_URI is correct")
    print("2. Add your IP to MongoDB Atlas Network Access")
    print("3. Check username/password in connection string")
    print(f"4. Your URI starts with: {MONGO_URI[:20]}...")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    sys.exit(1)

# =========================
# CREATE TEST DATA
# =========================
print("\n📝 CREATING TEST DATA")
print("-" * 50)

# Create indexes
try:
    users_col.create_index("points")
    folders_col.create_index([("cat", 1), ("parent", 1)])
    print("✅ Indexes created")
except Exception as e:
    print(f"⚠️ Index warning: {e}")

# Add test data if empty
if users_col.count_documents({}) == 0:
    test_users = [
        {"_id": "111111", "username": "test_user1", "first_name": "Test1", "points": 100, "vip": True, "refs": 5, "created_at": time.time()},
        {"_id": "222222", "username": "test_user2", "first_name": "Test2", "points": 50, "vip": False, "refs": 2, "created_at": time.time()},
        {"_id": "333333", "username": "test_user3", "first_name": "Test3", "points": 200, "vip": True, "refs": 10, "created_at": time.time()},
    ]
    users_col.insert_many(test_users)
    print(f"✅ Created {len(test_users)} test users")
else:
    count = users_col.count_documents({})
    print(f"ℹ️ Users collection has {count} documents")

if folders_col.count_documents({}) == 0:
    test_folders = [
        {"cat": "free", "name": "Free Method 1", "files": [], "price": 0, "number": 1, "parent": None, "created_at": time.time()},
        {"cat": "free", "name": "Free Method 2", "files": [], "price": 0, "number": 2, "parent": None, "created_at": time.time()},
        {"cat": "vip", "name": "VIP Method 1", "files": [], "price": 50, "number": 3, "parent": None, "created_at": time.time()},
        {"cat": "vip", "name": "VIP Method 2", "files": [], "price": 100, "number": 4, "parent": None, "created_at": time.time()},
        {"cat": "vip", "name": "Sub Method", "files": [], "price": 30, "number": 5, "parent": "VIP Method 1", "created_at": time.time()},
    ]
    folders_col.insert_many(test_folders)
    print(f"✅ Created {len(test_folders)} test folders")
else:
    count = folders_col.count_documents({})
    print(f"ℹ️ Folders collection has {count} documents")

# =========================
# BOT INITIALIZATION
# =========================
print("\n🤖 INITIALIZING BOT")
print("-" * 50)

try:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    bot_info = bot.get_me()
    print(f"✅ Bot Name: {bot_info.first_name}")
    print(f"✅ Bot Username: @{bot_info.username}")
    print(f"✅ Bot ID: {bot_info.id}")
except Exception as e:
    print(f"❌ Bot initialization failed: {e}")
    print("Check your BOT_TOKEN - get it from @BotFather")
    sys.exit(1)

# =========================
# KEYBOARDS
# =========================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📂 FREE METHODS", "💎 VIP METHODS")
    kb.row("📊 DATABASE STATS", "👤 MY PROFILE")
    kb.row("🔄 REFRESH DATA", "🔍 CHECK DB")
    kb.row("ℹ️ HELP", "📋 LIST DATA")
    return kb

# =========================
# BOT HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Save to MongoDB
    existing = users_col.find_one({"_id": user_id})
    if existing:
        users_col.update_one(
            {"_id": user_id},
            {"$set": {
                "username": username,
                "first_name": first_name,
                "last_active": time.time()
            }}
        )
        msg = "👋 Welcome back!"
    else:
        users_col.insert_one({
            "_id": user_id,
            "username": username,
            "first_name": first_name,
            "points": 10,
            "vip": False,
            "refs": 0,
            "created_at": time.time(),
            "last_active": time.time()
        })
        msg = "🎉 Welcome! You got 10 free points!"
    
    bot.send_message(
        message.chat.id,
        f"{msg}\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Name: {first_name or 'Unknown'}\n"
        f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"<b>Use the menu to test MongoDB!</b>",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📂 FREE METHODS")
def show_free(message):
    """Read from MongoDB - FREE methods"""
    folders = list(folders_col.find({"cat": "free", "parent": None}))
    
    if not folders:
        bot.send_message(message.chat.id, "❌ No free methods in database!")
        return
    
    text = f"📂 <b>FREE METHODS</b> (from MongoDB)\n\n"
    for f in folders:
        text += f"📄 [{f['number']}] {f['name']} - {f['price']} pts\n"
    text += f"\n📊 Total: <code>{len(folders)}</code> documents"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "💎 VIP METHODS")
def show_vip(message):
    """Read from MongoDB - VIP methods with subfolders"""
    folders = list(folders_col.find({"cat": "vip", "parent": None}))
    
    if not folders:
        bot.send_message(message.chat.id, "❌ No VIP methods in database!")
        return
    
    text = f"💎 <b>VIP METHODS</b> (from MongoDB)\n\n"
    for f in folders:
        sub_count = folders_col.count_documents({"cat": "vip", "parent": f["name"]})
        text += f"📄 [{f['number']}] {f['name']} - {f['price']} pts"
        if sub_count > 0:
            text += f" (📁 {sub_count} sub-folders)"
        text += "\n"
    text += f"\n📊 Total: <code>{len(folders)}</code> documents"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📊 DATABASE STATS")
def show_db_stats(message):
    """Show MongoDB statistics"""
    total_users = users_col.count_documents({})
    vip_users = users_col.count_documents({"vip": True})
    free_users = total_users - vip_users
    
    total_free = folders_col.count_documents({"cat": "free"})
    total_vip = folders_col.count_documents({"cat": "vip"})
    total_folders = folders_col.count_documents({})
    
    # Calculate total points using aggregation
    pipeline = [
        {"$group": {"_id": None, "total_points": {"$sum": "$points"}}}
    ]
    result = list(users_col.aggregate(pipeline))
    total_points = result[0]["total_points"] if result else 0
    
    # Average points
    avg_points = total_points / total_users if total_users > 0 else 0
    
    text = (
        f"📊 <b>MONGODB STATISTICS</b>\n\n"
        f"👥 <b>Users Collection:</b>\n"
        f"├ Total Documents: <code>{total_users}</code>\n"
        f"├ VIP Users: <code>{vip_users}</code>\n"
        f"├ Free Users: <code>{free_users}</code>\n"
        f"├ Total Points: <code>{total_points:,}</code>\n"
        f"└ Avg Points: <code>{avg_points:.1f}</code>\n\n"
        f"📁 <b>Folders Collection:</b>\n"
        f"├ Total Documents: <code>{total_folders}</code>\n"
        f"├ Free Methods: <code>{total_free}</code>\n"
        f"└ VIP Methods: <code>{total_vip}</code>\n\n"
        f"📡 <b>Connection:</b> MongoDB Atlas ✅"
    )
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "👤 MY PROFILE")
def show_profile(message):
    """Show user data from MongoDB"""
    user_id = str(message.from_user.id)
    user = users_col.find_one({"_id": user_id})
    
    if not user:
        bot.send_message(message.chat.id, "❌ Not in database! Send /start first")
        return
    
    vip_status = "💎 VIP" if user.get("vip") else "🆓 Free"
    created = datetime.fromtimestamp(user.get("created_at", time.time()))
    last_active = datetime.fromtimestamp(user.get("last_active", time.time()))
    
    text = (
        f"👤 <b>YOUR MONGODB PROFILE</b>\n\n"
        f"🆔 ID: <code>{user['_id']}</code>\n"
        f"👤 Username: @{user.get('username', 'None')}\n"
        f"📝 Name: {user.get('first_name', 'None')}\n"
        f"💰 Points: <code>{user.get('points', 0)}</code>\n"
        f"💎 Status: {vip_status}\n"
        f"👥 Referrals: {user.get('refs', 0)}\n"
        f"📅 Created: {created.strftime('%Y-%m-%d %H:%M')}\n"
        f"🕐 Last Active: {last_active.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"✅ Data loaded from MongoDB"
    )
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🔄 REFRESH DATA")
def refresh_data(message):
    """Refresh and show updated counts"""
    user_count = users_col.count_documents({})
    folder_count = folders_col.count_documents({})
    
    bot.send_message(
        message.chat.id,
        f"🔄 <b>DATA REFRESHED</b>\n\n"
        f"👥 Users: <code>{user_count}</code>\n"
        f"📁 Folders: <code>{folder_count}</code>\n\n"
        f"✅ All data loaded from MongoDB!",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🔍 CHECK DB")
def check_database(message):
    """Direct MongoDB connection test"""
    try:
        start = time.time()
        client.admin.command('ping')
        ping_ms = (time.time() - start) * 1000
        
        db_names = client.list_database_names()
        
        text = (
            f"🔍 <b>DATABASE CHECK</b>\n\n"
            f"📡 Status: <b>✅ CONNECTED</b>\n"
            f"⚡ Ping: <code>{ping_ms:.1f}ms</code>\n"
            f"📚 Database: <code>zedox_test</code>\n"
            f"📋 Collections: users, folders, config\n"
            f"🗄️ All DBs: {', '.join(db_names[:5])}\n\n"
            f"🔗 URI: <code>{MONGO_URI[:30]}...</code>"
        )
        
    except Exception as e:
        text = f"❌ <b>DATABASE ERROR</b>\n\n<code>{str(e)[:200]}</code>"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📋 LIST DATA")
def list_all_data(message):
    """List all collections data"""
    users = list(users_col.find({}).limit(5))
    folders = list(folders_col.find({}).limit(5))
    
    text = "📋 <b>MONGODB DATA</b>\n\n"
    
    text += "<b>👥 Users:</b>\n"
    if users:
        for u in users:
            text += f"• <code>{u['_id']}</code> - {u.get('first_name','?')} - {u.get('points',0)} pts\n"
    else:
        text += "No users\n"
    
    text += "\n<b>📁 Folders:</b>\n"
    if folders:
        for f in folders:
            text += f"• [{f['number']}] {f['name']} ({f['cat']})\n"
    else:
        text += "No folders\n"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "ℹ️ HELP")
def help_cmd(message):
    text = (
        "ℹ️ <b>TEST BOT - HELP</b>\n\n"
        "<b>Testing:</b>\n"
        "✅ MongoDB Connection\n"
        "✅ Environment Variables\n"
        "✅ CRUD Operations\n\n"
        "<b>Buttons:</b>\n"
        "• FREE METHODS - Read free methods\n"
        "• VIP METHODS - Read VIP methods\n"
        "• DATABASE STATS - Collection stats\n"
        "• MY PROFILE - Your MongoDB data\n"
        "• REFRESH DATA - Refresh counts\n"
        "• CHECK DB - Test connection\n"
        "• LIST DATA - Show all data\n\n"
        "<b>Admin Commands:</b>\n"
        "/add [amount] - Add points to yourself\n"
        "/vip - Make yourself VIP\n"
        "/users - List all users\n"
        "/folders - List all folders"
    )
    
    bot.send_message(message.chat.id, text)

# =========================
# ADMIN COMMANDS
# =========================
@bot.message_handler(commands=["add"])
def add_points(message):
    """Add points to yourself"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    try:
        amount = int(message.text.split()[1]) if len(message.text.split()) > 1 else 10
    except:
        amount = 10
    
    user_id = str(message.from_user.id)
    
    # Update MongoDB
    result = users_col.update_one(
        {"_id": user_id},
        {"$inc": {"points": amount}}
    )
    
    if result.modified_count > 0:
        user = users_col.find_one({"_id": user_id})
        bot.reply_to(
            message,
            f"✅ <b>Points Added!</b>\n\n"
            f"➕ Amount: +{amount}\n"
            f"💰 Balance: {user['points']} pts\n"
            f"📝 MongoDB: Updated ✅"
        )
    else:
        bot.reply_to(message, "❌ Failed! Send /start first.")

@bot.message_handler(commands=["vip"])
def make_vip_cmd(message):
    """Make yourself VIP"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    user_id = str(message.from_user.id)
    result = users_col.update_one(
        {"_id": user_id},
        {"$set": {"vip": True}}
    )
    
    if result.modified_count > 0:
        bot.reply_to(message, "✅ You are now VIP! 💎\nMongoDB: Updated ✅")
    else:
        bot.reply_to(message, "❌ Failed! Send /start first.")

@bot.message_handler(commands=["users"])
def list_users_cmd(message):
    """List all users"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    users = list(users_col.find({}))
    
    if not users:
        bot.reply_to(message, "❌ No users in MongoDB!")
        return
    
    text = f"👥 <b>USERS IN MONGODB</b> ({len(users)} total)\n\n"
    for i, u in enumerate(users[:20], 1):
        name = u.get('first_name') or u.get('username') or 'Unknown'
        vip = "💎" if u.get('vip') else "🆓"
        text += f"{i}. {vip} <code>{u['_id']}</code> - {name} - {u.get('points',0)} pts\n"
    
    if len(users) > 20:
        text += f"\n... and {len(users)-20} more"
    
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["folders"])
def list_folders_cmd(message):
    """List all folders"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    folders = list(folders_col.find({}))
    
    if not folders:
        bot.reply_to(message, "❌ No folders in MongoDB!")
        return
    
    text = f"📁 <b>FOLDERS IN MONGODB</b> ({len(folders)} total)\n\n"
    for f in folders[:20]:
        parent = f" (in {f['parent']})" if f.get('parent') else ""
        text += f"• [{f['number']}] {f['name']} - {f['cat']}{parent} - {f['price']} pts\n"
    
    bot.send_message(message.chat.id, text)

# =========================
# START BOT
# =========================
if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🚀 BOT IS STARTING")
    print("=" * 50)
    print(f"🤖 Bot: @{bot_info.username}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"💾 MongoDB: Connected")
    print(f"👥 Users: {users_col.count_documents({})}")
    print(f"📁 Folders: {folders_col.count_documents({})}")
    print("=" * 50)
    print("✅ Bot is running!")
    print("📱 Send /start in Telegram to test")
    print("=" * 50)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(5)
