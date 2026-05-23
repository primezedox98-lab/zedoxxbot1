"""
ZEDOX BOT - COMPLETE RAILWAY VERSION
"""
import os
import sys
import time
import random
import string
import threading
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from pymongo import MongoClient
from flask import Flask

# =========================
# FLASK FOR RAILWAY
# =========================
app = Flask(__name__)

@app.route('/')
def home():
    return "ZEDOX Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

# =========================
# ENVIRONMENT VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
MONGO_URI = os.getenv("MONGO_URI")

print("=" * 60)
print("🔍 ZEDOX BOT - ENVIRONMENT CHECK")
print("=" * 60)

if not BOT_TOKEN:
    print("❌ BOT_TOKEN missing!")
    sys.exit(1)
if not ADMIN_ID:
    print("❌ ADMIN_ID missing!")
    sys.exit(1)
if not MONGO_URI:
    print("❌ MONGO_URI missing!")
    sys.exit(1)

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
# MONGODB SETUP
# =========================
print("\n📦 CONNECTING TO MONGODB...")
try:
    client = MongoClient(MONGO_URI, maxPoolSize=50, minPoolSize=10, connectTimeoutMS=5000, socketTimeoutMS=5000, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB Connected!")
    
    db = client["zedox_complete"]
    users_col = db["users"]
    folders_col = db["folders"]
    codes_col = db["codes"]
    config_col = db["config"]
    custom_buttons_col = db["custom_buttons"]
    admins_col = db["admins"]
    payments_col = db["payments"]
    
    # Create indexes
    users_col.create_index("points")
    users_col.create_index("vip")
    users_col.create_index("refs")
    folders_col.create_index([("cat", 1), ("parent", 1)])
    folders_col.create_index("number", unique=True, sparse=True)
    print("✅ Indexes ready")
    
except Exception as e:
    print(f"❌ MongoDB Error: {e}")
    sys.exit(1)

# =========================
# BOT INIT
# =========================
print("\n🤖 STARTING BOT...")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Remove webhook to avoid conflicts
bot.remove_webhook()
time.sleep(1)

try:
    bot_info = bot.get_me()
    print(f"✅ Bot: @{bot_info.username}")
except Exception as e:
    print(f"❌ Bot Error: {e}")
    sys.exit(1)

# =========================
# CONFIG SYSTEM
# =========================
_config_cache = None
_config_cache_time = 0
CACHE_TTL = 30

def get_cached_config():
    global _config_cache, _config_cache_time
    now = time.time()
    if _config_cache is not None and (now - _config_cache_time) < CACHE_TTL:
        return _config_cache
    _config_cache = get_config()
    _config_cache_time = now
    return _config_cache

def get_config():
    cfg = config_col.find_one({"_id": "config"})
    if cfg is None:
        cfg = {
            "_id": "config",
            "force_channels": [],
            "custom_buttons": [],
            "vip_msg": "💎 Buy VIP to unlock this!",
            "welcome": "🔥 Welcome to ZEDOX BOT",
            "ref_reward": 5,
            "notify": True,
            "purchase_msg": "💰 Purchase VIP to access premium features!",
            "next_folder_number": 1,
            "points_per_dollar": 100,
            "contact_username": None,
            "contact_link": None,
            "vip_contact": None,
            "vip_price": 50,
            "vip_points_price": 5000,
            "payment_methods": ["💳 Binance", "💵 USDT (TRC20)", "💰 Bank Transfer", "🪙 Bitcoin"],
            "referral_vip_count": 50,
            "referral_purchase_count": 10,
            "vip_duration_days": 30,
            "binance_coin": "USDT",
            "binance_network": "TRC20",
            "binance_address": "",
            "binance_memo": "",
            "require_screenshot": True
        }
        config_col.insert_one(cfg)
    return cfg

def set_config(key, value):
    global _config_cache
    _config_cache = None
    config_col.update_one({"_id": "config"}, {"$set": {key: value}}, upsert=True)

# =========================
# ADMIN SYSTEM
# =========================
def init_admins():
    if admins_col.find_one({"_id": ADMIN_ID}) is None:
        admins_col.insert_one({
            "_id": ADMIN_ID,
            "username": None,
            "added_by": "system",
            "added_at": time.time(),
            "is_owner": True
        })

init_admins()

def is_admin(uid):
    uid = int(uid) if isinstance(uid, str) else uid
    if uid == ADMIN_ID:
        return True
    return admins_col.find_one({"_id": uid}) is not None

# =========================
# USER SYSTEM
# =========================
class User:
    _cache = {}
    _cache_time = {}
    
    def __init__(self, uid):
        self.uid = str(uid)
        
        if uid in self._cache and (time.time() - self._cache_time.get(uid, 0)) < 30:
            self.data = self._cache[uid]
            return
        
        data = users_col.find_one({"_id": self.uid})
        
        if data is None:
            data = {
                "_id": self.uid,
                "points": 0,
                "vip": False,
                "vip_expiry": None,
                "ref": None,
                "refs": 0,
                "refs_who_bought_vip": 0,
                "purchased_methods": [],
                "used_codes": [],
                "username": None,
                "created_at": time.time(),
                "last_active": time.time(),
                "total_points_earned": 0,
                "total_points_spent": 0
            }
            users_col.insert_one(data)
        
        self.data = data
        self._cache[uid] = data
        self._cache_time[uid] = time.time()
    
    def save(self):
        users_col.update_one({"_id": self.uid}, {"$set": self.data})
        self._cache[self.uid] = self.data
        self._cache_time[self.uid] = time.time()
    
    def is_vip(self):
        if self.data.get("vip", False):
            expiry = self.data.get("vip_expiry")
            if expiry is not None and expiry < time.time():
                self.data["vip"] = False
                self.data["vip_expiry"] = None
                self.save()
                return False
            return True
        return False
    
    def points(self): 
        return self.data.get("points", 0)
    
    def purchased_methods(self): 
        return self.data.get("purchased_methods", [])
    
    def username(self): 
        return self.data.get("username", None)
    
    def update_username(self, username):
        if username != self.data.get("username"):
            self.data["username"] = username
            self.save()
    
    def add_points(self, p):
        self.data["points"] += p
        self.data["total_points_earned"] = self.data.get("total_points_earned", 0) + p
        self.save()
    
    def spend_points(self, p):
        self.data["points"] -= p
        self.data["total_points_spent"] = self.data.get("total_points_spent", 0) + p
        self.save()
    
    def make_vip(self, duration_days=None):
        self.data["vip"] = True
        if duration_days is not None and duration_days > 0:
            self.data["vip_expiry"] = time.time() + (duration_days * 86400)
        else:
            self.data["vip_expiry"] = None
        self.save()
    
    def remove_vip(self):
        self.data["vip"] = False
        self.data["vip_expiry"] = None
        self.save()
    
    def purchase_method(self, method_name, price):
        if self.points() >= price:
            self.spend_points(price)
            if method_name not in self.purchased_methods():
                self.data["purchased_methods"].append(method_name)
                self.save()
            return True
        return False
    
    def can_access_method(self, method_name):
        return self.is_vip() or method_name in self.purchased_methods()
    
    def add_ref(self):
        self.data["refs"] = self.data.get("refs", 0) + 1
        self.save()
        
        config = get_cached_config()
        required_refs = config.get("referral_vip_count", 50)
        
        if self.data["refs"] >= required_refs and not self.is_vip():
            self.make_vip(config.get("vip_duration_days", 30))
            return True
        return False
    
    def get_refs_count(self):
        return self.data.get("refs", 0)

# =========================
# FOLDER SYSTEM
# =========================
class FS:
    def add(self, cat, name, files, price, parent=None, number=None, text_content=None):
        if number is None:
            config = get_config()
            number = config.get("next_folder_number", 1)
            set_config("next_folder_number", number + 1)
        
        folder_data = {
            "cat": cat,
            "name": name,
            "files": files,
            "price": price,
            "parent": parent,
            "number": number,
            "created_at": time.time()
        }
        
        if text_content:
            folder_data["text_content"] = text_content
        
        folders_col.insert_one(folder_data)
        return number
    
    def get(self, cat, parent=None):
        query = {"cat": cat}
        if parent is not None:
            query["parent"] = parent
        else:
            query["parent"] = None
        return list(folders_col.find(query).sort("number", 1))
    
    def get_one(self, cat, name, parent=None):
        query = {"cat": cat, "name": name}
        if parent is not None:
            query["parent"] = parent
        return folders_col.find_one(query)
    
    def get_by_number(self, number):
        return folders_col.find_one({"number": number})
    
    def delete(self, cat, name, parent=None):
        query = {"cat": cat, "name": name}
        if parent is not None:
            query["parent"] = parent
        else:
            query["parent"] = None
        
        folders_col.delete_one(query)
        return True
    
    def edit_price(self, cat, name, price, parent=None):
        query = {"cat": cat, "name": name}
        if parent is not None:
            query["parent"] = parent
        folders_col.update_one(query, {"$set": {"price": price}})

fs = FS()

# =========================
# CODES SYSTEM
# =========================
class Codes:
    def generate(self, pts, count, multi_use=False, expiry_days=None):
        res = []
        expiry = time.time() + (expiry_days * 86400) if expiry_days else None
        
        for _ in range(count):
            code = "ZEDOX" + ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))
            while codes_col.find_one({"_id": code}) is not None:
                code = "ZEDOX" + ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))
            
            codes_col.insert_one({
                "_id": code,
                "points": pts,
                "used": False,
                "multi_use": multi_use,
                "used_count": 0,
                "max_uses": 0 if not multi_use else 10,
                "expiry": expiry,
                "created_at": time.time(),
                "used_by_users": []
            })
            res.append(code)
        return res
    
    def redeem(self, code, user):
        code_data = codes_col.find_one({"_id": code})
        
        if code_data is None:
            return False, 0, "invalid"
        
        if code_data.get("expiry") and time.time() > code_data["expiry"]:
            return False, 0, "expired"
        
        if not code_data.get("multi_use", False) and code_data.get("used", False):
            return False, 0, "already_used"
        
        if user.uid in code_data.get("used_by_users", []):
            return False, 0, "already_used_by_user"
        
        pts = code_data["points"]
        user.add_points(pts)
        
        update_data = {
            "$push": {"used_by_users": user.uid},
            "$inc": {"used_count": 1}
        }
        
        if not code_data.get("multi_use", False):
            update_data["$set"] = {"used": True}
        
        codes_col.update_one({"_id": code}, update_data)
        
        return True, pts, "success"

