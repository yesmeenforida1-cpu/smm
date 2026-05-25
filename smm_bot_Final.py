import logging
import requests
import json
import os
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler, JobQueue

logging.basicConfig(level=logging.WARNING)

# ===== CONFIG =====
BOT_TOKEN = "8652759001:AAG5OOqv2v5du8VocXi-MFw3KEROGz4840I"
ADMIN_ID = 7974704580
BOT_NAME = "FREE SERVICE SMM FATHER"
OWNER = "@SW_WAFK"
SUPPORT = "@SOPPORT_CLAW_BOT"
API_KEY = "ad47f2ee564a704d046e4be672c05c1c"   # ✅ নতুন API KEY (peakerr.com)
API_URL = "https://peakerr.com/api/v2"
CHANNEL_1 = "@SMM_SERVICES_BANGLADESH"
CHANNEL_2 = "@jjSERVICE_SMM_FATHER"
LOG_CH = "@jjSERVICE_SMM_FATHER"
PROFIT_PCT = 35   # ✅ সব সার্ভিসের দাম ৩৫% বেশি

# ===== DATA FILE (persistent storage) =====
DATA_FILE = "bot_data.json"

# ===== STATES =====
(S_PLATFORM, S_SERVICE, S_QTY, S_LINK,
 D_AMOUNT, D_METHOD, D_TRXID, D_SCREENSHOT,
 BROADCAST, BLOCK_ID, BLOCK_DAYS,
 CH_BKASH, CH_NAGAD, CH_BINANCE,
 SET_LIST, AO_UID, AO_SVC, AO_QTY, AO_LINK,
 REF_UID, REF_AMT, CHK_UID, CUSTOM_SVC,
 DISC_CODE_PCT, DISC_CODE_NAME, DISC_CODE_DAYS,   # admin discount code creation
 DISC_USE) = range(27)   # user applying discount code

# ===== PAYMENT =====
PAYMENT = {
    "bkash":   {"number": "01759852112", "active": True},
    "nagad":   {"number": "01625141477", "active": True},
    "binance": {"id": "1234939031",      "active": False},
}

# ===== IN-MEMORY DATA =====
users = {}
orders = {}
blocked = {}
bot_on = True
today_stats = {}
total_stats = {"orders": 0, "revenue": 0.0, "cost": 0.0, "profit": 0.0}
SMM_CACHE = {}
discount_codes = {}   # {"CODE123": {"pct": 10, "days": 7, "expires": datetime, "used_by": []}}
user_discounts = {}   # {uid: {"pct": 10, "expires": datetime}}

SERVICES = {
    "telegram": {"name": "✈️ টেলিগ্রাম", "active": True, "list": {
        "tg1": {"name": "টেলিগ্রাম ১K মেম্বার (Drop হতে পারে)", "price": 40,  "min": 500,  "active": True, "search": "telegram member",    "avoid": ["premium","view","react","vote","lifetime","group"]},
        "tg2": {"name": "টেলিগ্রাম ১K Lifetime মেম্বার",        "price": 180, "min": 500,  "active": True, "search": "telegram lifetime",  "avoid": ["view","react","vote","group","premium"]},
        "tg3": {"name": "টেলিগ্রাম Post View ১K",               "price": 3,   "min": 100,  "active": True, "search": "telegram view post", "avoid": ["member","react","vote"]},
        "tg4": {"name": "টেলিগ্রাম Post React ১K",              "price": 12,  "min": 100,  "active": True, "search": "telegram reaction",  "avoid": ["member","view","vote"]},
        "tg5": {"name": "টেলিগ্রাম ১০০ Vote",                   "price": 15,  "min": 100,  "active": True, "search": "telegram vote poll", "avoid": ["member","view","react"]},
    }},
    "tiktok": {"name": "🎵 টিকটক", "active": True, "list": {
        "tt1": {"name": "টিকটক ১K Like",     "price": 35,  "min": 100,  "active": True, "search": "tiktok like",    "avoid": ["view","follow","share","comment"]},
        "tt2": {"name": "টিকটক ১০K View",    "price": 20,  "min": 1000, "active": True, "search": "tiktok view",    "avoid": ["like","follow","share","comment"]},
        "tt3": {"name": "টিকটক ১K Follower", "price": 150, "min": 100,  "active": True, "search": "tiktok follow",  "avoid": ["like","view","share","comment"]},
        "tt4": {"name": "টিকটক ১K Share",    "price": 80,  "min": 100,  "active": True, "search": "tiktok share",   "avoid": ["like","view","follow","comment"]},
        "tt5": {"name": "টিকটক ১০০ Comment", "price": 100, "min": 100,  "active": True, "search": "tiktok comment", "avoid": ["like","view","follow","share"]},
    }},
    "youtube": {"name": "🎬 ইউটিউব", "active": True, "list": {
        "yt1": {"name": "ইউটিউব ১K Subscriber", "price": 170, "min": 100, "active": True, "search": "youtube subscriber", "avoid": ["view","like","comment"]},
        "yt2": {"name": "ইউটিউব ১K Like",       "price": 50,  "min": 100, "active": True, "search": "youtube like",       "avoid": ["sub","view","comment"]},
        "yt3": {"name": "ইউটিউব ১K View",       "price": 120, "min": 100, "active": True, "search": "youtube view",       "avoid": ["sub","like","comment"]},
        "yt4": {"name": "ইউটিউব ১০০ Comment",   "price": 40,  "min": 100, "active": True, "search": "youtube comment",    "avoid": ["sub","like","view"]},
    }},
    "instagram": {"name": "📸 ইন্সটাগ্রাম", "active": True, "list": {
        "ig1": {"name": "ইন্সটাগ্রাম ১K Follower", "price": 180, "min": 100,   "active": True, "search": "instagram follower",  "avoid": ["view","like","comment"]},
        "ig2": {"name": "ইন্সটাগ্রাম ১০K View",    "price": 12,  "min": 1000,  "active": True, "search": "instagram view reel", "avoid": ["follow","like","comment"]},
        "ig3": {"name": "ইন্সটাগ্রাম ১০০K View",   "price": 90,  "min": 10000, "active": True, "search": "instagram view",      "avoid": ["follow","like","comment"]},
        "ig4": {"name": "ইন্সটাগ্রাম ১K Like",     "price": 40,  "min": 100,   "active": True, "search": "instagram like",      "avoid": ["follow","view","comment"]},
    }},
    "facebook": {"name": "🔵 ফেসবুক", "active": True, "list": {
        "fb1": {"name": "ফেসবুক ১K Follower",   "price": 90,  "min": 100, "active": True, "search": "facebook follower",   "avoid": ["like","view","share","comment"]},
        "fb2": {"name": "ফেসবুক ১K React",      "price": 70,  "min": 100, "active": True, "search": "facebook like react", "avoid": ["follow","view","share","comment"]},
        "fb3": {"name": "ফেসবুক ১০০ Comment",   "price": 120, "min": 100, "active": True, "search": "facebook comment",    "avoid": ["follow","like","view","share"]},
        "fb4": {"name": "ফেসবুক ১K Share",      "price": 85,  "min": 100, "active": True, "search": "facebook share",      "avoid": ["follow","like","view","comment"]},
        "fb5": {"name": "ফেসবুক ১K Video View", "price": 20,  "min": 100, "active": True, "search": "facebook video view", "avoid": ["follow","like","share","comment"]},
    }},
    "twitter": {"name": "🐦 Twitter/X", "active": True, "list": {
        "tw1": {"name": "Twitter ১K Follower", "price": 130, "min": 100, "active": True, "search": "twitter follower", "avoid": ["like","view","retweet"]},
        "tw2": {"name": "Twitter ১K Like",     "price": 35,  "min": 100, "active": True, "search": "twitter like",     "avoid": ["follow","view","retweet"]},
        "tw3": {"name": "Twitter ১K Retweet",  "price": 55,  "min": 100, "active": True, "search": "twitter retweet",  "avoid": ["follow","like","view"]},
        "tw4": {"name": "Twitter ১K View",     "price": 18,  "min": 100, "active": True, "search": "twitter view",     "avoid": ["follow","like","retweet"]},
    }},
}

