# =========================
# ZEDOX BOT - PRODUCTION VERSION
# Railway + MongoDB Optimized
# =========================

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
from typing import Optional, Dict, Any, List

import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("BOT_TOKEN and ADMIN_ID must be set in environment variables")

# =========================
# MONGODB CONNECTION (Optimized)
# =========================
class Database:
    def __init__(self, uri: str):
        self.client = MongoClient(
            uri,
            maxPoolSize=50,
            minPoolSize=10,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            w='majority'
        )
        self.db = self.client["zedox_production"]
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Create indexes for better performance"""
        # Users indexes
        self.db.users.create_index([("points", DESCENDING)])
        self.db.users.create_index([("vip", ASCENDING)])
        self.db.users.create_index([("refs", DESCENDING)])
        self.db.users.create_index([("last_active", DESCENDING)])
        
        # Folders indexes
        self.db.folders.create_index([("cat", ASCENDING), ("parent", ASCENDING)])
        self.db.folders.create_index([("number", ASCENDING)], unique=True, sparse=True)
        self.db.folders.create_index([("name", ASCENDING)])
        
        # Codes indexes
        self.db.codes.create_index([("used", ASCENDING)])
        self.db.codes.create_index([("expiry", ASCENDING)])
        
        # Payments indexes
        self.db.payments.create_index([("user_id", ASCENDING)])
        self.db.payments.create_index([("status", ASCENDING)])
        self.db.payments.create_index([("created_at", DESCENDING)])
    
    @property
    def users(self):
        return self.db.users
    
    @property
    def folders(self):
        return self.db.folders
    
    @property
    def codes(self):
        return self.db.codes
    
    @property
    def config(self):
        return self.db.config
    
    @property
    def admins(self):
        return self.db.admins
    
    @property
    def payments(self):
        return self.db.payments

# Initialize database
db = Database(MONGO_URI)

# =========================
# BOT INITIALIZATION
# =========================
bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    num_workers=4,
    skip_pending=True
)

# =========================
# CACHE SYSTEM
# =========================
class Cache:
    def __init__(self, ttl: int = 30):
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                data, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    return data
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        with self._lock:
            self._cache[key] = (value, time.time())
    
    def clear(self):
        with self._lock:
            self._cache.clear()

# Initialize caches
config_cache = Cache(ttl=30)
user_cache = Cache(ttl=60)
folder_cache = Cache(ttl=120)

# =========================
# HELPER FUNCTIONS
# =========================
def get_config() -> Dict[str, Any]:
    """Get bot configuration with caching"""
    cached = config_cache.get("config")
    if cached:
        return cached
    
    config = db.config.find_one({"_id": "main"})
    if not config:
        config = {
            "_id": "main",
            "force_channels": [],
            "custom_buttons": [],
            "vip_message": "💎 Buy VIP to unlock premium features!",
            "welcome_message": "🔥 Welcome to ZEDOX BOT",
            "ref_reward": 5,
            "vip_price_usd": 50,
            "vip_price_points": 5000,
            "vip_duration_days": 30,
            "referral_vip_count": 50,
            "referral_purchase_count": 10,
            "points_per_dollar": 100,
            "binance_coin": "USDT",
            "binance_network": "TRC20",
            "binance_address": "",
            "binance_memo": "",
            "require_screenshot": True,
            "payment_methods": ["💳 Binance", "💵 USDT (TRC20)", "💰 Bank Transfer"],
            "notify_on_purchase": True,
            "next_folder_number": 1
        }
        db.config.insert_one(config)
    
    config_cache.set("config", config)
    return config

def update_config(key: str, value: Any):
    """Update configuration value"""
    db.config.update_one(
        {"_id": "main"},
        {"$set": {key: value}},
        upsert=True
    )
    config_cache.clear()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    if user_id == ADMIN_ID:
        return True
    admin = db.admins.find_one({"_id": user_id})
    return admin is not None

def force_join_required(func):
    """Decorator to check force join channels"""
    @wraps(func)
    def wrapper(message):
        user_id = message.from_user.id
        
        # Skip for admins
        if is_admin(user_id):
            return func(message)
        
        config = get_config()
        channels = config.get("force_channels", [])
        
        if not channels:
            return func(message)
        
        not_joined = []
        for channel in channels:
            try:
                # Remove @ if present
                chat_id = channel.replace("@", "")
                member = bot.get_chat_member(f"@{chat_id}", user_id)
                if member.status in ["left", "kicked"]:
                    not_joined.append(channel)
            except:
                not_joined.append(channel)
        
        if not_joined:
            kb = InlineKeyboardMarkup(row_width=1)
            for channel in not_joined:
                chat_id = channel.replace("@", "")
                kb.add(InlineKeyboardButton(
                    f"📢 Join {channel}",
                    url=f"https://t.me/{chat_id}"
                ))
            kb.add(InlineKeyboardButton("✅ I've Joined", callback_data="check_join"))
            
            bot.send_message(
                user_id,
                "🚫 <b>Access Restricted</b>\n\n"
                "Please join our channels to use the bot:",
                reply_markup=kb
            )
            return
        
        return func(message)
    return wrapper

# =========================
# USER SYSTEM
# =========================
class User:
    def __init__(self, user_id: int):
        self.user_id = str(user_id)
        self._load()
    
    def _load(self):
        """Load or create user data"""
        cached = user_cache.get(self.user_id)
        if cached:
            self.data = cached
            return
        
        user_data = db.users.find_one({"_id": self.user_id})
        if not user_data:
            user_data = {
                "_id": self.user_id,
                "username": None,
                "first_name": None,
                "points": 0,
                "total_earned": 0,
                "total_spent": 0,
                "vip": False,
                "vip_expiry": None,
                "ref_by": None,
                "refs": 0,
                "refs_bought_vip": 0,
                "purchased_methods": [],
                "used_codes": [],
                "created_at": time.time(),
                "last_active": time.time()
            }
            db.users.insert_one(user_data)
        
        self.data = user_data
        user_cache.set(self.user_id, user_data)
    
    def save(self):
        """Save user data to database"""
        self.data["last_active"] = time.time()
        db.users.update_one(
            {"_id": self.user_id},
            {"$set": self.data}
        )
        user_cache.set(self.user_id, self.data)
    
    def update_profile(self, username: str = None, first_name: str = None):
        """Update user profile"""
        if username:
            self.data["username"] = username
        if first_name:
            self.data["first_name"] = first_name
        self.save()
    
    @property
    def points(self) -> int:
        return self.data.get("points", 0)
    
    def add_points(self, amount: int, reason: str = ""):
        """Add points to user"""
        self.data["points"] += amount
        self.data["total_earned"] = self.data.get("total_earned", 0) + amount
        self.save()
    
    def spend_points(self, amount: int) -> bool:
        """Spend points, returns False if insufficient"""
        if self.points < amount:
            return False
        self.data["points"] -= amount
        self.data["total_spent"] = self.data.get("total_spent", 0) + amount
        self.save()
        return True
    
    def is_vip(self) -> bool:
        """Check if user is VIP (with expiry check)"""
        if self.data.get("vip", False):
            expiry = self.data.get("vip_expiry")
            if expiry and expiry < time.time():
                self.data["vip"] = False
                self.data["vip_expiry"] = None
                self.save()
                return False
            return True
        return False
    
    def make_vip(self, duration_days: int = 30):
        """Make user VIP"""
        self.data["vip"] = True
        if duration_days > 0:
            self.data["vip_expiry"] = time.time() + (duration_days * 86400)
        else:
            self.data["vip_expiry"] = None  # Permanent
        self.save()
    
    def remove_vip(self):
        """Remove VIP status"""
        self.data["vip"] = False
        self.data["vip_expiry"] = None
        self.save()
    
    def add_referral(self):
        """Add a referral"""
        self.data["refs"] = self.data.get("refs", 0) + 1
        self.save()
        
        config = get_config()
        required = config.get("referral_vip_count", 50)
        
        if self.data["refs"] >= required and not self.is_vip():
            self.make_vip(config.get("vip_duration_days", 30))
            return True
        return False
    
    def can_access_method(self, method_name: str) -> bool:
        """Check if user can access a method"""
        if self.is_vip():
            return True
        return method_name in self.data.get("purchased_methods", [])

# =========================
# FOLDER SYSTEM
# =========================
class FolderSystem:
    @staticmethod
    def get_folders(category: str, parent: str = None, page: int = 0, per_page: int = 15) -> tuple:
        """Get folders with pagination"""
        query = {"cat": category, "parent": parent}
        total = db.folders.count_documents(query)
        folders = list(
            db.folders.find(query)
            .sort("number", 1)
            .skip(page * per_page)
            .limit(per_page)
        )
        return folders, total, page, per_page
    
    @staticmethod
    def get_folder(category: str, name: str, parent: str = None) -> Optional[Dict]:
        """Get a specific folder"""
        query = {"cat": category, "name": name}
        if parent:
            query["parent"] = parent
        return db.folders.find_one(query)
    
    @staticmethod
    def get_folder_by_number(number: int) -> Optional[Dict]:
        """Get folder by number"""
        return db.folders.find_one({"number": number})
    
    @staticmethod
    def has_subfolders(category: str, name: str) -> bool:
        """Check if folder has subfolders"""
        return db.folders.count_documents({"cat": category, "parent": name}) > 0
    
    @staticmethod
    def add_folder(category: str, name: str, files: List[Dict], price: int = 0, 
                   parent: str = None, text_content: str = None) -> int:
        """Add a new folder"""
        config = get_config()
        number = config.get("next_folder_number", 1)
        
        folder_data = {
            "cat": category,
            "name": name,
            "files": files,
            "price": price,
            "parent": parent,
            "number": number,
            "created_at": time.time()
        }
        
        if text_content:
            folder_data["text_content"] = text_content
        
        db.folders.insert_one(folder_data)
        update_config("next_folder_number", number + 1)
        
        return number
    
    @staticmethod
    def delete_folder(category: str, name: str, parent: str = None):
        """Delete a folder and its subfolders"""
        # Delete subfolders recursively
        subfolders = list(db.folders.find({"cat": category, "parent": name}))
        for sub in subfolders:
            FolderSystem.delete_folder(category, sub["name"], name)
        
        # Delete the folder itself
        db.folders.delete_one({"cat": category, "name": name, "parent": parent})
    
    @staticmethod
    def edit_price(category: str, name: str, price: int, parent: str = None):
        """Edit folder price"""
        query = {"cat": category, "name": name}
        if parent:
            query["parent"] = parent
        db.folders.update_one(query, {"$set": {"price": price}})

# =========================
# KEYBOARD BUILDERS
# =========================
def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Create main menu keyboard"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        "📂 FREE METHODS", "💎 VIP METHODS",
        "📦 PREMIUM APPS", "⚡ SERVICES",
        "💰 POINTS", "⭐ BUY VIP",
        "🎁 REFERRAL", "👤 ACCOUNT",
        "📚 MY METHODS", "💎 GET POINTS",
        "🆔 CHAT ID", "🏆 REDEEM"
    ]
    
    # Add custom buttons
    config = get_config()
    custom_buttons = config.get("custom_buttons", [])
    for btn in custom_buttons:
        buttons.append(btn["text"])
    
    if is_admin(user_id):
        buttons.append("⚙️ ADMIN PANEL")
    
    # Create rows of 2
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        kb.add(*row)
    
    return kb

def folders_keyboard(category: str, parent: str = None, page: int = 0) -> InlineKeyboardMarkup:
    """Create folders inline keyboard with pagination"""
    folders, total, current_page, per_page = FolderSystem.get_folders(category, parent, page)
    
    kb = InlineKeyboardMarkup(row_width=2)
    
    for folder in folders:
        name = folder["name"]
        number = folder.get("number", "?")
        price = folder.get("price", 0)
        has_subs = FolderSystem.has_subfolders(category, name)
        
        icon = "📁" if has_subs else "📄"
        text = f"{icon} [{number}] {name}"
        if price > 0:
            text += f" [{price} pts]"
        
        callback = f"open|{category}|{name}|{parent or 'root'}"
        kb.add(InlineKeyboardButton(text, callback_data=callback))
    
    # Navigation buttons
    if total > per_page:
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"page|{category}|{current_page-1}|{parent or 'root'}"
            ))
        if (current_page + 1) * per_page < total:
            nav_buttons.append(InlineKeyboardButton(
                "➡️ Next",
                callback_data=f"page|{category}|{current_page+1}|{parent or 'root'}"
            ))
        if nav_buttons:
            kb.row(*nav_buttons)
    
    # Back button for subfolders
    if parent:
        kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"back|{category}|{parent}"))
    
    return kb

# =========================
# BOT HANDLERS
# =========================

@bot.message_handler(commands=["start"])
def start_command(message):
    """Handle /start command"""
    user_id = message.from_user.id
    user = User(user_id)
    
    # Update user profile
    username = message.from_user.username
    first_name = message.from_user.first_name
    if username or first_name:
        user.update_profile(username, first_name)
    
    # Handle referral
    args = message.text.split()
    if len(args) > 1:
        ref_id = args[1]
        if ref_id.isdigit() and int(ref_id) != user_id:
            handle_referral(user_id, int(ref_id), user)
    
    # Send welcome
    config = get_config()
    welcome = config.get("welcome_message", "🔥 Welcome to ZEDOX BOT!")
    
    bot.send_message(
        user_id,
        f"{welcome}\n\n"
        f"💰 Your Points: <b>{user.points}</b>",
        reply_markup=main_menu_keyboard(user_id)
    )

def handle_referral(new_user_id: int, ref_id: int, new_user: User):
    """Handle referral logic"""
    try:
        # Check if user already has a referrer
        if new_user.data.get("ref_by"):
            return
        
        ref_user = User(ref_id)
        config = get_config()
        reward = config.get("ref_reward", 5)
        
        # Give reward to referrer
        ref_user.add_points(reward)
        got_vip = ref_user.add_referral()
        
        # Update new user
        new_user.data["ref_by"] = str(ref_id)
        new_user.save()
        
        # Notify referrer
        notify_msg = (
            f"🎉 <b>New Referral!</b>\n\n"
            f"👤 User joined using your link!\n"
            f"💰 You earned <b>+{reward} points</b>\n"
            f"📊 Total Referrals: <b>{ref_user.data['refs']}</b>"
        )
        
        if got_vip:
            notify_msg += (
                f"\n\n🌟 <b>CONGRATULATIONS!</b>\n"
                f"You've earned <b>FREE VIP</b> for reaching "
                f"{config.get('referral_vip_count', 50)} referrals!"
            )
        
        bot.send_message(ref_id, notify_msg)
    except Exception as e:
        print(f"Referral error: {e}")

@bot.message_handler(func=lambda m: m.text == "📂 FREE METHODS")
@force_join_required
def show_free_methods(message):
    """Show free methods"""
    folders, total, _, _ = FolderSystem.get_folders("free")
    if not folders:
        bot.send_message(
            message.from_user.id,
            "📂 <b>FREE METHODS</b>\n\nNo methods available yet!",
            reply_markup=main_menu_keyboard(message.from_user.id)
        )
        return
    
    bot.send_message(
        message.from_user.id,
        "📂 <b>FREE METHODS</b>\n\nSelect a method:",
        reply_markup=folders_keyboard("free")
    )

@bot.message_handler(func=lambda m: m.text == "💎 VIP METHODS")
@force_join_required
def show_vip_methods(message):
    """Show VIP methods"""
    user = User(message.from_user.id)
    
    if not user.is_vip():
        config = get_config()
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⭐ Get VIP Access", callback_data="buy_vip"))
        bot.send_message(
            message.from_user.id,
            "💎 <b>VIP METHODS</b>\n\n"
            "🔒 This section is for VIP members only!\n\n"
            f"💰 VIP Price: ${config.get('vip_price_usd', 50)} or {config.get('vip_price_points', 5000)} points",
            reply_markup=kb
        )
        return
    
    folders, total, _, _ = FolderSystem.get_folders("vip")
    if not folders:
        bot.send_message(
            message.from_user.id,
            "💎 <b>VIP METHODS</b>\n\nNo methods available yet!",
            reply_markup=main_menu_keyboard(message.from_user.id)
        )
        return
    
    bot.send_message(
        message.from_user.id,
        "💎 <b>VIP METHODS</b>\n\nSelect a method:",
        reply_markup=folders_keyboard("vip")
    )

@bot.message_handler(func=lambda m: m.text == "💰 POINTS")
@force_join_required
def show_points(message):
    """Show points balance"""
    user = User(message.from_user.id)
    
    config = get_config()
    ref_count = user.data.get("refs", 0)
    ref_vip_count = user.data.get("refs_bought_vip", 0)
    
    text = (
        f"💰 <b>YOUR POINTS</b>\n\n"
        f"┌ Balance: <code>{user.points:,}</code> pts\n"
        f"├ VIP: {'✅ Active' if user.is_vip() else '❌ Not Active'}\n"
        f"├ Total Earned: <code>{user.data.get('total_earned', 0):,}</code>\n"
        f"├ Total Spent: <code>{user.data.get('total_spent', 0):,}</code>\n"
        f"├ Referrals: {ref_count}/{config.get('referral_vip_count', 50)}\n"
        f"└ VIP Referrals: {ref_vip_count}/{config.get('referral_purchase_count', 10)}\n\n"
        f"✨ <b>Ways to Earn:</b>\n"
        f"• 🎁 Refer friends: +{config.get('ref_reward', 5)} pts each\n"
        f"• 🏆 Redeem codes\n"
        f"• 💎 Purchase points\n\n"
        f"💡 <b>Use points to:</b>\n"
        f"• Buy individual VIP methods\n"
        f"• Access premium content"
    )
    
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "🎁 REFERRAL")
@force_join_required
def show_referral(message):
    """Show referral link"""
    user = User(message.from_user.id)
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={user.user_id}"
    
    config = get_config()
    ref_count = user.data.get("refs", 0)
    
    text = (
        f"🎁 <b>REFERRAL SYSTEM</b>\n\n"
        f"🔗 Your Link:\n<code>{link}</code>\n\n"
        f"📊 <b>Your Stats:</b>\n"
        f"┌ Referrals: {ref_count}\n"
        f"├ Reward: +{config.get('ref_reward', 5)} pts each\n"
        f"└ Points Earned: {ref_count * config.get('ref_reward', 5)}\n\n"
        f"🎯 <b>Rewards:</b>\n"
        f"• {config.get('referral_vip_count', 50)} referrals → FREE VIP\n"
        f"• {config.get('referral_purchase_count', 10)} VIP purchases → FREE VIP"
    )
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}"))
    
    bot.send_message(message.from_user.id, text, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "👤 ACCOUNT")
@force_join_required
def show_account(message):
    """Show account info"""
    user = User(message.from_user.id)
    
    status = "💎 VIP" if user.is_vip() else "🆓 Free"
    if user.is_vip() and user.data.get("vip_expiry"):
        expiry = datetime.fromtimestamp(user.data["vip_expiry"])
        status += f" (Expires: {expiry.strftime('%Y-%m-%d')})"
    elif user.is_vip():
        status += " (Permanent)"
    
    text = (
        f"👤 <b>ACCOUNT</b>\n\n"
        f"┌ Status: {status}\n"
        f"├ ID: <code>{user.user_id}</code>\n"
        f"├ Points: <code>{user.points:,}</code>\n"
        f"├ Referrals: {user.data.get('refs', 0)}\n"
        f"├ Purchased: {len(user.data.get('purchased_methods', []))} methods\n"
        f"└ Joined: {datetime.fromtimestamp(user.data.get('created_at', time.time())).strftime('%Y-%m-%d')}"
    )
    
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "🏆 REDEEM")
@force_join_required
def redeem_code_prompt(message):
    """Prompt for redeem code"""
    msg = bot.send_message(
        message.from_user.id,
        "🎫 <b>REDEEM CODE</b>\n\nSend your code:"
    )
    bot.register_next_step_handler(msg, process_redeem_code)

def process_redeem_code(message):
    """Process redeem code"""
    user_id = message.from_user.id
    user = User(user_id)
    code = message.text.strip().upper()
    
    # Check code in database
    code_data = db.codes.find_one({"_id": code})
    
    if not code_data:
        bot.send_message(user_id, "❌ Invalid code!")
        return
    
    # Check expiry
    if code_data.get("expiry") and time.time() > code_data["expiry"]:
        bot.send_message(user_id, "❌ Code expired!")
        return
    
    # Check if already used
    if code_data.get("used", False) and not code_data.get("multi_use", False):
        bot.send_message(user_id, "❌ Code already used!")
        return
    
    # Check if user already used
    used_by = code_data.get("used_by", [])
    if user.user_id in used_by and not code_data.get("multi_use", False):
        bot.send_message(user_id, "❌ You've already used this code!")
        return
    
    # Handle multi-use
    if code_data.get("multi_use", False):
        max_uses = code_data.get("max_uses", 10)
        if len(used_by) >= max_uses:
            bot.send_message(user_id, "❌ Max uses reached!")
            return
    
    # Redeem points
    points = code_data["points"]
    user.add_points(points)
    
    # Update code
    update_data = {
        "$push": {"used_by": user.user_id},
        "$inc": {"used_count": 1}
    }
    if not code_data.get("multi_use", False):
        update_data["$set"] = {"used": True}
    
    db.codes.update_one({"_id": code}, update_data)
    
    bot.send_message(
        user_id,
        f"✅ <b>Code Redeemed!</b>\n\n"
        f"+{points} points added\n"
        f"💰 New Balance: <code>{user.points:,}</code>"
    )

@bot.message_handler(func=lambda m: m.text == "⭐ BUY VIP")
@force_join_required
def buy_vip(message):
    """Show VIP purchase options"""
    user = User(message.from_user.id)
    
    if user.is_vip():
        bot.send_message(
            message.from_user.id,
            "✅ You're already a VIP member!",
            reply_markup=main_menu_keyboard(message.from_user.id)
        )
        return
    
    config = get_config()
    price_usd = config.get("vip_price_usd", 50)
    price_points = config.get("vip_points_price", 5000)
    
    text = (
        f"⭐ <b>VIP MEMBERSHIP</b>\n\n"
        f"💰 <b>Price:</b>\n"
        f"• ${price_usd} USD\n"
        f"• {price_points:,} points\n\n"
        f"✨ <b>Benefits:</b>\n"
        f"• Access ALL VIP methods\n"
        f"• No points required\n"
        f"• Priority support\n"
        f"• Exclusive content\n\n"
        f"🎁 <b>Free VIP:</b>\n"
        f"• Invite {config.get('referral_vip_count', 50)} users\n"
        f"• Get {config.get('referral_purchase_count', 10)} referrals to buy VIP\n\n"
        f"🆔 Your ID: <code>{user.user_id}</code>\n"
        f"💰 Your Points: <code>{user.points:,}</code>"
    )
    
    kb = InlineKeyboardMarkup()
    if user.points >= price_points:
        kb.add(InlineKeyboardButton(
            f"⭐ Buy with {price_points:,} Points",
            callback_data="buy_vip_points"
        ))
    kb.add(InlineKeyboardButton("📞 Contact for Payment", callback_data="vip_contact"))
    
    bot.send_message(message.from_user.id, text, reply_markup=kb)

# =========================
# CALLBACK HANDLERS
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join_callback(call):
    """Check if user joined required channels"""
    user_id = call.from_user.id
    config = get_config()
    channels = config.get("force_channels", [])
    
    not_joined = []
    for channel in channels:
        try:
            chat_id = channel.replace("@", "")
            member = bot.get_chat_member(f"@{chat_id}", user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    
    if not_joined:
        bot.answer_callback_query(call.id, "❌ Please join all channels first!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id, "✅ Access granted!")
    bot.edit_message_text(
        "✅ <b>Access Granted!</b>\n\nWelcome to ZEDOX BOT!",
        user_id,
        call.message.message_id
    )
    user = User(user_id)
    bot.send_message(
        user_id,
        "🔥 Welcome! Use the menu below to navigate.",
        reply_markup=main_menu_keyboard(user_id)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("open|"))
def open_folder_callback(call):
    """Handle folder opening"""
    user_id = call.from_user.id
    user = User(user_id)
    
    _, category, name, parent = call.data.split("|")
    parent = None if parent == "root" else parent
    
    folder = FolderSystem.get_folder(category, name, parent)
    if not folder:
        bot.answer_callback_query(call.id, "❌ Folder not found!")
        return
    
    # Check for subfolders
    if FolderSystem.has_subfolders(category, name):
        bot.edit_message_text(
            f"📁 <b>{name}</b>\n\nSelect subfolder:",
            user_id,
            call.message.message_id,
            reply_markup=folders_keyboard(category, name)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Check access for VIP content
    if category == "vip" and not user.is_vip():
        price = folder.get("price", 0)
        if price > 0 and not user.can_access_method(name):
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton(f"💰 Buy for {price} pts", callback_data=f"buy_method|{category}|{name}|{price}"),
                InlineKeyboardButton("⭐ Get VIP", callback_data="buy_vip")
            )
            bot.answer_callback_query(call.id, f"🔒 Price: {price} pts")
            bot.send_message(
                user_id,
                f"🔒 <b>{name}</b>\n\n"
                f"💰 Price: {price} points\n"
                f"💳 Your Balance: {user.points} points",
                reply_markup=kb
            )
            return
    
    # Charge points for non-VIP, non-free content
    price = folder.get("price", 0)
    if category != "vip" and price > 0 and not user.is_vip():
        if not user.spend_points(price):
            bot.answer_callback_query(
                call.id,
                f"❌ Insufficient points! Need {price}, have {user.points}",
                show_alert=True
            )
            return
    
    # Send content
    text_content = folder.get("text_content")
    files = folder.get("files", [])
    
    if text_content:
        bot.answer_callback_query(call.id, "✅ Opening...")
        bot.send_message(user_id, text_content)
    
    if files:
        bot.answer_callback_query(call.id, "📤 Sending files...")
        for file_data in files:
            try:
                bot.copy_message(user_id, file_data["chat"], file_data["msg"])
                time.sleep(0.1)
            except Exception as e:
                print(f"Error sending file: {e}")
        
        bot.send_message(user_id, f"✅ {len(files)} file(s) sent!")
    
    # Mark as purchased for VIP methods
    if category == "vip" and not user.is_vip():
        if name not in user.data.get("purchased_methods", []):
            user.data.setdefault("purchased_methods", []).append(name)
            user.save()

@bot.callback_query_handler(func=lambda c: c.data.startswith("page|"))
def page_callback(call):
    """Handle pagination"""
    _, category, page, parent = call.data.split("|")
    parent = None if parent == "root" else parent
    page = int(page)
    
    bot.edit_message_reply_markup(
        call.from_user.id,
        call.message.message_id,
        reply_markup=folders_keyboard(category, parent, page)
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("back|"))
def back_callback(call):
    """Handle back navigation"""
    _, category, current_parent = call.data.split("|")
    
    # Find parent of current folder
    folder = FolderSystem.get_folder(category, current_parent)
    if folder:
        grandparent = folder.get("parent")
        bot.edit_message_text(
            f"📁 <b>{grandparent or category.upper()}</b>\n\nSelect folder:",
            call.from_user.id,
            call.message.message_id,
            reply_markup=folders_keyboard(category, grandparent)
        )
    else:
        bot.edit_message_text(
            f"📁 <b>{category.upper()}</b>\n\nSelect folder:",
            call.from_user.id,
            call.message.message_id,
            reply_markup=folders_keyboard(category)
        )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "buy_vip")
def buy_vip_callback(call):
    """Buy VIP callback"""
    # Redirect to buy VIP handler
    buy_vip(call.message)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "buy_vip_points")
def buy_vip_points_callback(call):
    """Buy VIP with points"""
    user = User(call.from_user.id)
    config = get_config()
    price = config.get("vip_price_points", 5000)
    
    if user.points < price:
        bot.answer_callback_query(call.id, f"❌ Need {price:,} points!", show_alert=True)
        return
    
    user.spend_points(price)
    user.make_vip(config.get("vip_duration_days", 30))
    
    bot.answer_callback_query(call.id, "✅ VIP Purchased!", show_alert=True)
    bot.edit_message_text(
        call.from_user.id,
        call.message.message_id,
        "🎉 <b>CONGRATULATIONS!</b>\n\nYou are now a VIP member!\n\nEnjoy all premium features! 🌟"
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_method|"))
def buy_method_callback(call):
    """Buy individual method"""
    user_id = call.from_user.id
    user = User(user_id)
    
    _, category, name, price = call.data.split("|")
    price = int(price)
    
    if user.points < price:
        bot.answer_callback_query(call.id, f"❌ Need {price} pts!", show_alert=True)
        return
    
    user.spend_points(price)
    if name not in user.data.get("purchased_methods", []):
        user.data.setdefault("purchased_methods", []).append(name)
        user.save()
    
    bot.answer_callback_query(call.id, f"✅ Purchased! -{price} pts", show_alert=True)
    
    # Open the folder now
    call.data = f"open|{category}|{name}|root"
    open_folder_callback(call)

# =========================
# ADMIN PANEL
# =========================

@bot.message_handler(func=lambda m: m.text == "⚙️ ADMIN PANEL" and is_admin(m.from_user.id))
def admin_panel(message):
    """Show admin panel"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        "📤 Upload FREE", "💎 Upload VIP",
        "📱 Upload APPS", "⚡ Upload SERVICE",
        "📁 Create Subfolder", "🗑 Delete Folder",
        "✏️ Edit Price", "✏️ Edit Name",
        "📝 Edit Content", "🔀 Move Folder",
        "👑 Add VIP", "👑 Remove VIP",
        "💰 Give Points", "🎫 Generate Codes",
        "📊 View Codes", "📦 Points Packages",
        "👥 Admins", "📞 Set Contacts",
        "⚙️ Settings", "📊 Statistics",
        "📢 Broadcast", "➕ Add Channel",
        "➖ Remove Channel", "🏆 Leaderboard",
        "❌ Exit Admin"
    ]
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        kb.add(*row)
    
    bot.send_message(
        message.from_user.id,
        "⚙️ <b>ADMIN PANEL</b>\n\nSelect an option:",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text == "❌ Exit Admin" and is_admin(m.from_user.id))
