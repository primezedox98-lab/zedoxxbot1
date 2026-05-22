"""
ZEDOX Bot - Minimal Test Version
Tests MongoDB connection, environment variables, and basic functionality
"""

import os
import time
from datetime import datetime
from pymongo import MongoClient
import telebot
from telebot.types import ReplyKeyboardMarkup

# =========================
# ENVIRONMENT VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI")

# Check if variables exist
print("=" * 50)
print("🔍 CHECKING ENVIRONMENT VARIABLES")
print("=" * 50)
print(f"BOT_TOKEN: {'✅ SET' if BOT_TOKEN else '❌ MISSING'}")
print(f"ADMIN_ID: {'✅ SET' if ADMIN_ID else '❌ MISSING'}")
print(f"MONGO_URI: {'✅ SET' if MONGO_URI else '❌ MISSING'}")

if not all([BOT_TOKEN, ADMIN_ID, MONGO_URI]):
    raise ValueError("Missing required environment variables!")

# =========================
# MONGODB CONNECTION
# =========================
print("\n📦 CONNECTING TO MONGODB...")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["zedox_test"]
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")
    raise

# Collections
users_col = db["users"]
folders_col = db["folders"]

# Create test data if empty
if users_col.count_documents({}) == 0:
    print("\n📝 Creating test users...")
    test_users = [
        {"_id": "111111", "username": "test_user1", "points": 100, "vip": True, "created_at": time.time()},
        {"_id": "222222", "username": "test_user2", "points": 50, "vip": False, "created_at": time.time()},
        {"_id": "333333", "username": "test_user3", "points": 200, "vip": True, "created_at": time.time()},
    ]
    users_col.insert_many(test_users)
    print(f"✅ Created {len(test_users)} test users")

if folders_col.count_documents({}) == 0:
    print("📝 Creating test folders...")
    test_folders = [
        {"cat": "free", "name": "Free Method 1", "price": 0, "number": 1, "files": [], "parent": None},
        {"cat": "free", "name": "Free Method 2", "price": 0, "number": 2, "files": [], "parent": None},
        {"cat": "vip", "name": "VIP Method 1", "price": 50, "number": 3, "files": [], "parent": None},
        {"cat": "vip", "name": "VIP Method 2", "price": 100, "number": 4, "files": [], "parent": None},
        {"cat": "vip", "name": "Sub Folder", "price": 30, "number": 5, "files": [], "parent": "VIP Method 1"},
    ]
    folders_col.insert_many(test_folders)
    print(f"✅ Created {len(test_folders)} test folders")

# =========================
# BOT SETUP
# =========================
bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# MAIN MENU
# =========================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📂 FREE METHODS", "💎 VIP METHODS")
    kb.add("📊 STATS", "👤 MY INFO")
    kb.add("🔄 REFRESH", "ℹ️ HELP")
    return kb

# =========================
# COMMANDS
# =========================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    
    # Save/update user
    user = users_col.find_one({"_id": user_id})
    if not user:
        users_col.insert_one({
            "_id": user_id,
            "username": message.from_user.username,
            "points": 0,
            "vip": False,
            "created_at": time.time()
        })
        print(f"✅ New user registered: {user_id}")
    else:
        users_col.update_one(
            {"_id": user_id},
            {"$set": {"username": message.from_user.username}}
        )
    
    bot.send_message(
        message.chat.id,
        "✅ <b>ZEDOX BOT - TEST VERSION</b>\n\n"
        "This is a minimal bot to test MongoDB.\n"
        "Use the menu below to check data.",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "📂 FREE METHODS")
def show_free_methods(message):
    """Show free methods from MongoDB"""
    folders = list(folders_col.find({"cat": "free", "parent": None}))
    
    if not folders:
        bot.send_message(message.chat.id, "📂 No free methods in database!")
        return
    
    text = "📂 <b>FREE METHODS</b>\n\n"
    for folder in folders:
        text += f"• [{folder['number']}] {folder['name']}\n"
    
    text += f"\n📊 Total: {len(folders)} methods"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💎 VIP METHODS")