# ===== FEATURE 6: PERSISTENT DATA SAVE/LOAD =====
def save_data():
    """সব ডেটা ফাইলে সেভ করো"""
    try:
        data = {
            "users": {str(k): v for k, v in users.items()},
            "orders": {str(k): v for k, v in orders.items()},
            "blocked": {str(k): {
                "until": v["until"] if v["until"] == "permanent" else v["until"].isoformat()
            } for k, v in blocked.items()},
            "today_stats": today_stats,
            "total_stats": total_stats,
            "bot_on": bot_on,
            "payment": PAYMENT,
            "services_prices": {
                pk: {sk: sv["price"] for sk, sv in pv["list"].items()}
                for pk, pv in SERVICES.items()
            },
            "discount_codes": {
                code: {
                    "pct": v["pct"],
                    "days": v["days"],
                    "expires": v["expires"].isoformat() if isinstance(v["expires"], datetime) else v["expires"],
                    "used_by": v["used_by"]
                } for code, v in discount_codes.items()
            },
            "user_discounts": {
                str(k): {
                    "pct": v["pct"],
                    "expires": v["expires"].isoformat() if isinstance(v["expires"], datetime) else v["expires"]
                } for k, v in user_discounts.items()
            },
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[SAVE ERROR] {e}")

def load_data():
    """ফাইল থেকে ডেটা লোড করো"""
    global users, orders, blocked, today_stats, total_stats, bot_on, discount_codes, user_discounts
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        users = {int(k): v for k, v in data.get("users", {}).items()}
        orders = {int(k): v for k, v in data.get("orders", {}).items()}
        raw_blocked = data.get("blocked", {})
        for k, v in raw_blocked.items():
            if v["until"] == "permanent":
                blocked[int(k)] = {"until": "permanent"}
            else:
                blocked[int(k)] = {"until": datetime.fromisoformat(v["until"])}
        today_stats = data.get("today_stats", {})
        total_stats = data.get("total_stats", {"orders": 0, "revenue": 0.0, "cost": 0.0, "profit": 0.0})
        bot_on = data.get("bot_on", True)
        # Load payment settings
        saved_payment = data.get("payment", {})
        for m in ["bkash", "nagad", "binance"]:
            if m in saved_payment:
                PAYMENT[m].update(saved_payment[m])
        # Load service prices
        saved_prices = data.get("services_prices", {})
        for pk, prices in saved_prices.items():
            if pk in SERVICES:
                for sk, price in prices.items():
                    if sk in SERVICES[pk]["list"]:
                        SERVICES[pk]["list"][sk]["price"] = price
        # Load discount codes
        raw_codes = data.get("discount_codes", {})
        for code, v in raw_codes.items():
            discount_codes[code] = {
                "pct": v["pct"],
                "days": v["days"],
                "expires": datetime.fromisoformat(v["expires"]) if v["expires"] else None,
                "used_by": v["used_by"]
            }
        # Load user discounts
        raw_ud = data.get("user_discounts", {})
        for k, v in raw_ud.items():
            user_discounts[int(k)] = {
                "pct": v["pct"],
                "expires": datetime.fromisoformat(v["expires"]) if v["expires"] else None
            }
        print(f"✅ ডেটা লোড হয়েছে: {len(users)} ইউজার, {len(orders)} অর্ডার")
    except Exception as e:
        print(f"[LOAD ERROR] {e}")

# ===== SMM API =====
def get_smm_services():
    global SMM_CACHE
    try:
        r = requests.post(API_URL, data={"key": API_KEY, "action": "services"}, timeout=15)
        data = r.json()
        SMM_CACHE = {str(s.get("service")): s for s in data}
        return data
    except:
        return []

def get_peakerr_balance():
    try:
        r = requests.post(API_URL, data={"key": API_KEY, "action": "balance"}, timeout=10)
        data = r.json()
        usd = float(data.get("balance", 0))
        bdt = round(usd * 110, 2)
        return usd, bdt
    except:
        return 0, 0

def find_best_id(search, avoid):
    try:
        if not SMM_CACHE:
            get_smm_services()
        results = []
        for svc in SMM_CACHE.values():
            name = svc.get("name", "").lower()
            if all(t.lower() in name for t in search.split()):
                if not any(a.lower() in name for a in avoid):
                    results.append(svc)
        if not results:
            return None, None
        pref = [s for s in results if any(w in s.get("name","").lower() for w in ["lifetime","non drop","nondrop","no drop"])]
        pool = pref if pref else results
        best = min(pool, key=lambda x: float(x.get("rate", 9999)))
        return str(best.get("service")), float(best.get("rate", 0))
    except:
        return None, None

def find_by_name(query):
    try:
        if not SMM_CACHE:
            get_smm_services()
        results = []
        for svc in SMM_CACHE.values():
            if query.lower() in svc.get("name","").lower():
                results.append(svc)
        if not results:
            return None, None, None
        best = min(results, key=lambda x: float(x.get("rate", 9999)))
        return str(best.get("service")), float(best.get("rate", 0)), best.get("name","")
    except:
        return None, None, None

def place_order(sid, link, qty):
    try:
        r = requests.post(API_URL, data={"key": API_KEY, "action": "add", "service": sid, "link": link, "quantity": qty}, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def auto_protect():
    updated = []
    try:
        get_smm_services()
        for pk, pv in SERVICES.items():
            for sk, sv in pv["list"].items():
                sid, rate = find_best_id(sv["search"], sv["avoid"])
                if rate:
                    smm_bdt = round(rate * 110, 2)
                    protected = round(smm_bdt * (1 + PROFIT_PCT/100), 2)
                    if protected > sv["price"]:
                        old = sv["price"]
                        SERVICES[pk]["list"][sk]["price"] = protected
                        updated.append(f"📈 {sv['name']}: {old} → {protected} TK")
    except:
        pass
    return updated

# ===== HELPERS =====
def get_user(uid, u=None):
    if uid not in users:
        users[uid] = {
            "balance": 0.0, "spent": 0.0, "orders": [],
            "name": u.first_name if u else "User",
            "username": f"@{u.username}" if u and u.username else "N/A",
            "joined": datetime.now().isoformat(),   # feature 5: join time track
            "last_discount_sent": None              # feature 5: last discount notification
        }
    return users[uid]

def is_blocked(uid):
    if uid in blocked:
        b = blocked[uid]
        if b["until"] == "permanent":
            return True
        if datetime.now() < b["until"]:
            return True
        else:
            del blocked[uid]
    return False

def get_price(skey):
    for pv in SERVICES.values():
        if skey in pv["list"]:
            return pv["list"][skey]["price"]
    return 0

def get_price_with_discount(skey, uid):
    """ইউজারের ডিসকাউন্ট থাকলে দাম কমিয়ে দেয়"""
    base_price = get_price(skey)
    disc = user_discounts.get(uid)
    if disc and disc["expires"] and datetime.now() < disc["expires"]:
        pct = disc["pct"]
        return round(base_price * (1 - pct/100), 2), pct
    return base_price, 0

def update_stats(rev, cost):
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in today_stats:
        today_stats[today] = {"orders": 0, "revenue": 0.0, "cost": 0.0, "profit": 0.0}
    today_stats[today]["orders"] += 1
    today_stats[today]["revenue"] += rev
    today_stats[today]["cost"] += cost
    today_stats[today]["profit"] += rev - cost
    total_stats["orders"] += 1
    total_stats["revenue"] += rev
    total_stats["cost"] += cost
    total_stats["profit"] += rev - cost

def main_kb(uid=None):
    kbd = [
        ["🟢 সার্ভিস কিনুন", "💰 ডিপোজিট করুন"],
        ["📋 সার্ভিস প্রাইস", "👤 আমার প্রোফাইল"],
        ["🎟️ ডিসকাউন্ট কোড", "📞 সাপোর্ট"]
    ]
    return ReplyKeyboardMarkup(kbd, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        ["📊 Statistics", "💹 My Profit"],
        ["📢 Broadcast", "💰 SMM Prices"],
        ["⚙️ Payment Settings", "🚫 Block User"],
        ["📋 All Commands", "🔴 Bot OFF" if bot_on else "🟢 Bot ON"],
        ["👤 Check User", "💸 Refund User"],
        ["🛒 Admin Order", "💎 Peakerr Balance"],
        ["👥 সব ইউজার লিস্ট", "🎟️ Discount Code বানাও"],
        ["🔙 Main Menu"]
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup([["❌ বাতিল করুন"]], resize_keyboard=True)

async def check_joined(bot, uid):
    try:
        m1 = await bot.get_chat_member(CHANNEL_1, uid)
        m2 = await bot.get_chat_member(CHANNEL_2, uid)
        return (m1.status in ["member","administrator","creator"] and
                m2.status in ["member","administrator","creator"])
    except:
        return True

async def process_order(context, uid, sdata, skey, qty, link, discount_pct=0):
    u = get_user(uid)
    price = get_price(skey)
    if discount_pct > 0:
        price = round(price * (1 - discount_pct/100), 2)
    cost = round((qty / 1000) * price, 2)
    sid, smm_rate = find_best_id(sdata["search"], sdata["avoid"])
    actual_cost = 0.0
    if sid and smm_rate:
        smm_bdt = round(smm_rate * 110, 2)
        if smm_bdt > price:
            new_price = round(smm_bdt * (1 + PROFIT_PCT/100), 2)
            for pk, pv in SERVICES.items():
                if skey in pv["list"]:
                    SERVICES[pk]["list"][skey]["price"] = new_price
            return False, (f"⚠️ দাম আপডেট হয়েছে!\n\n"
                           f"📦 {sdata['name']}\n"
                           f"💰 নতুন দাম: {new_price} TK/1000\n\n"
                           f"অনুগ্রহ করে আবার অর্ডার করুন।")
        result = place_order(sid, link, qty)
        actual_cost = round((qty / 1000) * smm_rate * 110, 2)
        if "error" in result or result.get("order") is None:
            error_msg = result.get("error", str(result))
            try:
                await context.bot.send_message(ADMIN_ID,
                    f"❌ অর্ডার Failed!\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 ইউজার: {u['name']} (ID: {uid})\n"
                    f"📦 সার্ভিস: {sdata['name']}\n"
                    f"🔢 পরিমাণ: {qty}\n"
                    f"💰 খরচ: {cost:.2f} TK\n"
                    f"❌ কারণ: {error_msg}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Refund দেবেন?",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Yes — Refund দিন", callback_data=f"failrefund_{uid}_{cost}"),
                        InlineKeyboardButton("❌ No — Retry হবে", callback_data=f"failretry_{uid}_{cost}")
                    ]])
                )
            except:
                pass
    update_stats(cost, actual_cost)
    oid = len(orders) + 1
    orders[oid] = {"uid": uid, "name": u["name"], "service": sdata["name"],
                   "qty": qty, "cost": cost, "actual_cost": actual_cost,
                   "link": link, "status": "Processing",
                   "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
    u["orders"].append(oid)
    u["spent"] = u.get("spent", 0) + cost
    save_data()
    try:
        await context.bot.send_message(LOG_CH,
            f"🆕 NEW AUTO ORDER SUCCESS 🆕\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 ইউজার: {u['name']}\n"
            f"📦 সার্ভিস: {sdata['name']}\n"
            f"🔢 পরিমাণ: {qty}\n"
            f"💰 মোট খরচ: {cost:.2f} TK\n"
            f"✅ স্ট্যাটাস: Processing\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    except:
        pass
    return True, cost

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    u = get_user(uid, user)

    if not bot_on and uid != ADMIN_ID:
        await update.message.reply_text("⚠️ বট সাময়িকভাবে বন্ধ আছে!\nএকটু পরে আবার চেষ্টা করুন। 🙏")
        return ConversationHandler.END

    if is_blocked(uid):
        await update.message.reply_text("🚫 আপনার একাউন্ট ব্লক করা হয়েছে!\nসমস্যা হলে Support এ যোগাযোগ করুন।")
        return ConversationHandler.END

    joined = await check_joined(context.bot, uid)
    if not joined:
        await update.message.reply_text(
            f"🚀 {BOT_NAME} তে স্বাগতম! 🚀\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ বট ব্যবহার করতে নিচের ২টি\n"
            "চ্যানেলে অবশ্যই জয়েন করুন!\n\n"
            f"📢 চ্যানেল ১: {CHANNEL_1}\n"
            f"📢 চ্যানেল ২: {CHANNEL_2}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ জয়েন করার পর Verify বাটন চাপুন।",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Channel 1 Join করুন", url=f"https://t.me/{CHANNEL_1.replace('@','')}")],
                [InlineKeyboardButton("📢 Channel 2 Join করুন", url=f"https://t.me/{CHANNEL_2.replace('@','')}")],
                [InlineKeyboardButton("✅ Verify করুন", callback_data="verify")]
            ])
        )
        return ConversationHandler.END

    # ===== FEATURE 5: Auto discount tracking (start time for new users) =====
    if "joined" not in u:
        u["joined"] = datetime.now().isoformat()
    if "last_discount_sent" not in u:
        u["last_discount_sent"] = None

    if uid == ADMIN_ID:
        usd, bdt = get_peakerr_balance()
        await update.message.reply_text(
            f"⭐ ADMIN DASHBOARD ⭐\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Admin: {u['name']}\n"
            f"👥 মোট ইউজার: {len(users)} জন\n"
            f"📦 মোট অর্ডার: {len(orders)} টি\n"
            f"🏆 মোট লাভ: {total_stats['profit']:.2f} TK\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 Peakerr Balance:\n"
            f"   ${usd:.2f} = {bdt:.2f} TK\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 বট: {'✅ চালু' if bot_on else '❌ বন্ধ'}\n"
            f"🔴 Bkash: {'✅' if PAYMENT['bkash']['active'] else '❌'} | "
            f"🟠 Nagad: {'✅' if PAYMENT['nagad']['active'] else '❌'} | "
            f"💎 Binance: {'✅' if PAYMENT['binance']['active'] else '❌'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END

    # Check active discount for user
    disc_info = ""
    disc = user_discounts.get(uid)
    if disc and disc["expires"] and datetime.now() < disc["expires"]:
        remaining = disc["expires"] - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        disc_info = f"\n🎁 সক্রিয় ডিসকাউন্ট: {disc['pct']}% OFF (আর {hours} ঘণ্টা বাকি)\n"

    await update.message.reply_text(
        f"⭐ SERVICE MASTER DASHBOARD ⭐\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 ইউজার: {u['name']}\n"
        f"💰 ব্যালেন্স: {u['balance']:.2f} TK\n"
        f"📊 মোট খরচ: {u.get('spent', 0):.2f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
        f"{disc_info}\n"
        f"নিচের বাটন থেকে সার্ভিস অর্ডার করুন:",
        reply_markup=main_kb(uid)
    )
    return ConversationHandler.END

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if await check_joined(context.bot, uid):
        get_user(uid, query.from_user)
        await query.message.reply_text("✅ ভেরিফিকেশন সফল!\nএখন বট ব্যবহার করতে পারবেন। 😊", reply_markup=main_kb())
    else:
        await query.answer("❌ এখনো জয়েন করেননি!\nজয়েন করে আবার চেষ্টা করুন।", show_alert=True)

# ===== CANCEL HANDLER =====
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data.clear()
    if uid == ADMIN_ID:
        await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=admin_kb())
    else:
        await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=main_kb())
    return ConversationHandler.END