def exit_admin(message):
    """Exit admin panel"""
    bot.send_message(
        message.from_user.id,
        "✅ Exited admin panel",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )

@bot.message_handler(func=lambda m: m.text == "💰 Give Points" and is_admin(m.from_user.id))
def give_points_prompt(message):
    """Give points to user"""
    msg = bot.send_message(
        message.from_user.id,
        "💰 <b>GIVE POINTS</b>\n\n"
        "Send: <code>user_id amount</code>\n"
        "Example: <code>123456789 1000</code>"
    )
    bot.register_next_step_handler(msg, process_give_points)

def process_give_points(message):
    """Process give points"""
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(message.from_user.id, "❌ Format: user_id amount")
            return
        
        user_id, amount = parts
        if not user_id.isdigit() or not amount.lstrip('-').isdigit():
            bot.send_message(message.from_user.id, "❌ Invalid user_id or amount!")
            return
        
        user_id = int(user_id)
        amount = int(amount)
        
        if amount <= 0:
            bot.send_message(message.from_user.id, "❌ Amount must be positive!")
            return
        
        user = User(user_id)
        old_balance = user.points
        user.add_points(amount)
        
        bot.send_message(
            message.from_user.id,
            f"✅ <b>Points Added!</b>\n\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 Old Balance: {old_balance:,}\n"
            f"➕ Added: +{amount:,}\n"
            f"💰 New Balance: {user.points:,}"
        )
        
        # Notify user
        try:
            bot.send_message(
                user_id,
                f"🎉 <b>Points Received!</b>\n\n"
                f"+{amount:,} points added to your account!\n"
                f"💰 New Balance: {user.points:,}"
            )
        except:
            pass
            
    except Exception as e:
        bot.send_message(message.from_user.id, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == "📊 Statistics" and is_admin(m.from_user.id))