def show_vip_methods(message):
    """Show VIP methods from MongoDB"""
    folders = list(folders_col.find({"cat": "vip", "parent": None}))
    
    if not folders:
        bot.send_message(message.chat.id, "💎 No VIP methods in database!")
        return
    
    text = "💎 <b>VIP METHODS</b>\n\n"
    for folder in folders:
        # Check for subfolders
        sub_count = folders_col.count_documents({"cat": "vip", "parent": folder["name"]})
        text += f"• [{folder['number']}] {folder['name']} - {folder['price']} pts"
        if sub_count > 0:
            text += f" 📁({sub_count} sub)"
        text += "\n"
    
    text += f"\n📊 Total: {len(folders)} methods"
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📊 STATS")
def show_stats(message):
    """Show database statistics"""
    total_users = users_col.count_documents({})
    vip_users = users_col.count_documents({"vip": True})
    free_users = total_users - vip_users
    
    total_free = folders_col.count_documents({"cat": "free"})
    total_vip = folders_col.count_documents({"cat": "vip"})
    
    # Get total points
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$points"}}}]
    result = list(users_col.aggregate(pipeline))
    total_points = result[0]["total"] if result else 0
    
    text = (
        f"📊 <b>DATABASE STATISTICS</b>\n\n"
        f"👥 <b>Users:</b>\n"
        f"├ Total: <code>{total_users}</code>\n"
        f"├ VIP: <code>{vip_users}</code>\n"
        f"└ Free: <code>{free_users}</code>\n\n"
        f"📁 <b>Methods:</b>\n"
        f"├ Free: <code>{total_free}</code>\n"
        f"└ VIP: <code>{total_vip}</code>\n\n"
        f"💰 <b>Points:</b>\n"
        f"└ Total in circulation: <code>{total_points:,}</code>\n\n"
        f"🕐 <b>Connected to:</b> MongoDB Atlas"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👤 MY INFO")
def show_my_info(message):
    """Show current user info from MongoDB"""
    user_id = str(message.from_user.id)
    user = users_col.find_one({"_id": user_id})
    
    if not user:
        bot.send_message(message.chat.id, "❌ You're not registered! Send /start")
        return
    
    vip_status = "✅ VIP" if user.get("vip") else "❌ Free"
    
    text = (
        f"👤 <b>YOUR INFO</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{user.get('username', 'None')}\n"
        f"💰 Points: <code>{user.get('points', 0)}</code>\n"
        f"💎 Status: {vip_status}\n"
        f"📅 Joined: {datetime.fromtimestamp(user.get('created_at', time.time())).strftime('%Y-%m-%d %H:%M')}"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🔄 REFRESH")
def refresh(message):
    """Refresh data"""
    bot.send_message(
        message.chat.id,
        "✅ Data refreshed from MongoDB!\n\nUse the menu to check updated data.",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ HELP")
def help_cmd(message):
    """Show help"""
    text = (
        "ℹ️ <b>TEST BOT HELP</b>\n\n"
        "This bot tests:\n"
        "✅ MongoDB Connection\n"
        "✅ Environment Variables\n"
        "✅ Data Storage\n"
        "✅ Data Retrieval\n\n"
        "<b>Buttons:</b>\n"
        "• FREE METHODS - Shows free methods\n"
        "• VIP METHODS - Shows VIP methods\n"
        "• STATS - Database statistics\n"
        "• MY INFO - Your user data\n"
        "• REFRESH - Refresh data\n\n"
        "<b>Admin Commands:</b>\n"
        "/add_points [amount] - Add points to yourself\n"
        "/make_vip - Make yourself VIP\n"
        "/check_db - Check database connection"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# =========================
# ADMIN COMMANDS
# =========================
@bot.message_handler(commands=["add_points"])
def add_points(message):
    """Add points to yourself (admin only)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    try:
        amount = int(message.text.split()[1]) if len(message.text.split()) > 1 else 100
    except:
        amount = 100
    
    user_id = str(message.from_user.id)
    
    # Update in MongoDB
    result = users_col.update_one(
        {"_id": user_id},
        {"$inc": {"points": amount}}
    )
    
    # Get updated user
    user = users_col.find_one({"_id": user_id})
    
    bot.reply_to(
        message,
        f"✅ Added {amount} points!\n"
        f"💰 New balance: {user['points']} points\n\n"
        f"📝 MongoDB Update: {'Success' if result.modified_count > 0 else 'Failed'}"
    )

@bot.message_handler(commands=["make_vip"])
def make_vip(message):
    """Make yourself VIP (admin only)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    user_id = str(message.from_user.id)
    
    # Update in MongoDB
    result = users_col.update_one(
        {"_id": user_id},
        {"$set": {"vip": True}}
    )
    
    bot.reply_to(
        message,
        f"✅ You are now VIP!\n\n"
        f"📝 MongoDB Update: {'Success' if result.modified_count > 0 else 'Failed'}"
    )

@bot.message_handler(commands=["check_db"])
def check_db(message):
    """Check database connection status"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    try:
        # Test MongoDB
        start = time.time()
        client.admin.command('ping')
        ping_time = (time.time() - start) * 1000
        
        # Get stats
        total_users = users_col.count_documents({})
        total_folders = folders_col.count_documents({})
        
        text = (
            "✅ <b>DATABASE STATUS</b>\n\n"
            f"📡 Connection: <b>ACTIVE</b>\n"
            f"⚡ Ping: <code>{ping_time:.1f}ms</code>\n"
            f"👥 Users: <code>{total_users}</code>\n"
            f"📁 Folders: <code>{total_folders}</code>\n\n"
            f"🔗 URI: <code>{MONGO_URI[:30]}...</code>"
        )
        
    except Exception as e:
        text = f"❌ <b>DATABASE ERROR</b>\n\n<code>{str(e)}</code>"
    
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=["list_users"])
def list_users(message):
    """List all users (admin only)"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    
    users = list(users_col.find({}).limit(10))
    
    if not users:
        bot.reply_to(message, "❌ No users in database!")
        return
    
    text = "👥 <b>RECENT USERS</b>\n\n"
    for i, user in enumerate(users, 1):
        username = user.get("username") or "Unknown"
        points = user.get("points", 0)
        vip = "💎" if user.get("vip") else "🆓"
        text += f"{i}. {vip} <code>{user['_id']}</code> (@{username}) - {points} pts\n"
    
    bot.reply_to(message, text, parse_mode="HTML")

# =========================
# START BOT
# =========================
print("\n" + "=" * 50)
print("🤖 BOT STARTING...")
print("=" * 50)

try:
    bot_info = bot.get_me()
    print(f"✅ Bot Name: {bot_info.first_name}")
    print(f"✅ Bot Username: @{bot_info.username}")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ MongoDB: Connected")
    print(f"✅ Users in DB: {users_col.count_documents({})}")
    print(f"✅ Folders in DB: {folders_col.count_documents({})}")
    print("=" * 50)
    print("🚀 Bot is running... Press Ctrl+C to stop")
    print("=" * 50)
    
    # Start polling
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
    
except Exception as e:
    print(f"❌ Error starting bot: {e}")
    raise