# ===== BUY SERVICE =====
async def buy_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    platforms = [(pk, pv) for pk, pv in SERVICES.items() if pv["active"]]
    btns = []
    row = []
    for pk, pv in platforms:
        row.append(pv["name"])
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append(["🔙 মেইন মেনু"])
    await update.message.reply_text(
        "🛒 সার্ভিস মেনু ওপেন হয়েছে\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "নিচের কিবোর্ড থেকে আপনার পছন্দের\n"
        "সোশ্যাল মিডিয়া সিলেক্ট করুন:",
        reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True)
    )
    return S_PLATFORM

async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    if text == "🔙 মেইন মেনু":
        await start(update, context)
        return ConversationHandler.END
    p = None
    for pk, pv in SERVICES.items():
        if pv["name"] == text and pv["active"]:
            p = pk
            break
    if not p:
        await update.message.reply_text("❌ সঠিক অপশন সিলেক্ট করুন।")
        return S_PLATFORM
    context.user_data["platform"] = p
    active_svcs = [(k, v) for k, v in SERVICES[p]["list"].items() if v["active"]]
    btns = []
    for i in range(0, len(active_svcs), 2):
        row = [active_svcs[i][1]["name"]]
        if i+1 < len(active_svcs):
            row.append(active_svcs[i+1][1]["name"])
        btns.append(row)
    btns.append(["🔙 ব্যাক করুন"])
    # Check discount
    disc = user_discounts.get(uid)
    disc_note = ""
    if disc and disc["expires"] and datetime.now() < disc["expires"]:
        disc_note = f"\n🎁 আপনার {disc['pct']}% ডিসকাউন্ট সক্রিয়!"
    await update.message.reply_text(
        f"{SERVICES[p]['name']} SERVICES\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"নিচের কিবোর্ড থেকে সার্ভিস বেছে নিন:\n\n"
        f"⚡ Fast Delivery | 💎 Best Quality{disc_note}",
        reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True)
    )
    return S_SERVICE

async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    if text == "🔙 ব্যাক করুন":
        return await buy_service(update, context)
    p = context.user_data.get("platform")
    found = None
    fkey = None
    for k, v in SERVICES[p]["list"].items():
        if v["name"] == text and v["active"]:
            found = v
            fkey = k
            break
    if not found:
        await update.message.reply_text("❌ সঠিক সার্ভিস সিলেক্ট করুন।")
        return S_SERVICE
    context.user_data["skey"] = fkey
    context.user_data["sdata"] = found
    price, disc_pct = get_price_with_discount(fkey, uid)
    disc_note = f"\n🎁 {disc_pct}% ডিসকাউন্ট প্রয়োগ হয়েছে!" if disc_pct > 0 else ""
    await update.message.reply_text(
        f"💎 {text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 দাম: {price} TK (প্রতি ১০০০){disc_note}\n"
        f"📋 সর্বনিম্ন অর্ডার = {found['min']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"আপনি কতগুলো নিতে চান?\n"
        f"(শুধু সংখ্যা লিখুন, যেমন: 1000)",
        reply_markup=ReplyKeyboardMarkup([["🔙 ব্যাক করুন"]], resize_keyboard=True)
    )
    return S_QTY

async def enter_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    if text == "🔙 ব্যাক করুন":
        return await buy_service(update, context)
    try:
        qty = int(text)
    except:
        await update.message.reply_text("❌ ভুল সংখ্যা!\nদয়া করে শুধু সংখ্যা লিখুন।\nযেমন: 1000")
        return S_QTY
    sdata = context.user_data["sdata"]
    skey = context.user_data["skey"]
    u = get_user(uid)
    if qty < sdata["min"]:
        await update.message.reply_text(f"❌ সর্বনিম্ন {sdata['min']} টি অর্ডার করতে হবে!\nআবার লিখুন:")
        return S_QTY
    price, disc_pct = get_price_with_discount(skey, uid)
    cost = round((qty / 1000) * price, 2)
    if u["balance"] < cost:
        await update.message.reply_text(
            f"❌ পর্যাপ্ত ব্যালেন্স নেই!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 প্রয়োজন: {cost:.2f} TK\n"
            f"💳 আপনার ব্যালেন্স: {u['balance']:.2f} TK\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 ডিপোজিট করতে মেইন মেনু থেকে\n'ডিপোজিট করুন' চাপুন।",
            reply_markup=main_kb()
        )
        return ConversationHandler.END
    context.user_data["qty"] = qty
    context.user_data["cost"] = cost
    context.user_data["disc_pct"] = disc_pct
    disc_note = f"\n🎁 {disc_pct}% ডিসকাউন্ট প্রয়োগ!" if disc_pct > 0 else ""
    await update.message.reply_text(
        f"✅ {qty} টি সিলেক্ট করা হয়েছে{disc_note}\n"
        f"💰 মোট খরচ হবে: {cost:.2f} TK\n\n"
        f"🔗 এখন আপনার লিংক দিন:\n(যেমন: https://t.me/yourchannel)",
        reply_markup=ReplyKeyboardMarkup([["🔙 ব্যাক করুন"]], resize_keyboard=True)
    )
    return S_LINK

async def enter_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 ব্যাক করুন":
        return await buy_service(update, context)
    sdata = context.user_data["sdata"]
    skey = context.user_data["skey"]
    qty = context.user_data["qty"]
    disc_pct = context.user_data.get("disc_pct", 0)
    uid = update.effective_user.id
    u = get_user(uid)
    price, _ = get_price_with_discount(skey, uid)
    cost = round((qty / 1000) * price, 2)
    u["balance"] -= cost
    success, result = await process_order(context, uid, sdata, skey, qty, text, disc_pct)
    if not success:
        u["balance"] += cost
        await update.message.reply_text(result, reply_markup=main_kb())
        return ConversationHandler.END
    await update.message.reply_text(
        f"✅ অর্ডার সফলভাবে দেওয়া হয়েছে!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 সার্ভিস: {sdata['name']}\n"
        f"🔢 পরিমাণ: {qty}\n"
        f"💰 খরচ: {cost:.2f} TK\n"
        f"💳 বাকি ব্যালেন্স: {u['balance']:.2f} TK\n"
        f"✅ স্ট্যাটাস: Processing\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ শীঘ্রই ডেলিভারি শুরু হবে!\n"
        f"সমস্যা হলে Support এ জানান। 😊",
        reply_markup=main_kb()
    )
    return ConversationHandler.END

# ===== DEPOSIT =====
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    methods = []
    if PAYMENT["bkash"]["active"]:
        methods.append("🔴 Bkash")
    if PAYMENT["nagad"]["active"]:
        methods.append("🟠 Nagad")
    if PAYMENT["binance"]["active"]:
        methods.append("💎 Binance")
    method_text = " | ".join(methods) if methods else "কোনো মেথড নেই"
    await update.message.reply_text(
        f"💰 ডিপোজিট করুন\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Available: {method_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"কত টাকা ডিপোজিট করতে চান?\n\n"
        f"⚠️ সর্বনিম্ন ১০ টাকা\n"
        f"⚠️ সর্বোচ্চ ৫০০০ টাকা\n\n"
        f"শুধু সংখ্যা লিখুন (যেমন: 100)",
        reply_markup=ReplyKeyboardMarkup([["🔙 মেইন মেনু"]], resize_keyboard=True)
    )
    return D_AMOUNT