codesys = Codes()

# =========================
# FORCE JOIN
# =========================
def force_block(uid):
    if is_admin(uid):
        return False
    
    cfg = get_cached_config()
    force_channels = cfg.get("force_channels", [])
    
    if not force_channels:
        return False
    
    not_joined = []
    for ch in force_channels:
        try:
            chat_id = ch.replace("@", "")
            member = bot.get_chat_member(f"@{chat_id}", uid)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)
    
    if not_joined:
        kb = InlineKeyboardMarkup()
        for channel in force_channels:
            chat_id = channel.replace("@", "")
            kb.add(InlineKeyboardButton(f"📢 Join {channel}", url=f"https://t.me/{chat_id}"))
        kb.add(InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(uid, "🚫 <b>Access Restricted!</b>\n\nPlease join the following channels:", reply_markup=kb)
        return True
    
    return False

def force_join_handler(func):
    @wraps(func)
    def wrapper(message):
        if force_block(message.from_user.id):
            return
        return func(message)
    return wrapper

# =========================
# KEYBOARDS
# =========================
def get_custom_buttons():
    cfg = get_cached_config()
    return cfg.get("custom_buttons", [])

def main_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    kb.add("📂 FREE METHODS", "💎 VIP METHODS")
    kb.add("📦 PREMIUM APPS", "⚡ SERVICES")
    kb.add("💰 POINTS", "⭐ BUY VIP")
    
    custom_btns = get_custom_buttons()
    for btn in custom_btns:
        kb.add(btn["text"])
    
    kb.add("🎁 REFERRAL", "👤 ACCOUNT")
    kb.add("📚 MY METHODS", "💎 GET POINTS")
    kb.add("🆔 CHAT ID", "🏆 REDEEM")
    
    if is_admin(uid):
        kb.add("⚙️ ADMIN PANEL")
    
    return kb

def admin_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row("📦 Upload FREE", "💎 Upload VIP")
    kb.row("📁 Create Subfolder", "🗑 Delete Folder")
    kb.row("✏️ Edit Price", "✏️ Edit Name")
    kb.row("👑 Add VIP", "👑 Remove VIP")
    kb.row("💰 Give Points", "🎫 Generate Codes")
    kb.row("📊 Stats", "📢 Broadcast")
    kb.row("➕ Add Channel", "➖ Remove Channel")
    kb.row("⚙️ Settings", "📊 Leaderboard")
    kb.row("❌ Exit")
    return kb

# =========================
# BOT HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def start_cmd(m):
    uid = m.from_user.id
    args = m.text.split()
    
    user = User(uid)
    
    if m.from_user.username:
        user.update_username(m.from_user.username)
    
    if len(args) > 1:
        ref_id = args[1]
        if ref_id != str(uid) and ref_id.isdigit():
            ref_user = User(ref_id)
            if not user.data.get("ref"):
                reward = get_cached_config().get("ref_reward", 5)
                ref_user.add_points(reward)
                got_vip = ref_user.add_ref()
                user.data["ref"] = ref_id
                user.save()
                
                try:
                    vip_msg = ""
                    if got_vip:
                        vip_msg = f"\n\n🎉 <b>CONGRATULATIONS!</b> 🎉\nYou've reached {ref_user.get_refs_count()} referrals and got <b>FREE VIP ACCESS</b>!"
                    
                    bot.send_message(int(ref_id), 
                        f"👤 <b>New Referral Alert!</b>\n\n"
                        f"✨ <b>@{user.username() or user.uid}</b> just joined!\n\n"
                        f"💰 You earned <b>+{reward} points</b>!\n"
                        f"📊 Total Referrals: <b>{ref_user.get_refs_count()}</b>\n"
                        f"💎 Total Points: <b>{ref_user.points()}</b>{vip_msg}")
                except:
                    pass
    
    if force_block(uid):
        return
    
    cfg = get_cached_config()
    welcome_msg = cfg.get("welcome", "🔥 Welcome to ZEDOX BOT!")
    
    bot.send_message(uid, f"{welcome_msg}\n\n💰 Your points: <b>{user.points()}</b>", reply_markup=main_menu(uid))

@bot.message_handler(func=lambda m: m.text == "💰 POINTS")
@force_join_handler
def points_cmd(m):
    uid = m.from_user.id
    user = User(uid)
    
    purchased_count = len(user.purchased_methods())
    ref_count = user.get_refs_count()
    
    points_msg = f"💰 <b>YOUR POINTS BALANCE</b> 💰\n\n"
    points_msg += f"┌ <b>Points:</b> <code>{user.points()}</code>\n"
    points_msg += f"├ <b>VIP Status:</b> {'✅ Active' if user.is_vip() else '❌ Not Active'}\n"
    points_msg += f"├ <b>Purchased Methods:</b> <code>{purchased_count}</code>\n"
    points_msg += f"├ <b>Total Referrals:</b> <code>{ref_count}</code>\n"
    points_msg += f"├ <b>Total Earned:</b> <code>{user.data.get('total_points_earned', 0)}</code>\n"
    points_msg += f"└ <b>Total Spent:</b> <code>{user.data.get('total_points_spent', 0)}</code>\n\n"
    
    points_msg += f"✨ <b>Ways to Earn Points:</b>\n"
    points_msg += f"• 🎁 <b>Referral System:</b> Share your link\n"
    points_msg += f"• 🏆 <b>Redeem Codes:</b> Use coupon codes\n"
    points_msg += f"• 💎 <b>Purchase:</b> Click 💎 GET POINTS button\n\n"
    
    cfg = get_cached_config()
    points_msg += f"🎯 <b>Referral Rewards:</b>\n"
    points_msg += f"• Invite {cfg.get('referral_vip_count', 50)} users → <b>FREE VIP</b>\n"
    points_msg += f"• {cfg.get('referral_purchase_count', 10)} referrals buy VIP → <b>FREE VIP</b>"
    
    bot.send_message(uid, points_msg)

@bot.message_handler(func=lambda m: m.text == "📂 FREE METHODS")
@force_join_handler
def show_free_methods(m):
    uid = m.from_user.id
    data = fs.get("free")
    
    if not data:
        bot.send_message(uid, "📂 No free methods available!")
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    for item in data[:30]:
        name = item["name"]
        number = item.get("number", "?")
        subfolders = fs.get("free", name)
        icon = "📁" if subfolders else "📄"
        text = f"{icon} [{number}] {name}"
        kb.add(InlineKeyboardButton(text, callback_data=f"open|free|{name}|"))
    
    bot.send_message(uid, "📂 <b>FREE METHODS</b>\n\nSelect a method:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💎 VIP METHODS")
@force_join_handler
def show_vip_methods(m):
    uid = m.from_user.id
    user = User(uid)
    data = fs.get("vip")
    
    if not data:
        bot.send_message(uid, "💎 No VIP methods available!")
        return
    
    if not user.is_vip():
        bot.send_message(uid, "🔒 <b>VIP REQUIRED</b>\n\nUse ⭐ BUY VIP to get access!")
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    for item in data[:30]:
        name = item["name"]
        price = item.get("price", 0)
        number = item.get("number", "?")
        subfolders = fs.get("vip", name)
        icon = "📁" if subfolders else "📄"
        text = f"{icon} [{number}] {name}"
        if price > 0:
            text += f" [{price} pts]"
        kb.add(InlineKeyboardButton(text, callback_data=f"open|vip|{name}|"))
    
    bot.send_message(uid, "💎 <b>VIP METHODS</b>\n\nSelect a method:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open|"))