def show_statistics(message):
    """Show bot statistics"""
    total_users = db.users.count_documents({})
    vip_users = db.users.count_documents({"vip": True})
    free_users = total_users - vip_users
    
    total_folders = db.folders.count_documents({})
    free_folders = db.folders.count_documents({"cat": "free"})
    vip_folders = db.folders.count_documents({"cat": "vip"})
    
    total_codes = db.codes.count_documents({})
    used_codes = db.codes.count_documents({"used": True})
    
    # Aggregate stats
    pipeline = [
        {"$group": {
            "_id": None,
            "total_points": {"$sum": "$points"},
            "total_earned": {"$sum": "$total_earned"},
            "total_spent": {"$sum": "$total_spent"},
            "total_refs": {"$sum": "$refs"}
        }}
    ]
    stats = list(db.users.aggregate(pipeline))
    stats = stats[0] if stats else {}
    
    text = (
        f"📊 <b>BOT STATISTICS</b>\n\n"
        f"👥 <b>Users:</b>\n"
        f"├ Total: {total_users:,}\n"
        f"├ VIP: {vip_users:,}\n"
        f"└ Free: {free_users:,}\n\n"
        f"📁 <b>Content:</b>\n"
        f"├ Total Folders: {total_folders:,}\n"
        f"├ Free Methods: {free_folders:,}\n"
        f"└ VIP Methods: {vip_folders:,}\n\n"
        f"💰 <b>Points:</b>\n"
        f"├ Total Points: {stats.get('total_points', 0):,}\n"
        f"├ Total Earned: {stats.get('total_earned', 0):,}\n"
        f"├ Total Spent: {stats.get('total_spent', 0):,}\n"
        f"└ Total Referrals: {stats.get('total_refs', 0):,}\n\n"
        f"🎫 <b>Codes:</b>\n"
        f"├ Total: {total_codes:,}\n"
        f"├ Used: {used_codes:,}\n"
        f"└ Active: {total_codes - used_codes:,}"
    )
    
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m.from_user.id))
def broadcast_prompt(message):
    """Send broadcast message"""
    msg = bot.send_message(
        message.from_user.id,
        "📢 <b>BROADCAST</b>\n\n"
        "Send the message you want to broadcast to all users.\n"
        "You can send text, photos, videos, or documents."
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    """Process broadcast"""
    status_msg = bot.send_message(message.from_user.id, "📤 Broadcasting...")
    
    users = list(db.users.find({}))
    total = len(users)
    sent = 0
    failed = 0
    
    for user in users:
        try:
            user_id = int(user["_id"])
            
            if message.content_type == "text":
                bot.send_message(user_id, message.text, parse_mode="HTML")
            elif message.content_type == "photo":
                bot.send_photo(
                    user_id,
                    message.photo[-1].file_id,
                    caption=message.caption,
                    parse_mode="HTML"
                )
            elif message.content_type == "video":
                bot.send_video(
                    user_id,
                    message.video.file_id,
                    caption=message.caption,
                    parse_mode="HTML"
                )
            elif message.content_type == "document":
                bot.send_document(
                    user_id,
                    message.document.file_id,
                    caption=message.caption,
                    parse_mode="HTML"
                )
            
            sent += 1
            if sent % 20 == 0:
                time.sleep(0.5)  # Rate limiting
                
        except Exception as e:
            failed += 1
            print(f"Broadcast error for {user['_id']}: {e}")
    
    bot.edit_message_text(
        f"✅ Broadcast complete!\n\n"
        f"📤 Sent: {sent}/{total}\n"
        f"❌ Failed: {failed}/{total}",
        message.from_user.id,
        status_msg.message_id
    )

# =========================
# ERROR HANDLER
# =========================

@bot.message_handler(func=lambda m: True)
def fallback_handler(message):
    """Handle unknown messages"""
    if message.text and message.text.startswith("/"):
        return  # Ignore other commands
    
    user = User(message.from_user.id)
    bot.send_message(
        message.from_user.id,
        "❌ Unknown command. Please use the menu buttons.",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )

# =========================
# MAIN FUNCTION
# =========================

def main():
    """Main function to run the bot"""
    print("=" * 50)
    print("🚀 ZEDOX BOT - PRODUCTION VERSION")
    print(f"✅ Bot: @{bot.get_me().username}")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"💾 MongoDB: Connected")
    print("=" * 50)
    
    # Remove webhook if exists
    bot.remove_webhook()
    
    # Start polling
    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )
        except Exception as e:
            print(f"❌ Bot error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