async def dep_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 মেইন মেনু":
        await start(update, context)
        return ConversationHandler.END
    try:
        amount = float(text)
        if amount < 10 or amount > 5000:
            raise ValueError
    except:
        await update.message.reply_text("❌ ভুল সংখ্যা!\nসর্বনিম্ন ১০ - সর্বোচ্চ ৫০০০ টাকা।\nআবার লিখুন:")
        return D_AMOUNT
    context.user_data["dep_amount"] = amount
    btns = []
    row = []
    if PAYMENT["bkash"]["active"]:
        row.append(InlineKeyboardButton("🔴 Bkash", callback_data="pay_bkash"))
    if PAYMENT["nagad"]["active"]:
        row.append(InlineKeyboardButton("🟠 Nagad", callback_data="pay_nagad"))
    if row:
        btns.append(row)
    if PAYMENT["binance"]["active"]:
        btns.append([InlineKeyboardButton("💎 Binance", callback_data="pay_binance")])
    btns.append([InlineKeyboardButton("🔙 মেইন মেনু", callback_data="pay_back")])
    await update.message.reply_text(
        f"💰 DEPOSIT AMOUNT: {amount:.0f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ পেমেন্ট মেথড বেছে নিন:",
        reply_markup=InlineKeyboardMarkup(btns)
    )
    return D_METHOD

async def pay_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    amount = context.user_data.get("dep_amount", 0)
    if data == "pay_back":
        await query.message.reply_text("মেইন মেনু:", reply_markup=main_kb())
        return ConversationHandler.END
    if data == "pay_bkash":
        context.user_data["dep_method"] = "Bkash"
        await query.message.reply_text(
            f"🔴 Bkash পেমেন্ট\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 পরিমাণ: {amount:.0f} TK\n\n"
            f"📱 Bkash নম্বর:\n"
            f"👉 {PAYMENT['bkash']['number']}\n\n"
            f"✅ উপরের নম্বরে {amount:.0f} TK\n"
            f"   Send Money করুন।\n\n"
            f"📝 পাঠানো হলে Transaction ID লিখুন:",
            reply_markup=ReplyKeyboardMarkup([["🔙 মেইন মেনু"]], resize_keyboard=True)
        )
        return D_TRXID
    elif data == "pay_nagad":
        context.user_data["dep_method"] = "Nagad"
        await query.message.reply_text(
            f"🟠 Nagad পেমেন্ট\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 পরিমাণ: {amount:.0f} TK\n\n"
            f"📱 Nagad নম্বর:\n"
            f"👉 {PAYMENT['nagad']['number']}\n\n"
            f"✅ উপরের নম্বরে {amount:.0f} TK\n"
            f"   Send Money করুন।\n\n"
            f"📸 পেমেন্টের Transaction স্ক্রিনশট পাঠান:",
            reply_markup=ReplyKeyboardMarkup([["🔙 মেইন মেনু"]], resize_keyboard=True)
        )
        return D_SCREENSHOT
    elif data == "pay_binance":
        context.user_data["dep_method"] = "Binance"
        await query.message.reply_text(
            f"💎 Binance পেমেন্ট\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 পরিমাণ: {amount:.0f} TK\n\n"
            f"🆔 Binance Pay ID:\n"
            f"👉 {PAYMENT['binance']['id']}\n\n"
            f"✅ উপরের ID তে {amount:.0f} TK পাঠান।\n\n"
            f"📸 পেমেন্টের স্ক্রিনশট পাঠান:",
            reply_markup=ReplyKeyboardMarkup([["🔙 মেইন মেনু"]], resize_keyboard=True)
        )
        return D_SCREENSHOT

async def dep_trxid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 মেইন মেনু":
        await start(update, context)
        return ConversationHandler.END
    amount = context.user_data.get("dep_amount", 0)
    method = context.user_data.get("dep_method", "")
    uid = update.effective_user.id
    u = get_user(uid)
    await context.bot.send_message(ADMIN_ID,
        f"💰 নতুন Deposit Request!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {u['name']} ({u['username']})\n"
        f"🆔 ID: {uid}\n"
        f"💵 Amount: {amount:.0f} TK\n"
        f"🏦 Method: {method}\n"
        f"📝 TrxID: {text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}_{amount}")
        ]])
    )
    await update.message.reply_text(
        "✅ ডিপোজিট রিকোয়েস্ট পাঠানো হয়েছে!\n\n"
        "⏳ অ্যাডমিন যাচাই করার পর ব্যালেন্সে যোগ হবে।\n"
        "সাধারণত ৫-১৫ মিনিটের মধ্যে হয়।",
        reply_markup=main_kb()
    )
    return ConversationHandler.END

async def dep_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text == "🔙 মেইন মেনু":
        await start(update, context)
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("❌ স্ক্রিনশট পাওয়া যায়নি!\nদয়া করে পেমেন্টের স্ক্রিনশট (Photo) পাঠান।")
        return D_SCREENSHOT
    amount = context.user_data.get("dep_amount", 0)
    method = context.user_data.get("dep_method", "")
    uid = update.effective_user.id
    u = get_user(uid)
    photo = update.message.photo[-1].file_id
    await context.bot.send_photo(ADMIN_ID, photo,
        caption=f"💰 নতুন Deposit Request!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {u['name']} ({u['username']})\n"
                f"🆔 ID: {uid}\n"
                f"💵 Amount: {amount:.0f} TK\n"
                f"🏦 Method: {method}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}_{amount}")
        ]])
    )
    await update.message.reply_text(
        "✅ স্ক্রিনশট পাঠানো হয়েছে!\n\n"
        "⏳ অ্যাডমিন যাচাই করার পর ব্যালেন্সে যোগ হবে।",
        reply_markup=main_kb()
    )
    return ConversationHandler.END

async def approve_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split("_")
    action, uid, amount = parts[0], int(parts[1]), float(parts[2])
    u = get_user(uid)
    if action == "approve":
        u["balance"] += amount
        save_data()
        txt = (query.message.caption or query.message.text or "") + f"\n\n✅ APPROVED — {amount:.0f} TK যোগ!"
        try:
            await query.message.edit_caption(txt)
        except:
            await query.message.edit_text(txt)
        try:
            await context.bot.send_message(uid,
                f"🎉 ডিপোজিট সফল!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 {amount:.0f} TK যোগ হয়েছে!\n"
                f"💳 নতুন ব্যালেন্স: {u['balance']:.2f} TK\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"এখন সার্ভিস অর্ডার করুন! 😊"
            )
        except:
            pass
    else:
        txt = (query.message.caption or query.message.text or "") + "\n\n❌ REJECTED"
        try:
            await query.message.edit_caption(txt)
        except:
            await query.message.edit_text(txt)
        try:
            await context.bot.send_message(uid, "❌ ডিপোজিট বাতিল হয়েছে!\nসমস্যা হলে Support এ যোগাযোগ করুন।")
        except:
            pass

# ===== USER PAGES =====
async def service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    disc = user_discounts.get(uid)
    has_disc = disc and disc["expires"] and datetime.now() < disc["expires"]
    disc_pct = disc["pct"] if has_disc else 0

    msg = "💬 SOCIAL MEDIA ALL SERVICE 💬\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    if has_disc:
        msg += f"🎁 আপনার {disc_pct}% ডিসকাউন্ট সক্রিয়!\n\n"
    for pv in SERVICES.values():
        if not pv["active"]:
            continue
        msg += f"💥 {pv['name']} 👇\n"
        for k, s in pv["list"].items():
            if s["active"]:
                base = get_price(k)
                if has_disc:
                    discounted = round(base * (1 - disc_pct/100), 2)
                    msg += f"💠 {s['name']} = ~~{base}~~ {discounted} TK\n"
                else:
                    msg += f"💠 {s['name']} = {base} TK\n"
        msg += "\n"
    msg += (f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎁 সর্বনিম্ন ১ টাকা অর্ডার করতে পারবেন।\n"
            f"📞 বিস্তারিত: {OWNER}\n\n"
            f"নিচের বাটন থেকে অর্ডার করুন 👇")
    await update.message.reply_text(msg, reply_markup=main_kb())

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id, user)
    uid = user.id
    disc = user_discounts.get(uid)
    disc_info = ""
    if disc and disc["expires"] and datetime.now() < disc["expires"]:
        remaining = disc["expires"] - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        disc_info = f"\n🎁 ডিসকাউন্ট: {disc['pct']}% OFF ({hours} ঘণ্টা বাকি)"
    await update.message.reply_text(
        f"👤 USER ACCOUNT DETAILS 👤\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 নাম: {user.first_name}\n"
        f"🆔 আইডি: {user.id}\n"
        f"🔗 ইউজার: {u['username']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ব্যালেন্স: {u['balance']:.2f} TK\n"
        f"💸 মোট খরচ: {u.get('spent',0):.2f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 মোট অর্ডার: {len(u['orders'])} টি\n"
        f"👥 Bot মেম্বার: {len(users)} জন\n"
        f"🏆 স্ট্যাটাস: Verified ✅{disc_info}",
        reply_markup=main_kb()
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 সাপোর্ট সেন্টার\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"কোনো সমস্যা হলে সাপোর্টে যোগাযোগ করুন।\n\n"
        f"⏰ সাপোর্ট সময়: সকাল ১০টা - রাত ১০টা\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"নিচের বাটনে ক্লিক করে মেসেজ দিন:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Support এ মেসেজ দিন", url=f"https://t.me/{SUPPORT.replace('@','')}")],
            [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER.replace('@','')}")],
        ])
    )

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if not u["orders"]:
        await update.message.reply_text("📦 এখনো কোনো অর্ডার করেননি।")
        return
    msg = "📋 আপনার অর্ডার হিস্ট্রি\n━━━━━━━━━━━━━━━━━━━━━━\n"
    total = 0
    for oid in u["orders"][-10:]:
        if oid in orders:
            o = orders[oid]
            msg += f"📦 {o['service']}\n   পরিমাণ: {o['qty']} | খরচ: {o['cost']:.2f} TK\n"
            total += o["cost"]
    msg += f"━━━━━━━━━━━━━━━━━━━━━━\n💰 মোট: {total:.2f} TK"
    await update.message.reply_text(msg, reply_markup=main_kb())