def open_folder(c):
    uid = c.from_user.id
    user = User(uid)
    
    parts = c.data.split("|")
    cat = parts[1]
    name = parts[2]
    
    folder = fs.get_one(cat, name)
    
    if folder is None:
        bot.answer_callback_query(c.id, "❌ Folder not found")
        return
    
    # Check for subfolders
    subfolders = fs.get(cat, name)
    
    if subfolders and len(subfolders) > 0:
        kb = InlineKeyboardMarkup(row_width=1)
        for sub in subfolders:
            sub_name = sub["name"]
            sub_number = sub.get("number", "?")
            deeper = fs.get(cat, sub_name)
            icon = "📁" if deeper else "📄"
            text = f"{icon} [{sub_number}] {sub_name}"
            if sub.get("price", 0) > 0:
                text += f" - {sub['price']} pts"
            kb.add(InlineKeyboardButton(text, callback_data=f"open|{cat}|{sub_name}|"))
        
        kb.add(InlineKeyboardButton("🔙 BACK", callback_data=f"back|{cat}|"))
        
        bot.edit_message_text(
            f"📁 <b>{name}</b>\n\nSelect subfolder:",
            uid,
            c.message.message_id,
            reply_markup=kb
        )
        bot.answer_callback_query(c.id)
        return
    
    # Send content
    text_content = folder.get("text_content")
    files = folder.get("files", [])
    
    if text_content:
        bot.send_message(uid, text_content)
        bot.answer_callback_query(c.id, "✅ Content sent!")
    
    if files:
        for f in files:
            try:
                bot.copy_message(uid, f["chat"], f["msg"])
                time.sleep(0.1)
            except:
                pass
        bot.answer_callback_query(c.id, f"✅ {len(files)} file(s) sent!")
    elif not text_content:
        bot.answer_callback_query(c.id, "📁 No content yet")