# ===== ADMIN =====
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    usd, bdt = get_peakerr_balance()
    await update.message.reply_text(
        f"📊 STATISTICS\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 ইউজার: {len(users)} জন\n"
        f"📦 অর্ডার: {len(orders)} টি\n"
        f"💰 মোট আয়: {total_stats['revenue']:.2f} TK\n"
        f"💸 SMM খরচ: {total_stats['cost']:.2f} TK\n"
        f"🏆 মোট লাভ: {total_stats['profit']:.2f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Peakerr Balance: ${usd:.2f} = {bdt:.2f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_kb()
    )

async def my_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    td = today_stats.get(today, {"orders":0,"revenue":0,"cost":0,"profit":0})
    usd, bdt = get_peakerr_balance()
    await update.message.reply_text(
        f"💎 MY PROFIT DASHBOARD 💎\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 আজকে ({today})\n"
        f"📦 {td['orders']} অর্ডার\n"
        f"💰 বিক্রি: {td['revenue']:.2f} TK\n"
        f"💸 SMM খরচ: {td['cost']:.2f} TK\n"
        f"🏆 আজকের লাভ: {td['profit']:.2f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 সারাজীবন\n"
        f"📦 {total_stats['orders']} অর্ডার\n"
        f"💰 {total_stats['revenue']:.2f} TK বিক্রি\n"
        f"💸 {total_stats['cost']:.2f} TK খরচ\n"
        f"🏆 {total_stats['profit']:.2f} TK লাভ\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Peakerr Balance: ${usd:.2f} = {bdt:.2f} TK\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_kb()
    )

async def smm_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⏳ Peakerr থেকে দাম আনছি...")
    get_smm_services()
    msg = "💹 PEAKERR REAL PRICE (BDT)\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for pk, pv in SERVICES.items():
        msg += f"{pv['name']}:\n"
        for sk, sv in pv["list"].items():
            sid, rate = find_best_id(sv["search"], sv["avoid"])
            price = get_price(sk)
            if rate:
                bdt = round(rate * 110, 2)
                profit = round(price - bdt, 2)
                e = "✅" if profit > 0 else "❌"
                msg += f"{e} {sv['name']}:\n   তোমার={price} | Peakerr={bdt} | লাভ={profit} TK\n"
            else:
                msg += f"⚠️ {sv['name']}: ID পাওয়া যায়নি\n"
        msg += "\n"
    await update.message.reply_text(msg, reply_markup=admin_kb())

async def all_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"📋 ALL ADMIN COMMANDS\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 দাম পরিবর্তন:\n"
        f"• /price_up 20 → সব দাম 20% বাড়াও\n"
        f"• /price_down 10 → সব দাম 10% কমাও\n"
        f"• /list → নিজে দাম সেট করো\n"
        f"• /protect → Peakerr দাম বাড়লে অটো আপডেট\n\n"
        f"📊 রিপোর্ট:\n"
        f"• /today → আজকের বিক্রি ও লাভ\n"
        f"• /history → অর্ডার হিস্ট্রি\n\n"
        f"⚙️ Service Management:\n"
        f"• /toggle_svc tg1 → service চালু/বন্ধ\n"
        f"• /toggle_platform telegram → platform চালু/বন্ধ\n"
        f"• /service=telegram member → custom service অর্ডার\n\n"
        f"🎟️ Discount:\n"
        f"• 'Discount Code বানাও' বাটন চাপো\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_kb()
    )
    msg2 = "📋 SERVICE KEYS:\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for pv in SERVICES.values():
        msg2 += f"\n{pv['name']}:\n"
        for sk, sv in pv["list"].items():
            status = "✅" if sv["active"] else "❌"
            msg2 += f"{status} {sk} = {sv['name']} ({get_price(sk)} TK)\n"
    await update.message.reply_text(msg2, reply_markup=admin_kb())

async def payment_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    bk = "✅ চালু" if PAYMENT["bkash"]["active"] else "❌ বন্ধ"
    ng = "✅ চালু" if PAYMENT["nagad"]["active"] else "❌ বন্ধ"
    bn = "✅ চালু" if PAYMENT["binance"]["active"] else "❌ বন্ধ"
    await update.message.reply_text(
        f"⚙️ PAYMENT SETTINGS\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 Bkash: {bk} | {PAYMENT['bkash']['number']}\n"
        f"🟠 Nagad: {ng} | {PAYMENT['nagad']['number']}\n"
        f"💎 Binance: {bn} | {PAYMENT['binance']['id']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 Bkash ON/OFF", callback_data="tog_bkash"),
             InlineKeyboardButton("🟠 Nagad ON/OFF", callback_data="tog_nagad")],
            [InlineKeyboardButton("💎 Binance ON/OFF", callback_data="tog_binance")],
            [InlineKeyboardButton("✏️ Bkash নম্বর", callback_data="ch_bkash"),
             InlineKeyboardButton("✏️ Nagad নম্বর", callback_data="ch_nagad")],
            [InlineKeyboardButton("✏️ Binance ID", callback_data="ch_binance")],
        ])
    )

async def pay_settings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    data = query.data
    if data == "tog_bkash":
        PAYMENT["bkash"]["active"] = not PAYMENT["bkash"]["active"]
        status = "✅ চালু" if PAYMENT["bkash"]["active"] else "❌ বন্ধ"
        await query.answer(f"🔴 Bkash এখন {status}!", show_alert=True)
        await context.bot.send_message(ADMIN_ID, f"⚙️ Payment Update!\n🔴 Bkash এখন {status}!")
        save_data()
    elif data == "tog_nagad":
        PAYMENT["nagad"]["active"] = not PAYMENT["nagad"]["active"]
        status = "✅ চালু" if PAYMENT["nagad"]["active"] else "❌ বন্ধ"
        await query.answer(f"🟠 Nagad এখন {status}!", show_alert=True)
        await context.bot.send_message(ADMIN_ID, f"⚙️ Payment Update!\n🟠 Nagad এখন {status}!")
        save_data()
    elif data == "tog_binance":
        PAYMENT["binance"]["active"] = not PAYMENT["binance"]["active"]
        status = "✅ চালু" if PAYMENT["binance"]["active"] else "❌ বন্ধ"
        await query.answer(f"💎 Binance এখন {status}!", show_alert=True)
        await context.bot.send_message(ADMIN_ID, f"⚙️ Payment Update!\n💎 Binance এখন {status}!")
        save_data()
    elif data == "ch_bkash":
        await query.message.reply_text("🔴 নতুন Bkash নম্বর লিখুন:", reply_markup=cancel_kb())
        context.user_data["ch_type"] = "bkash"
        return CH_BKASH
    elif data == "ch_nagad":
        await query.message.reply_text("🟠 নতুন Nagad নম্বর লিখুন:", reply_markup=cancel_kb())
        context.user_data["ch_type"] = "nagad"
        return CH_NAGAD
    elif data == "ch_binance":
        await query.message.reply_text("💎 নতুন Binance Pay ID লিখুন:", reply_markup=cancel_kb())
        context.user_data["ch_type"] = "binance"
        return CH_BINANCE

async def change_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    ch = context.user_data.get("ch_type")
    if ch == "bkash":
        PAYMENT["bkash"]["number"] = text
        await update.message.reply_text(f"✅ Bkash নম্বর পরিবর্তন: {text}", reply_markup=admin_kb())
    elif ch == "nagad":
        PAYMENT["nagad"]["number"] = text
        await update.message.reply_text(f"✅ Nagad নম্বর পরিবর্তন: {text}", reply_markup=admin_kb())
    elif ch == "binance":
        PAYMENT["binance"]["id"] = text
        await update.message.reply_text(f"✅ Binance ID পরিবর্তন: {text}", reply_markup=admin_kb())
    save_data()
    return ConversationHandler.END

async def block_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("🚫 Block করতে User এর Telegram ID লিখুন:", reply_markup=cancel_kb())
    return BLOCK_ID

async def block_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        uid = int(update.message.text)
        context.user_data["block_uid"] = uid
        u = users.get(uid, {})
        name = u.get("name", "Unknown")
        await update.message.reply_text(
            f"👤 User: {name} (ID: {uid})\nকতদিনের জন্য block করবেন?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("1 দিন", callback_data="blk_1"),
                 InlineKeyboardButton("7 দিন", callback_data="blk_7")],
                [InlineKeyboardButton("30 দিন", callback_data="blk_30"),
                 InlineKeyboardButton("🔴 Permanent", callback_data="blk_perm")],
            ])
        )
        return BLOCK_DAYS
    except:
        await update.message.reply_text("❌ সঠিক Telegram ID দিন।")
        return BLOCK_ID

async def block_days_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = context.user_data.get("block_uid")
    data = query.data
    if data == "blk_perm":
        blocked[uid] = {"until": "permanent"}
        await query.message.reply_text(f"🚫 {uid} Permanently blocked!", reply_markup=admin_kb())
    else:
        days = int(data.replace("blk_",""))
        blocked[uid] = {"until": datetime.now() + timedelta(days=days)}
        await query.message.reply_text(f"🚫 {uid} — {days} দিনের জন্য blocked!", reply_markup=admin_kb())
    save_data()
    try:
        await context.bot.send_message(uid, "🚫 আপনার একাউন্ট সাময়িকভাবে বন্ধ করা হয়েছে।\nসমস্যা হলে Support এ যোগাযোগ করুন।")
    except:
        pass
    return ConversationHandler.END

async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("👤 User এর Telegram ID লিখুন:", reply_markup=cancel_kb())
    return CHK_UID

async def check_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        uid = int(update.message.text)
        if uid not in users:
            await update.message.reply_text("❌ এই ID তে কোনো User পাওয়া যায়নি।", reply_markup=admin_kb())
            return ConversationHandler.END
        u = users[uid]
        user_orders = [orders[oid] for oid in u["orders"] if oid in orders]
        msg = (f"👤 USER INFO\n━━━━━━━━━━━━━━━━━━━━━━\n"
               f"🔥 নাম: {u['name']}\n🆔 ID: {uid}\n🔗 {u['username']}\n"
               f"━━━━━━━━━━━━━━━━━━━━━━\n"
               f"💰 ব্যালেন্স: {u['balance']:.2f} TK\n"
               f"💸 মোট খরচ: {u.get('spent',0):.2f} TK\n"
               f"📦 মোট অর্ডার: {len(user_orders)} টি\n"
               f"{'🚫 BLOCKED' if is_blocked(uid) else '✅ Active'}\n"
               f"━━━━━━━━━━━━━━━━━━━━━━\n"
               f"📋 শেষ ৫টা অর্ডার:\n")
        for o in user_orders[-5:]:
            msg += f"• {o['service']} × {o['qty']} = {o['cost']:.2f} TK\n"
        await update.message.reply_text(msg, reply_markup=admin_kb())
    except:
        await update.message.reply_text("❌ সঠিক ID দিন।", reply_markup=admin_kb())
    return ConversationHandler.END

async def refund_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("💸 Refund দিতে User এর Telegram ID লিখুন:", reply_markup=cancel_kb())
    return REF_UID

async def refund_uid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        uid = int(update.message.text)
        if uid not in users:
            await update.message.reply_text("❌ User পাওয়া যায়নি।")
            return REF_UID
        context.user_data["ref_uid"] = uid
        u = users[uid]
        await update.message.reply_text(
            f"👤 {u['name']}\n💳 ব্যালেন্স: {u['balance']:.2f} TK\n\nকত টাকা দেবেন?",
            reply_markup=cancel_kb()
        )
        return REF_AMT
    except:
        await update.message.reply_text("❌ সঠিক ID দিন।")
        return REF_UID

async def refund_amt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        amount = float(update.message.text)
        uid = context.user_data.get("ref_uid")
        u = get_user(uid)
        u["balance"] += amount
        save_data()
        await update.message.reply_text(
            f"✅ Refund সফল!\n👤 {u['name']} কে {amount:.0f} TK দেওয়া হয়েছে!\n💳 নতুন ব্যালেন্স: {u['balance']:.2f} TK",
            reply_markup=admin_kb()
        )
        try:
            await context.bot.send_message(uid, f"💰 {amount:.0f} TK আপনার একাউন্টে যোগ হয়েছে!\n💳 ব্যালেন্স: {u['balance']:.2f} TK")
        except:
            pass
    except:
        await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
        return REF_AMT
    return ConversationHandler.END

async def admin_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text(
        "🛒 Admin Order\n━━━━━━━━━━━━━━━━━━━━━━\nUser এর Telegram ID লিখুন:",
        reply_markup=cancel_kb()
    )
    return AO_UID

async def ao_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        uid = int(update.message.text)
        if uid not in users:
            await update.message.reply_text("❌ User পাওয়া যায়নি।")
            return AO_UID
        context.user_data["ao_uid"] = uid
        u = users[uid]
        msg = f"👤 {u['name']} | 💳 {u['balance']:.2f} TK\n\n📋 Service নাম লিখুন:\n\n"
        for pv in SERVICES.values():
            if pv["active"]:
                msg += f"{pv['name']}:\n"
                for sk, sv in pv["list"].items():
                    if sv["active"]:
                        msg += f"  • {sv['name']} = {get_price(sk)} TK\n"
                msg += "\n"
        await update.message.reply_text(msg, reply_markup=cancel_kb())
        return AO_SVC
    except:
        await update.message.reply_text("❌ সঠিক ID দিন।")
        return AO_UID

async def ao_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    text = update.message.text.strip()
    found = None
    fkey = None
    for pv in SERVICES.values():
        for sk, sv in pv["list"].items():
            if sv["name"].lower() == text.lower():
                found = sv
                fkey = sk
                break
        if found:
            break
    if not found:
        await update.message.reply_text("❌ Service পাওয়া যায়নি!\nসঠিক নাম লিখুন।")
        return AO_SVC
    context.user_data["ao_skey"] = fkey
    context.user_data["ao_sdata"] = found
    await update.message.reply_text(
        f"✅ {found['name']}\n💰 {get_price(fkey)} TK/1000\nপরিমাণ লিখুন:",
        reply_markup=cancel_kb()
    )
    return AO_QTY

async def ao_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        qty = int(update.message.text)
        sdata = context.user_data["ao_sdata"]
        if qty < sdata["min"]:
            await update.message.reply_text(f"❌ সর্বনিম্ন {sdata['min']} টি!")
            return AO_QTY
        context.user_data["ao_qty"] = qty
        await update.message.reply_text("🔗 লিংক দিন:", reply_markup=cancel_kb())
        return AO_LINK
    except:
        await update.message.reply_text("❌ সঠিক সংখ্যা দিন।")
        return AO_QTY

async def ao_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    link = update.message.text
    uid = context.user_data["ao_uid"]
    skey = context.user_data["ao_skey"]
    sdata = context.user_data["ao_sdata"]
    qty = context.user_data["ao_qty"]
    u = get_user(uid)
    price = get_price(skey)
    cost = round((qty / 1000) * price, 2)
    u["balance"] -= cost
    success, result = await process_order(context, uid, sdata, skey, qty, link)
    if success:
        await update.message.reply_text(
            f"✅ অর্ডার দেওয়া হয়েছে!\n👤 {u['name']}\n📦 {sdata['name']}\n🔢 {qty}\n💰 {cost:.2f} TK",
            reply_markup=admin_kb()
        )
        try:
            await context.bot.send_message(uid, f"✅ আপনার অর্ডার দেওয়া হয়েছে!\n📦 {sdata['name']} × {qty}\n✅ Processing")
        except:
            pass
    else:
        u["balance"] += cost
        await update.message.reply_text(result, reply_markup=admin_kb())
    return ConversationHandler.END

async def toggle_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_on
    if update.effective_user.id != ADMIN_ID:
        return
    bot_on = not bot_on
    save_data()
    await update.message.reply_text(f"🤖 বট {'✅ চালু' if bot_on else '❌ বন্ধ'} করা হয়েছে!", reply_markup=admin_kb())

async def price_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        pct = float(context.args[0])
    except:
        await update.message.reply_text("❌ /price_up 20\n(সব দাম 20% বাড়াবে)")
        return
    msg = f"✅ সব দাম {pct}% বাড়ানো হয়েছে!\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for pk, pv in SERVICES.items():
        msg += f"{pv['name']}:\n"
        for sk, sv in pv["list"].items():
            old = get_price(sk)
            new = round(old * (1 + pct/100), 2)
            SERVICES[pk]["list"][sk]["price"] = new
            msg += f"• {sv['name']}: {old} → {new} TK 📈\n"
        msg += "\n"
    save_data()
    await update.message.reply_text(msg, reply_markup=admin_kb())