@bot.callback_query_handler(func=lambda c: c.data.startswith("back|"))
def back_handler(c):
    _, cat = c.data.split("|")
    bot.edit_message_text(
        f"📁 <b>{cat.upper()}</b>\n\nSelect:",
        c.from_user.id,
        c.message.message_id,
        reply_markup=InlineKeyboardMarkup()
    )
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join(c):
    uid = c.from_user.id
    if not force_block(uid):
        bot.edit_message_text("✅ <b>Access Granted!</b>", uid, c.message.message_id)
        bot.send_message(uid, "🎉 Welcome!", reply_markup=main_menu(uid))
    else:
        bot.answer_callback_query(c.id, "❌ Join channels first!", show_alert=True)

# =========================
# ADMIN PANEL
# =========================
@bot.message_handler(func=lambda m: m.text == "⚙️ ADMIN PANEL" and is_admin(m.from_user.id))
def open_admin(m):
    bot.send_message(m.from_user.id, "⚙️ <b>Admin Panel</b>", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "❌ Exit" and is_admin(m.from_user.id))
def exit_admin(m):
    bot.send_message(m.from_user.id, "✅ Exited admin panel", reply_markup=main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📊 Stats" and is_admin(m.from_user.id))
def stats_cmd(m):
    total_users = users_col.count_documents({})
    vip_users = users_col.count_documents({"vip": True})
    total_free = folders_col.count_documents({"cat": "free"})
    total_vip = folders_col.count_documents({"cat": "vip"})
    
    text = (
        f"📊 <b>STATISTICS</b>\n\n"
        f"👥 Users: <code>{total_users}</code> (VIP: {vip_users})\n"
        f"📁 Free: <code>{total_free}</code> | VIP: <code>{total_vip}</code>\n"
        f"💾 MongoDB: Connected ✅"
    )
    
    bot.send_message(m.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "💰 Give Points" and is_admin(m.from_user.id))
def give_points_start(m):
    msg = bot.send_message(m.from_user.id, "💰 <b>Give Points</b>\n\nSend: <code>user_id points</code>\nExample: <code>123456789 100</code>")
    bot.register_next_step_handler(msg, give_points_process)

def give_points_process(m):
    try:
        parts = m.text.strip().split()
        if len(parts) != 2:
            bot.send_message(m.from_user.id, "❌ Use: user_id points")
            return
        
        user_id = int(parts[0])
        points = int(parts[1])
        
        if points <= 0 or points > 1000000:
            bot.send_message(m.from_user.id, "❌ Points must be 1-1,000,000")
            return
        
        user = User(user_id)
        old = user.points()
        user.add_points(points)
        
        bot.send_message(m.from_user.id, 
            f"✅ <b>Points Added!</b>\n\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 Old: {old:,} → New: {user.points():,}\n"
            f"➕ Added: +{points:,}")
        
        try:
            bot.send_message(user_id, f"🎉 You received <b>+{points:,} points</b>!\n💰 Balance: {user.points():,}")
        except:
            pass
    except:
        bot.send_message(m.from_user.id, "❌ Error! Use: user_id points")

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m.from_user.id))
def broadcast_start(m):
    msg = bot.send_message(m.from_user.id, "📢 Send message to broadcast to all users:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(m):
    users = list(users_col.find({}))
    sent, failed = 0, 0
    
    for u in users:
        try:
            bot.send_message(int(u["_id"]), m.text)
            sent += 1
            if sent % 20 == 0:
                time.sleep(0.5)
        except:
            failed += 1
    
    bot.send_message(m.from_user.id, f"✅ Broadcast done!\n📤 Sent: {sent}\n❌ Failed: {failed}")

# =========================
# FALLBACK
# =========================
@bot.message_handler(func=lambda m: True)
def fallback(m):
    uid = m.from_user.id
    if force_block(uid):
        return
    
    known = ["📂 FREE METHODS", "💎 VIP METHODS", "📦 PREMIUM APPS", "⚡ SERVICES", 
             "💰 POINTS", "⭐ BUY VIP", "🎁 REFERRAL", "👤 ACCOUNT", "🆔 CHAT ID", 
             "🏆 REDEEM", "📚 MY METHODS", "💎 GET POINTS", "⚙️ ADMIN PANEL"]
    
    if m.text and m.text not in known:
        bot.send_message(uid, "❌ Use the menu buttons", reply_markup=main_menu(uid))

# =========================
# START BOT
# =========================
def start_bot():
    """Start bot polling"""
    print("\n" + "=" * 60)
    print("🚀 ZEDOX BOT - RUNNING")
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

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    # Start bot in background
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask for Railway
    port = int(os.getenv("PORT", 8080))
    print(f"\n🌐 Health check server on port {port}")
    app.run(host='0.0.0.0', port=port)