async def price_down(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        pct = float(context.args[0])
    except:
        await update.message.reply_text("❌ /price_down 10\n(সব দাম 10% কমাবে)")
        return
    msg = f"✅ সব দাম {pct}% কমানো হয়েছে!\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for pk, pv in SERVICES.items():
        msg += f"{pv['name']}:\n"
        for sk, sv in pv["list"].items():
            old = get_price(sk)
            new = round(old * (1 - pct/100), 2)
            SERVICES[pk]["list"][sk]["price"] = new
            msg += f"• {sv['name']}: {old} → {new} TK 📉\n"
        msg += "\n"
    save_data()
    await update.message.reply_text(msg, reply_markup=admin_kb())

async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    td = today_stats.get(today, {"orders":0,"revenue":0,"cost":0,"profit":0})
    await update.message.reply_text(
        f"📅 আজকের রিপোর্ট ({today})\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 {td['orders']} অর্ডার\n💰 বিক্রি: {td['revenue']:.2f} TK\n"
        f"💸 খরচ: {td['cost']:.2f} TK\n🏆 লাভ: {td['profit']:.2f} TK",
        reply_markup=admin_kb()
    )

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = ("📋 PRICE LIST SET\n━━━━━━━━━━━━━━━━━━━━━━\n"
           "ফরম্যাট: service_নাম=নতুন_দাম\n\n"
           "উদাহরণ:\nটেলিগ্রাম ১K মেম্বার (Drop হতে পারে)=50\nটিকটক ১K Like=40\n\n"
           "বর্তমান দাম:\n")
    for pv in SERVICES.values():
        for sk, sv in pv["list"].items():
            msg += f"• {sv['name']} = {get_price(sk)} TK\n"
    msg += "\nনতুন list পাঠান:"
    await update.message.reply_text(msg, reply_markup=cancel_kb())
    return SET_LIST

async def set_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    lines = update.message.text.strip().split("\n")
    updated = []
    for line in lines:
        if "=" in line:
            name, val = line.rsplit("=", 1)
            name = name.strip()
            try:
                price = float(val.strip())
                for pk, pv in SERVICES.items():
                    for sk, sv in pv["list"].items():
                        if sv["name"].lower() == name.lower():
                            SERVICES[pk]["list"][sk]["price"] = price
                            updated.append(f"✅ {sv['name']}: {price} TK")
            except:
                pass
    save_data()
    if updated:
        await update.message.reply_text("✅ আপডেট!\n" + "\n".join(updated), reply_markup=admin_kb())
    else:
        await update.message.reply_text("❌ সঠিক ফরম্যাটে দিন।")
    return ConversationHandler.END

async def toggle_svc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        key = context.args[0]
        for pk, pv in SERVICES.items():
            if key in pv["list"]:
                current = pv["list"][key]["active"]
                SERVICES[pk]["list"][key]["active"] = not current
                await update.message.reply_text(f"{'✅ চালু' if not current else '❌ বন্ধ'}: {pv['list'][key]['name']}")
                return
        await update.message.reply_text("❌ Key পাওয়া যায়নি।\nযেমন: /toggle_svc tg1")
    except:
        await update.message.reply_text("❌ /toggle_svc tg1")

async def toggle_platform_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        key = context.args[0]
        if key in SERVICES:
            current = SERVICES[key]["active"]
            SERVICES[key]["active"] = not current
            await update.message.reply_text(f"{'✅ চালু' if not current else '❌ বন্ধ'}: {SERVICES[key]['name']}")
        else:
            await update.message.reply_text("❌ Keys: telegram, tiktok, youtube, instagram, facebook, twitter")
    except:
        await update.message.reply_text("❌ /toggle_platform telegram")

async def protect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⏳ Auto price protection চালাচ্ছি...")
    updated = auto_protect()
    save_data()
    if updated:
        await update.message.reply_text("✅ দাম আপডেট!\n" + "\n".join(updated), reply_markup=admin_kb())
    else:
        await update.message.reply_text("✅ সব দাম ঠিক আছে।", reply_markup=admin_kb())

async def service_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        query = update.message.text.split("=", 1)[1].strip()
        sid, rate, name = find_by_name(query)
        if not sid:
            await update.message.reply_text(f"❌ '{query}' পাওয়া যায়নি।")
            return
        bdt = round(rate * 110, 2)
        context.user_data["custom_sid"] = sid
        context.user_data["custom_name"] = name
        context.user_data["custom_rate"] = rate
        await update.message.reply_text(
            f"✅ পাওয়া গেছে!\n📦 {name}\n💰 {bdt} TK/1000\n\nফরম্যাট: পরিমাণ লিংক\nযেমন: 1000 https://t.me/ch",
            reply_markup=cancel_kb()
        )
        return CUSTOM_SVC
    except:
        await update.message.reply_text("❌ /service=telegram member")

async def custom_svc_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        parts = update.message.text.split(" ", 1)
        qty = int(parts[0])
        link = parts[1].strip()
        sid = context.user_data["custom_sid"]
        name = context.user_data["custom_name"]
        rate = context.user_data["custom_rate"]
        place_order(sid, link, qty)
        cost = round((qty / 1000) * rate * 110, 2)
        await update.message.reply_text(
            f"✅ Custom Order!\n📦 {name}\n🔢 {qty}\n💰 {cost:.2f} TK\n✅ Processing",
            reply_markup=admin_kb()
        )
    except:
        await update.message.reply_text("❌ ফরম্যাট: পরিমাণ লিংক\nযেমন: 1000 https://t.me/ch")
        return CUSTOM_SVC
    return ConversationHandler.END

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("📢 মেসেজ লিখুন:", reply_markup=cancel_kb())
    return BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    msg = update.message.text
    ok = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 Admin:\n\n{msg}")
            ok += 1
        except:
            pass
    await update.message.reply_text(f"✅ {ok}/{len(users)} জনকে পাঠানো হয়েছে।", reply_markup=admin_kb())
    return ConversationHandler.END

async def fail_order_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    parts = query.data.split("_")
    action = parts[0]
    uid = int(parts[1])
    amount = float(parts[2])
    u = get_user(uid)
    if action == "failrefund":
        u["balance"] += amount
        save_data()
        txt = (query.message.text or "") + f"\n\n✅ Refund দেওয়া হয়েছে — {amount:.2f} TK!"
        await query.message.edit_text(txt)
        try:
            await context.bot.send_message(uid,
                f"💰 আপনার অর্ডারটি সম্পন্ন হয়নি।\n"
                f"দুঃখিত এই সমস্যার জন্য! 🙏\n\n"
                f"✅ {amount:.2f} TK আপনার ব্যালেন্সে ফেরত দেওয়া হয়েছে।\n"
                f"💳 নতুন ব্যালেন্স: {u['balance']:.2f} TK\n\n"
                f"সমস্যা হলে Support এ যোগাযোগ করুন।"
            )
        except:
            pass
    elif action == "failretry":
        txt = (query.message.text or "") + "\n\n⏳ Retry হবে — কাস্টমারকে জানানো হয়েছে।"
        await query.message.edit_text(txt)
        try:
            await context.bot.send_message(uid,
                f"⏳ আপনার অর্ডার প্রক্রিয়াধীন আছে।\n"
                f"একটু বেশি সময় লাগতে পারে।\n"
                f"সমস্যা হলে Support এ যোগাযোগ করুন।"
            )
        except:
            pass

# ===== FEATURE 1: AUTO BALANCE LOW ALERT (90% spent) =====
async def check_balance_alert(context):
    """প্রতি ৩০ মিনিটে Peakerr ব্যালেন্স চেক করো"""
    try:
        usd, bdt = get_peakerr_balance()
        # ধরে নিচ্ছি সর্বোচ্চ ব্যালেন্স ৫০০ USD (ট্র্যাক করো)
        # ৯০% কমলে মানে মাত্র ১০% বাকি = $50 এর কম
        threshold_usd = 50  # আপনি চাইলে পরিবর্তন করো
        if usd < threshold_usd:
            await context.bot.send_message(ADMIN_ID,
                f"⚠️ LOW BALANCE ALERT! ⚠️\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 Peakerr ব্যালেন্স অনেক কম!\n"
                f"💵 বর্তমান: ${usd:.2f} = {bdt:.2f} TK\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ দ্রুত Peakerr ব্যালেন্স রিচার্জ করুন!\n"
                f"🔗 https://peakerr.com"
            )
    except Exception as e:
        print(f"[Balance Alert Error] {e}")

# ===== FEATURE 2: REALTIME PEAKERR BALANCE BUTTON =====
async def peakerr_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⏳ Real-time balance আনছি...")
    usd, bdt = get_peakerr_balance()
    await update.message.reply_text(
        f"💎 PEAKERR REAL-TIME BALANCE\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 USD: ${usd:.4f}\n"
        f"💰 BDT: {bdt:.2f} টাকা\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 আপডেট: {datetime.now().strftime('%H:%M:%S')}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")
        ]])
    )

async def refresh_balance_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ আপডেট হচ্ছে...")
    if query.from_user.id != ADMIN_ID:
        return
    usd, bdt = get_peakerr_balance()
    await query.message.edit_text(
        f"💎 PEAKERR REAL-TIME BALANCE\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 USD: ${usd:.4f}\n"
        f"💰 BDT: {bdt:.2f} টাকা\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 আপডেট: {datetime.now().strftime('%H:%M:%S')}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")
        ]])
    )

# ===== FEATURE 3: ALL USERS LIST =====
async def all_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not users:
        await update.message.reply_text("❌ কোনো ইউজার নেই।", reply_markup=admin_kb())
        return
    msg = f"👥 সব ইউজার লিস্ট ({len(users)} জন)\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    count = 0
    for uid, u in list(users.items())[-50:]:  # শেষ ৫০ জন
        status = "🚫" if is_blocked(uid) else "✅"
        msg += f"{status} {u['name']} | ID: {uid}\n"
        count += 1
    if len(users) > 50:
        msg += f"\n... এবং আরও {len(users)-50} জন"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n📊 মোট: {len(users)} জন"
    await update.message.reply_text(msg, reply_markup=admin_kb())

# ===== FEATURE 4: DAILY REPORT AT MIDNIGHT =====
async def daily_midnight_report(context):
    """প্রতিদিন রাত ১২টায় দৈনিক রিপোর্ট পাঠাও"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        td = today_stats.get(today, {"orders":0,"revenue":0,"cost":0,"profit":0})
        usd, bdt = get_peakerr_balance()
        await context.bot.send_message(ADMIN_ID,
            f"📊 দৈনিক রিপোর্ট 📊\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 তারিখ: {today}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 মোট অর্ডার: {td['orders']} টি\n"
            f"💰 মোট বিক্রি: {td['revenue']:.2f} TK\n"
            f"💸 Peakerr খরচ: {td['cost']:.2f} TK\n"
            f"🏆 নিট লাভ: {td['profit']:.2f} TK\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 Peakerr Balance: ${usd:.2f} = {bdt:.2f} TK\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌙 শুভরাত্রি! 😊"
        )
    except Exception as e:
        print(f"[Daily Report Error] {e}")

# ===== FEATURE 5: AUTO 5% DISCOUNT EVERY 5 DAYS =====
async def auto_discount_sender(context):
    """প্রতি ১ ঘণ্টায় চেক করো — কেউ ৫ দিন পূর্ণ করলে ডিসকাউন্ট পাঠাও"""
    try:
        now = datetime.now()
        for uid, u in users.items():
            joined_str = u.get("joined")
            if not joined_str:
                continue
            joined_dt = datetime.fromisoformat(joined_str)
            days_since_join = (now - joined_dt).days
            last_sent = u.get("last_discount_sent")

            # ৫ দিনের মাল্টিপল চেক (৫, ১০, ১৫ দিন = ৩ বার)
            for round_num in range(1, 4):  # 1, 2, 3 round
                target_day = round_num * 5
                if days_since_join >= target_day:
                    sent_key = f"disc_round_{round_num}"
                    if not u.get(sent_key):
                        # এই রাউন্ডের ডিসকাউন্ট এখনো পাঠানো হয়নি
                        disc_pct = 5
                        disc_expires = now + timedelta(days=1)
                        user_discounts[uid] = {"pct": disc_pct, "expires": disc_expires}
                        u[sent_key] = True
                        save_data()
                        try:
                            await context.bot.send_message(uid,
                                f"🎉 বিশেষ অফার! 🎉\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🎁 আপনি {disc_pct}% ডিসকাউন্ট পেয়েছেন!\n\n"
                                f"⚡ শুধুমাত্র ২৪ ঘণ্টার জন্য!\n"
                                f"তাড়াতাড়ি আমাদের সার্ভিস কিনুন!\n\n"
                                f"🛒 এখনই অর্ডার করতে /start চাপুন",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("🛒 এখনই কিনুন!", callback_data="go_buy")
                                ]])
                            )
                        except:
                            pass
                        break  # একটাই পাঠাই একবারে
    except Exception as e:
        print(f"[Auto Discount Error] {e}")

async def go_buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await buy_service(query, context)

# ===== FEATURE 7: ADMIN DISCOUNT CODE CREATION =====
async def admin_discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text(
        "🎟️ নতুন Discount Code বানাও\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "কত % ডিসকাউন্ট দিতে চাও?\n"
        "(শুধু সংখ্যা, যেমন: 10 মানে 10%)",
        reply_markup=cancel_kb()
    )
    return DISC_CODE_PCT

async def disc_code_pct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        pct = float(update.message.text.strip())
        if pct <= 0 or pct > 100:
            raise ValueError
        context.user_data["new_disc_pct"] = pct
        await update.message.reply_text(
            f"✅ {pct}% ডিসকাউন্ট সেট!\n\n"
            f"এখন কোড কি দিতে চাও?\n"
            f"(ইংরেজি, যেমন: SUMMER2025)\n"
            f"অথবা লেখো AUTO — অটো কোড তৈরি হবে)",
            reply_markup=cancel_kb()
        )
        return DISC_CODE_NAME
    except:
        await update.message.reply_text("❌ সঠিক সংখ্যা দিন (1-100):")
        return DISC_CODE_PCT

async def disc_code_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    text = update.message.text.strip().upper()
    if text == "AUTO":
        code = "DISC" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    else:
        code = text.replace(" ", "")
    context.user_data["new_disc_code"] = code
    await update.message.reply_text(
        f"✅ কোড: {code}\n\n"
        f"এই কোড কতদিন কাজ করবে?\n"
        f"(শুধু সংখ্যা লিখুন, যেমন: 7 মানে ৭ দিন)",
        reply_markup=cancel_kb()
    )
    return DISC_CODE_DAYS

async def disc_code_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        await update.message.reply_text("বাতিল।", reply_markup=admin_kb())
        return ConversationHandler.END
    try:
        days = int(update.message.text.strip())
        if days <= 0 or days > 365:
            raise ValueError
        pct = context.user_data["new_disc_pct"]
        code = context.user_data["new_disc_code"]
        expires = datetime.now() + timedelta(days=days)
        discount_codes[code] = {
            "pct": pct,
            "days": days,
            "expires": expires,
            "used_by": []
        }
        save_data()
        await update.message.reply_text(
            f"✅ Discount Code তৈরি হয়েছে!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎟️ কোড: {code}\n"
            f"💰 ডিসকাউন্ট: {pct}%\n"
            f"📅 মেয়াদ: {days} দিন ({expires.strftime('%Y-%m-%d')} পর্যন্ত)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"এই কোড ইউজারদের দিন!",
            reply_markup=admin_kb()
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ সঠিক সংখ্যা দিন (1-365):")
        return DISC_CODE_DAYS

# ===== FEATURE 7: USER DISCOUNT CODE =====
async def user_discount_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    disc = user_discounts.get(uid)
    active_info = ""
    if disc and disc["expires"] and datetime.now() < disc["expires"]:
        remaining = disc["expires"] - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        active_info = f"\n✅ বর্তমান ডিসকাউন্ট: {disc['pct']}% OFF ({hours} ঘণ্টা বাকি)\n"
    await update.message.reply_text(
        f"🎟️ ডিসকাউন্ট কোড\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{active_info}\n"
        f"আপনার কাছে কোনো Discount Code থাকলে\n"
        f"নিচের বাটন চেপে কোড দিন:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎟️ কোড ব্যবহার করুন", callback_data="use_disc_code")
        ]])
    )

async def use_disc_code_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🎟️ আপনার Discount Code লিখুন:",
        reply_markup=cancel_kb()
    )
    context.user_data["expecting_disc_code"] = True
    return DISC_USE

async def disc_use_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ বাতিল করুন":
        context.user_data.pop("expecting_disc_code", None)
        await update.message.reply_text("বাতিল।", reply_markup=main_kb())
        return ConversationHandler.END
    code = update.message.text.strip().upper()
    uid = update.effective_user.id
    if code not in discount_codes:
        await update.message.reply_text(
            "❌ এই কোডটি বৈধ নয়!\nসঠিক কোড দিন।",
            reply_markup=main_kb()
        )
        return ConversationHandler.END
    dc = discount_codes[code]
    if dc["expires"] and datetime.now() > dc["expires"]:
        await update.message.reply_text(
            "❌ এই কোডটির মেয়াদ শেষ হয়ে গেছে!",
            reply_markup=main_kb()
        )
        return ConversationHandler.END
    if uid in dc["used_by"]:
        await update.message.reply_text(
            "❌ আপনি এই কোড আগেই ব্যবহার করেছেন!",
            reply_markup=main_kb()
        )
        return ConversationHandler.END
    # Apply discount
    disc_expires = datetime.now() + timedelta(hours=24)
    user_discounts[uid] = {"pct": dc["pct"], "expires": disc_expires}
    dc["used_by"].append(uid)
    save_data()
    await update.message.reply_text(
        f"🎉 ডিসকাউন্ট সক্রিয় হয়েছে!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎟️ কোড: {code}\n"
        f"💰 ডিসকাউন্ট: {dc['pct']}% OFF\n"
        f"⏰ মেয়াদ: ২৪ ঘণ্টা\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 এখনই সার্ভিস কিনুন!",
        reply_markup=main_kb()
    )
    return ConversationHandler.END

# ===== HANDLE TEXT =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    if text == "📋 সার্ভিস প্রাইস":
        await service_price(update, context)
    elif text == "👤 আমার প্রোফাইল":
        await my_profile(update, context)
    elif text == "📞 সাপোর্ট":
        await support(update, context)
    elif text == "🎟️ ডিসকাউন্ট কোড":
        await user_discount_menu(update, context)
    elif text == "📊 Statistics" and uid == ADMIN_ID:
        await admin_stats(update, context)
    elif text == "💹 My Profit" and uid == ADMIN_ID:
        await my_profit(update, context)
    elif text == "💰 SMM Prices" and uid == ADMIN_ID:
        await smm_prices(update, context)
    elif text == "📋 All Commands" and uid == ADMIN_ID:
        await all_commands(update, context)
    elif text == "⚙️ Payment Settings" and uid == ADMIN_ID:
        await payment_settings(update, context)
    elif text in ["🔴 Bot OFF","🟢 Bot ON"] and uid == ADMIN_ID:
        await toggle_bot(update, context)
    elif text == "💎 Peakerr Balance" and uid == ADMIN_ID:
        await peakerr_balance_cmd(update, context)
    elif text == "👥 সব ইউজার লিস্ট" and uid == ADMIN_ID:
        await all_users_list(update, context)
    elif text == "🎟️ Discount Code বানাও" and uid == ADMIN_ID:
        # Trigger discount conversation
        await admin_discount_start(update, context)
    elif text in ["🔙 Main Menu","🔙 মেইন মেনু","মেইন মেনু"]:
        await start(update, context)
    elif text.startswith("/service=") and uid == ADMIN_ID:
        await service_cmd(update, context)

def main():
    # ডেটা লোড করো
    load_data()

    app = Application.builder().token(BOT_TOKEN).build()

    cancel_filter = filters.Regex("^❌ বাতিল করুন$")

    buy_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🟢 সার্ভিস কিনুন$"), buy_service)],
        states={
            S_PLATFORM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_platform)],
            S_SERVICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, select_service)],
            S_QTY:      [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_qty)],
            S_LINK:     [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_link)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    dep_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 ডিপোজিট করুন$"), deposit)],
        states={
            D_AMOUNT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_amount)],
            D_METHOD:     [CallbackQueryHandler(pay_method_cb, pattern="^pay_")],
            D_TRXID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, dep_trxid)],
            D_SCREENSHOT: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, dep_screenshot)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    bc_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Broadcast$"), broadcast_start)],
        states={BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    block_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚫 Block User$"), block_start)],
        states={
            BLOCK_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, block_id_handler)],
            BLOCK_DAYS: [CallbackQueryHandler(block_days_cb, pattern="^blk_")],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pay_settings_cb, pattern="^ch_")],
        states={
            CH_BKASH:   [MessageHandler(filters.TEXT & ~filters.COMMAND, change_payment)],
            CH_NAGAD:   [MessageHandler(filters.TEXT & ~filters.COMMAND, change_payment)],
            CH_BINANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_payment)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    list_conv = ConversationHandler(
        entry_points=[CommandHandler("list", list_cmd)],
        states={SET_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_list)]},
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    check_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👤 Check User$"), check_user)],
        states={CHK_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_user_id)]},
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    refund_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Refund User$"), refund_start)],
        states={
            REF_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, refund_uid_handler)],
            REF_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, refund_amt_handler)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    ao_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 Admin Order$"), admin_order_start)],
        states={
            AO_UID:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ao_uid)],
            AO_SVC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ao_svc)],
            AO_QTY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ao_qty)],
            AO_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ao_link)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    custom_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^/service="), service_cmd)],
        states={CUSTOM_SVC: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_svc_order)]},
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    # Feature 7: Admin Discount Code creation conversation
    disc_admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎟️ Discount Code বানাও$"), admin_discount_start)],
        states={
            DISC_CODE_PCT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, disc_code_pct)],
            DISC_CODE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, disc_code_name)],
            DISC_CODE_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, disc_code_days)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )
    # Feature 7: User applying discount code
    disc_use_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(use_disc_code_cb, pattern="^use_disc_code$")],
        states={
            DISC_USE: [MessageHandler(filters.TEXT & ~filters.COMMAND, disc_use_handler)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(cancel_filter, cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price_up", price_up))
    app.add_handler(CommandHandler("price_down", price_down))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("toggle_svc", toggle_svc_cmd))
    app.add_handler(CommandHandler("toggle_platform", toggle_platform_cmd))
    app.add_handler(CommandHandler("protect", protect_cmd))
    app.add_handler(buy_conv)
    app.add_handler(dep_conv)
    app.add_handler(bc_conv)
    app.add_handler(block_conv)
    app.add_handler(pay_conv)
    app.add_handler(list_conv)
    app.add_handler(check_conv)
    app.add_handler(refund_conv)
    app.add_handler(ao_conv)
    app.add_handler(custom_conv)
    app.add_handler(disc_admin_conv)
    app.add_handler(disc_use_conv)
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(approve_cb, pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(pay_settings_cb, pattern="^tog_"))
    app.add_handler(CallbackQueryHandler(fail_order_cb, pattern="^(failrefund|failretry)_"))
    app.add_handler(CallbackQueryHandler(refresh_balance_cb, pattern="^refresh_balance$"))
    app.add_handler(CallbackQueryHandler(go_buy_cb, pattern="^go_buy$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ===== SCHEDULED JOBS =====
    jq = app.job_queue

    # Feature 1: Balance low alert — প্রতি ৩০ মিনিটে চেক
    jq.run_repeating(check_balance_alert, interval=1800, first=60)

    # Feature 4: Daily midnight report — প্রতিদিন রাত ১২:০০ AM
    jq.run_daily(daily_midnight_report, time=datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0).time())

    # Feature 5: Auto discount sender — প্রতি ঘণ্টায় চেক করো
    jq.run_repeating(auto_discount_sender, interval=3600, first=120)

    print("✅ Bot চালু হয়েছে! সব ৭টি ফিচার সক্রিয়!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
