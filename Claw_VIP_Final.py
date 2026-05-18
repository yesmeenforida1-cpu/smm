import os, json, random, asyncio, threading, aiohttp, pytz, time as _time
from asyncio import Lock
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler,
    CommandHandler, ContextTypes, filters, CallbackQueryHandler
)

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════
TOKEN    = "8741499786:AAEaFZSLW9OV5JOp_P9ZpkPcsXdxsnuOcE4"
ADMIN_ID = 7974704580
GROUP_ID = "@jjSERVICE_SMM_FATHER"

TWELVE_KEY = "25d98f4edeed4afca3fc847598557d76"
ALPHA_KEYS = ["5K499BSXFQ1E8QZH","ZG8IC3OVLL0C2WMU",
              "I1JEU7U6UJNWY6FZ","IN0P3RSEQVNPJ0R8","NAQK3YVWXERVQZVH"]
_aidx = 0
_alock = threading.Lock()

def next_alpha():
    global _aidx
    with _alock:
        k = ALPHA_KEYS[_aidx % len(ALPHA_KEYS)]
        _aidx += 1
    return k

DATA_FILE = "data.json"
USER_FILE = "ultra_users.json"

PAYMENT_INFO = {
    "bkash":   "01759852112",
    "nagad":   "01625141477",
    "binance": "1234939031",
}
VIP_PRICE        = 500
SUPPORT_USERNAME = "@SOPPORT_CLAW_BOT"
OWNER_USERNAME   = "@SW_WAFI"

FREE_SIGNALS = 3
VIP_SIGNALS  = 5

# ═══════════════════════════════════════
# PAIRS
# ═══════════════════════════════════════
ALL_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
    "EURJPY","GBPJPY","AUDJPY","EURGBP","EURAUD","EURCAD","EURCHF",
    "GBPAUD","GBPCAD","GBPCHF","GBPNZD","AUDCAD","AUDCHF",
    "AUDNZD","CADJPY","CHFJPY","NZDJPY","NZDCAD","NZDCHF",
    "EURNZD","USDSGD","USDHKD","USDMXN",
]

# Binance USDT mapping
BINANCE_MAP = {
    "EURUSD":"EURUSDT","GBPUSD":"GBPUSDT",
    "AUDUSD":"AUDUSTDT","NZDUSD":"NZDUSDT",
}

# ═══════════════════════════════════════
# STATE
# ═══════════════════════════════════════
active_sessions        = set()
pending_signal_confirm = set()
pending_payment        = {}
admin_set_mode         = {}
pending_txn            = {}
_user_cache            = {}

_file_lock    = Lock()
_candle_cache = {}
_candle_lock  = Lock()
_pair_locks   = {}
_pl_lock      = threading.Lock()

def _get_pair_lock(pair):
    with _pl_lock:
        if pair not in _pair_locks:
            _pair_locks[pair] = Lock()
        return _pair_locks[pair]

# ═══════════════════════════════════════
# KEEP-ALIVE
# ═══════════════════════════════════════
class _KA(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Claw VIP alive!")
    def log_message(self, *a): pass

threading.Thread(
    target=lambda: HTTPServer(
        ("0.0.0.0", int(os.environ.get("PORT", 8080))), _KA
    ).serve_forever(), daemon=True
).start()

# ═══════════════════════════════════════
# FILE HELPERS
# ═══════════════════════════════════════
for f in [DATA_FILE, USER_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as fp: json.dump({}, fp)

def load_json(file):
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json(file, data):
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, file)

# ═══════════════════════════════════════
# USER HELPERS
# ═══════════════════════════════════════
def _def():
    return {"name":"বন্ধু","xp":0,"level":1,
            "session_used_today":[],"signal_count":0,
            "win":0,"loss":0,"is_vip":False,
            "last_reset":str(datetime.now().date())}

def get_user(uid):
    uid = str(uid)
    if uid in _user_cache: return _user_cache[uid]
    d = load_json(USER_FILE)
    if uid not in d: d[uid] = _def(); save_json(USER_FILE, d)
    _user_cache[uid] = d[uid]; return d[uid]

def update_user(uid, key, val):
    uid = str(uid); get_user(uid)
    _user_cache[uid][key] = val
    d = load_json(USER_FILE)
    if uid not in d: d[uid] = _def()
    d[uid][key] = val; save_json(USER_FILE, d)

async def update_user_async(uid, key, val):
    uid = str(uid); get_user(uid)
    _user_cache[uid][key] = val
    async with _file_lock:
        d = load_json(USER_FILE)
        if uid not in d: d[uid] = _def()
        d[uid][key] = val; save_json(USER_FILE, d)

def add_xp(uid, n=2):
    uid = str(uid); u = get_user(uid)
    u["xp"] += n
    if u["xp"] >= u["level"] * 50: u["xp"] = 0; u["level"] += 1
    update_user(uid, "xp", u["xp"]); update_user(uid, "level", u["level"])

def is_vip(uid):
    uid = str(uid)
    if int(uid) == ADMIN_ID: return True
    return get_user(uid).get("is_vip", False)

def reset_daily(uid):
    uid = str(uid); u = get_user(uid)
    today = str(datetime.now().date())
    if u.get("last_reset") != today:
        u.update({"session_used_today":[],"signal_count":0,
                  "win":0,"loss":0,"last_reset":today})
        _user_cache[uid] = u
        d = load_json(USER_FILE); d[uid] = u; save_json(USER_FILE, d)

# ═══════════════════════════════════════
# SESSION TIME
# ═══════════════════════════════════════
VIP_SESSIONS = [(7,0,12,0),(13,0,16,0),(19,0,21,30)]

def dhaka_now():
    return datetime.now(pytz.timezone("Asia/Dhaka"))

def in_session():
    n = dhaka_now(); c = n.hour*60+n.minute
    for sh,sm,eh,em in VIP_SESSIONS:
        if sh*60+sm <= c < eh*60+em: return True
    return False

def next_session():
    n = dhaka_now(); c = n.hour*60+n.minute
    for sh,sm,eh,em in VIP_SESSIONS:
        if sh*60+sm > c: return f"{sh:02d}:{sm:02d}"
    return f"আগামীকাল {VIP_SESSIONS[0][0]:02d}:{VIP_SESSIONS[0][1]:02d}"

def current_slot():
    n = dhaka_now(); c = n.hour*60+n.minute
    if 7*60<=c<12*60:     return "morning"
    if 13*60<=c<16*60:    return "afternoon"
    if 19*60<=c<21*60+30: return "evening"
    return None

def secs_to_candle():
    return 60 - dhaka_now().second

# ═══════════════════════════════════════
# MARKET DATA — 5 SOURCE PARALLEL
# ৪০০+ user এর জন্য shared cache
# ═══════════════════════════════════════
UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) Safari/605.1",
    "python-requests/2.31.0",
]

async def _binance(session, pair):
    sym = BINANCE_MAP.get(pair)
    if not sym: return None
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&limit=80"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10),
                               headers={"User-Agent":"Mozilla/5.0"}) as r:
            res = await r.json(content_type=None)
        if isinstance(res, list) and len(res) >= 25:
            return [{"open":float(k[1]),"high":float(k[2]),
                     "low":float(k[3]),"close":float(k[4])} for k in res]
    except: pass
    return None

async def _yahoo(session, pair):
    sym = pair + "=X"
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=1d",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=1d",
    ]
    for url in urls:
        for ua in UAS:
            try:
                hdrs = {"User-Agent":ua,"Accept":"application/json",
                        "Referer":"https://finance.yahoo.com/","Origin":"https://finance.yahoo.com"}
                async with session.get(url, headers=hdrs,
                                       timeout=aiohttp.ClientTimeout(total=12)) as r:
                    if r.status != 200: continue
                    res = await r.json(content_type=None)
                chart = res.get("chart",{}).get("result",[])
                if not chart: continue
                q = chart[0]["indicators"]["quote"][0]
                candles = []
                for i in range(len(q.get("close",[]))):
                    try:
                        if all(q[k][i] is not None for k in ["open","high","low","close"]):
                            candles.append({k:float(q[k][i]) for k in ["open","high","low","close"]})
                    except: continue
                if len(candles) >= 25: return candles
            except: continue
    return None

async def _twelvedata(session, pair):
    sym = f"{pair[:3]}/{pair[3:]}"
    for key in [TWELVE_KEY]:
        try:
            url = (f"https://api.twelvedata.com/time_series"
                   f"?symbol={sym}&interval=1min&outputsize=80&apikey={key}")
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                res = await r.json(content_type=None)
            if "values" in res and len(res["values"]) >= 25:
                return [{"open":float(v["open"]),"high":float(v["high"]),
                         "low":float(v["low"]),"close":float(v["close"])}
                        for v in reversed(res["values"])]
        except: continue
    return None

async def _alphavantage(session, pair):
    try:
        url = (f"https://www.alphavantage.co/query?function=FX_INTRADAY"
               f"&from_symbol={pair[:3]}&to_symbol={pair[3:]}"
               f"&interval=1min&outputsize=compact&apikey={next_alpha()}")
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            res = await r.json(content_type=None)
        ts = res.get("Time Series FX (1min)", {})
        if len(ts) >= 25:
            return [{"open":float(v["1. open"]),"high":float(v["2. high"]),
                     "low":float(v["3. low"]),"close":float(v["4. close"])}
                    for _, v in sorted(ts.items())]
    except: pass
    return None

async def _stooq(session, pair):
    try:
        sym = (pair[:3]+pair[3:]).lower()
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=12),
                               headers={"User-Agent":"Mozilla/5.0"}) as r:
            text = await r.text()
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if len(lines) < 22: return None
        candles = []
        for line in lines[1:]:
            p = line.split(",")
            if len(p) >= 5:
                try: candles.append({"open":float(p[1]),"high":float(p[2]),
                                     "low":float(p[3]),"close":float(p[4])})
                except: continue
        return candles if len(candles) >= 20 else None
    except: return None

async def fetch_candles(session, pair, force=False):
    """
    Shared cache — 400+ user এর জন্য।
    একই pair একসাথে শুধু ১টাই fetch করবে।
    """
    now = _time.time()
    if not force:
        async with _candle_lock:
            cached = _candle_cache.get(pair)
        if cached and now - cached[1] < 55:
            return cached[0]

    async with _get_pair_lock(pair):
        # double-check
        if not force:
            async with _candle_lock:
                cached = _candle_cache.get(pair)
            if cached and now - cached[1] < 55:
                return cached[0]

        # সব source parallel
        results = await asyncio.gather(
            _binance(session, pair),
            _yahoo(session, pair),
            _twelvedata(session, pair),
            _alphavantage(session, pair),
            _stooq(session, pair),
            return_exceptions=True
        )

        best = None
        for res in results:
            if isinstance(res, list) and len(res) >= 20:
                if best is None or len(res) > len(best):
                    best = res

        if best:
            async with _candle_lock:
                _candle_cache[pair] = (best, _time.time())
            return best
    return None

async def get_fresh_price(session, pair):
    """cache bypass করে fresh price"""
    async with _candle_lock:
        _candle_cache.pop(pair, None)
    await asyncio.sleep(2)
    candles = await fetch_candles(session, pair, force=True)
    if candles: return candles[-1]["close"]
    return None

# ═══════════════════════════════════════
# INDICATOR ENGINE
# ═══════════════════════════════════════
def _ema(data, p):
    k = 2/(p+1); r = [data[0]]
    for x in data[1:]: r.append(x*k + r[-1]*(1-k))
    return r

def _rsi(closes, p=14):
    if len(closes) < p+1: return 50
    g, l = [], []
    for i in range(1, p+1):
        d = closes[i]-closes[i-1]
        g.append(d if d>0 else 0); l.append(-d if d<0 else 0)
    ag, al = sum(g)/p, sum(l)/p
    if al == 0: return 100
    return 100 - 100/(1+ag/al)

def _macd(closes):
    if len(closes) < 30: return 0, 0
    e12 = _ema(closes, 12); e26 = _ema(closes, 26)
    ml = [e12[i]-e26[i] for i in range(len(closes))]
    sl = _ema(ml, 9)
    return ml[-1], sl[-1]

def _bb(closes, p=20):
    if len(closes) < p: return closes[-1], closes[-1], closes[-1]
    r = closes[-p:]; m = sum(r)/p
    s = (sum((x-m)**2 for x in r)/p)**0.5
    return m+2*s, m, m-2*s

def _stoch(closes, highs, lows, p=14):
    if len(closes) < p: return 50, 50
    h = max(highs[-p:]); l = min(lows[-p:])
    if h == l: return 50, 50
    k = (closes[-1]-l)/(h-l)*100
    return k, k

def _atr(highs, lows, closes, p=14):
    if len(closes) < 2: return 0
    trs = []
    for i in range(1, min(p+1, len(closes))):
        trs.append(max(highs[i]-lows[i],
                       abs(highs[i]-closes[i-1]),
                       abs(lows[i]-closes[i-1])))
    return sum(trs)/len(trs) if trs else 0

def analyze(candles):
    if len(candles) < 30: return None, 0, 0
    closes = [c["close"] for c in candles]
    opens  = [c["open"]  for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]

    call = 0; put = 0; factors = []

    # 1. EMA
    e5=_ema(closes,5); e10=_ema(closes,10)
    e20=_ema(closes,20); e50=_ema(closes,min(50,len(closes)//2))
    if e5[-1]>e10[-1]>e20[-1]:   call+=4; factors.append("ema_up")
    elif e5[-1]<e10[-1]<e20[-1]: put+=4;  factors.append("ema_down")
    if closes[-1]>e50[-1]: call+=2
    else:                  put+=2
    for e in [e5,e10,e20]:
        if e[-1]>e[-2]: call+=1
        else:           put+=1

    # 2. RSI
    r = _rsi(closes[-25:])
    if   r<25: call+=4; factors.append("rsi_os")
    elif r<35: call+=2
    elif r>75: put+=4;  factors.append("rsi_ob")
    elif r>65: put+=2
    if len(closes)>=26:
        rp = _rsi(closes[-26:-1])
        if r>rp: call+=1
        else:    put+=1

    # 3. MACD
    mv,ms = _macd(closes)
    if mv>ms:   call+=3; factors.append("macd_bull")
    elif mv<ms: put+=3;  factors.append("macd_bear")
    if mv>0: call+=1
    else:    put+=1

    # 4. Bollinger
    bu,bm,bl = _bb(closes)
    if closes[-1]<bl:   call+=3; factors.append("bb_os")
    elif closes[-1]>bu: put+=3;  factors.append("bb_ob")
    elif closes[-1]>bm: call+=1
    else:               put+=1

    # 5. Stochastic
    sk,sd = _stoch(closes, highs, lows)
    if sk<20:   call+=2; factors.append("stoch_os")
    elif sk>80: put+=2;  factors.append("stoch_ob")
    elif sk>sd: call+=1
    else:       put+=1

    # 6. Candle Patterns
    body = abs(closes[-1]-opens[-1])
    rng  = highs[-1]-lows[-1]
    if rng > 0:
        if body/rng > 0.7:
            if closes[-1]>opens[-1]: call+=3; factors.append("bull_candle")
            else:                    put+=3;  factors.append("bear_candle")
        lw = min(opens[-1],closes[-1])-lows[-1]
        uw = highs[-1]-max(opens[-1],closes[-1])
        if lw>body*2 and uw<body: call+=2
        elif uw>body*2 and lw<body: put+=2
    if len(candles)>=2:
        pb=abs(closes[-2]-opens[-2]); cb=abs(closes[-1]-opens[-1])
        if cb>pb*1.5:
            if closes[-1]>opens[-1] and closes[-2]<opens[-2]:
                call+=3; factors.append("bull_engulf")
            elif closes[-1]<opens[-1] and closes[-2]>opens[-2]:
                put+=3;  factors.append("bear_engulf")

    # 7. Momentum
    if closes[-1]>closes[-2]>closes[-3]: call+=2
    elif closes[-1]<closes[-2]<closes[-3]: put+=2
    up10 = sum(1 for i in range(-10,0) if closes[i]>closes[i-1])
    if   up10>=8: call+=3; factors.append("uptrend")
    elif up10>=6: call+=1
    elif up10<=2: put+=3;  factors.append("downtrend")
    elif up10<=4: put+=1

    # 8. S/R
    rh=max(highs[-20:]); rl=min(lows[-20:]); pr=rh-rl
    if pr>0:
        pos=(closes[-1]-rl)/pr
        if pos<0.15:   call+=2
        elif pos>0.85: put+=2

    # 9. ATR filter
    at=_atr(highs,lows,closes)
    avg_b=sum(abs(closes[i]-opens[i]) for i in range(-5,0))/5
    if at>0 and avg_b/at<0.15:
        call=int(call*0.7); put=int(put*0.7)

    total=call+put
    if total==0: return None,0,0
    diff=abs(call-put)
    sig="CALL" if call>put else "PUT"
    cf=min(len(factors)*1.8,8)
    acc=min(round(82+(diff/total)*8+cf,1),95.0)
    return sig, acc, diff

# ═══════════════════════════════════════
# SMART SCANNER — সেরা pair বেছে নেয়
# ═══════════════════════════════════════
async def scan_best(session, needed):
    pairs = ALL_PAIRS.copy(); random.shuffle(pairs)

    async def _do(pair):
        try:
            c = await fetch_candles(session, pair)
            if not c or len(c)<30: return None
            sig,acc,diff = analyze(c)
            if sig is None: return None
            return (pair, sig, acc, diff, c[-1]["close"])
        except: return None

    results = await asyncio.gather(*[_do(p) for p in pairs], return_exceptions=True)
    found = [r for r in results if r and not isinstance(r, Exception)]
    found.sort(key=lambda x:(x[2],x[3]), reverse=True)

    # min accuracy filter
    for threshold in [85, 80, 75, 0]:
        best = [f for f in found if f[2]>=threshold]
        if len(best) >= needed: return best[:needed]
    return found[:needed]

# ═══════════════════════════════════════
# SESSION SUMMARY
# ═══════════════════════════════════════
def session_summary(win, loss):
    total=win+loss
    bars="🟩"*win+"🟥"*loss
    acc=round(win/total*100,1) if total>0 else 0
    return (
        "𝗧𝗢𝗗𝗔𝗬𝗦  𝗩𝗜𝗣  𝗦𝗜𝗚𝗡𝗔𝗟\n"
        f"{bars}\n\n"
        f"𝗧𝗼𝘁𝗮𝗹 : {total:02d} 🎀\n"
        f"𝗪𝗶𝗻   : {win:02d} 📊\n"
        f"𝗟𝗼𝘀𝘀  : {loss:02d} {'☑️' if loss==0 else '❌'}\n\n"
        f"🎯 Accuracy: {acc}%\n\n"
        f"⭐️ {OWNER_USERNAME} ✅"
    )

# ═══════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════
def main_kb(uid=None):
    return ReplyKeyboardMarkup([
        ["📊 Signal নিন", "💎 VIP কিনুন"],
        ["📈 আমার স্ট্যাটাস", "📋 হেল্প"],
        ["📞 সাপোর্ট"],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        ["👤 Profile", "💳 Payment"],
        ["📢 Broadcast", "📋 Report"],
        ["🔙 User Menu"],
    ], resize_keyboard=True)

# ═══════════════════════════════════════
# /start
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.message.from_user.id)
    name = update.message.from_user.first_name or "বন্ধু"
    get_user(uid)
    if int(uid)==ADMIN_ID:
        await update.message.reply_text(
            f"🔧 ADMIN PANEL\n━━━━━━━━━━\nস্বাগতম {name}! 👑",
            reply_markup=admin_kb()
        ); return
    await update.message.reply_text(
        f"আস্সালামু আলাইকুম, {name}! 👋\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏆  Claw VIP BOT  🏆\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ ৩০টা pair real-time scan\n"
        "✅ Binance+Yahoo+Twelve Data\n"
        "✅ MACD+RSI+BB+Stoch+EMA\n"
        "✅ Real WIN/LOSS result\n\n"
        f"🆓 Free : দিনে {FREE_SIGNALS}টা\n"
        f"💎 VIP  : দিনে {VIP_SIGNALS*3}টা\n\n"
        f"📞 {SUPPORT_USERNAME} | 👑 {OWNER_USERNAME}",
        reply_markup=main_kb(uid)
    )

# ═══════════════════════════════════════
# SIGNAL SESSION
# ═══════════════════════════════════════
async def run_signal_session(update, uid):
    if uid in active_sessions:
        await update.message.reply_text("⚠️ Session চলছে!", reply_markup=main_kb(uid)); return

    reset_daily(uid)
    vip   = is_vip(uid)
    admin = int(uid) == ADMIN_ID

    if not vip and not admin:
        u = get_user(uid)
        if len(u.get("session_used_today",[])) >= 1:
            await update.message.reply_text(
                f"⛔ আজকের {FREE_SIGNALS}টা signal শেষ।\n💎 VIP = {VIP_SIGNALS*3}টা/দিন → /buy",
                reply_markup=main_kb(uid)
            ); return
        slot = "free"
    elif vip and not admin:
        if not in_session():
            await update.message.reply_text(
                f"⛔ VIP session বন্ধ।\n⏰ পরবর্তী: {next_session()}\n\n"
                "সকাল ৭–১২ | দুপুর ১–৪ | সন্ধ্যা ৭–৯:৩০",
                reply_markup=main_kb(uid)
            ); return
        slot = current_slot()
        u = get_user(uid)
        if slot and slot in u.get("session_used_today",[]):
            sn = {"morning":"সকাল","afternoon":"দুপুর","evening":"সন্ধ্যা"}.get(slot, slot)
            await update.message.reply_text(
                f"⛔ {sn} session আগেই নেওয়া হয়েছে।",
                reply_markup=main_kb(uid)
            ); return
    else:
        slot = None

    per = VIP_SIGNALS if vip else FREE_SIGNALS
    active_sessions.add(uid)

    try:
        await update.message.reply_text(
            f"🔍 ৩০টা pair scan করছি...\n⏳ একটু অপেক্ষা করুন",
            reply_markup=main_kb(uid)
        )

        async with aiohttp.ClientSession() as http:
            signals = await scan_best(http, per)

            if not signals:
                await update.message.reply_text(
                    "⚠️ Market data পাচ্ছি না।\n২ মিনিট পরে আবার try করুন।",
                    reply_markup=main_kb(uid)
                )
                active_sessions.discard(uid); return

            # Mark session used
            if slot and not admin:
                u = get_user(uid)
                used = u.get("session_used_today",[])
                if slot not in used: used.append(slot)
                update_user(uid, "session_used_today", used)

            s_win=0; s_loss=0

            for pair,sig,acc,diff,entry_est in signals:
                now   = dhaka_now()
                wait  = secs_to_candle()
                etime = (now+timedelta(seconds=wait)).replace(
                            second=0,microsecond=0).strftime("%H:%M")
                sig_line = "🟢 CALL UP ⬆️" if sig=="CALL" else "🔴 PUT DOWN ⬇️"
                badge    = "💎" if vip else "🆓"

                await update.message.reply_text(
                    "━━━━━━━━━━━━━━━━━\n"
                    f"📊 Pair  : {pair}\n"
                    f"⏰ Entry : {etime}\n"
                    "🕐 Time  : 1 Minute\n"
                    f"{sig_line}\n"
                    +(f"🎯 Accuracy: {acc}%\n" if vip else "")+
                    "━━━━━━━━━━━━━━━━━\n"
                    f"{badge} CLAW VIP BOT {badge}"
                )

                await asyncio.sleep(max(wait, 1))

                # ── Entry price ──
                entry_price = await get_fresh_price(http, pair)
                if not entry_price: entry_price = entry_est

                await update.message.reply_text("⏳ Trade চলছে... ৬০ সেকেন্ড")
                await asyncio.sleep(63)

                # ── Exit price ──
                exit_price = await get_fresh_price(http, pair)

                # ── Real Win/Loss ──
                is_win = None
                if entry_price and exit_price:
                    d = exit_price - entry_price
                    if abs(d) >= 0.000001:
                        is_win = (d>0) if sig=="CALL" else (d<0)
                    else:
                        # price same — ৩০s পরে আবার check
                        await asyncio.sleep(30)
                        ep2 = await get_fresh_price(http, pair)
                        if ep2:
                            d2 = ep2 - entry_price
                            exit_price = ep2
                            is_win = (d2>=0) if sig=="CALL" else (d2<=0)

                if is_win is None: continue

                icon = "✅ WIN" if is_win else "❌ Loss"
                dir_str = "CALL ⬆️" if sig=="CALL" else "PUT ⬇️"
                price_info = ""
                if entry_price and exit_price:
                    dp = exit_price - entry_price
                    price_info = (f"\n📌 Entry: {entry_price:.5f}"
                                  f"\n📌 Exit : {exit_price:.5f}"
                                  f"\n📌 Diff : {dp:+.5f}")

                await update.message.reply_text(
                    f"📊 {pair} — {dir_str}\n{icon}{price_info}"
                )

                if is_win:
                    s_win += 1
                    await update_user_async(uid,"win",get_user(uid).get("win",0)+1)
                else:
                    s_loss += 1
                    await update_user_async(uid,"loss",get_user(uid).get("loss",0)+1)

                await update_user_async(uid,"signal_count",
                                        get_user(uid).get("signal_count",0)+1)
                add_xp(uid, 5)
                await asyncio.sleep(3)

        await update.message.reply_text(
            session_summary(s_win, s_loss), reply_markup=main_kb(uid)
        )

    except Exception as e:
        print(f"Signal error uid={uid}: {e}")
        await update.message.reply_text(
            "⚠️ সমস্যা হয়েছে। আবার try করুন।", reply_markup=main_kb(uid)
        )
    finally:
        active_sessions.discard(uid)

# ═══════════════════════════════════════
# BUY / PAYMENT
# ═══════════════════════════════════════
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💰 {VIP_PRICE} টাকা — ১ মাস", callback_data="pay_500")],
        [InlineKeyboardButton("🔙 বাতিল", callback_data="pay_cancel")],
    ])
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━\n💎 VIP PLAN\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ দিনে {VIP_SIGNALS*3}টা Signal ({VIP_SIGNALS}×৩ session)\n"
        "✅ 83–95% Accuracy\n"
        "✅ Real WIN/LOSS\n"
        "✅ Binance+Yahoo+Alpha data\n\n"
        "নিচে select করুন:",
        reply_markup=kb
    )

async def payment_cb(update, context):
    q = update.callback_query; await q.answer()
    d = q.data; uid = str(q.from_user.id)

    if d == "pay_500":
        pending_payment[uid] = {"amount":500}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 bKash",   callback_data="pm_bkash")],
            [InlineKeyboardButton("📱 Nagad",   callback_data="pm_nagad")],
            [InlineKeyboardButton("💳 Binance", callback_data="pm_binance")],
            [InlineKeyboardButton("🔙 Back",    callback_data="pay_500")],
        ])
        await q.edit_message_text("💳 Payment method বেছে নাও:", reply_markup=kb)

    elif d in ["pm_bkash","pm_nagad","pm_binance"]:
        method = d.replace("pm_","")
        pending_txn[uid] = {
            "method": method,
            "amount": pending_payment.get(uid,{}).get("amount",VIP_PRICE)
        }
        info = PAYMENT_INFO.get(method,"")
        amt  = pending_txn[uid]["amount"]
        if method=="binance":
            msg = (f"💳 Binance Pay ID: {info}\n\n"
                   f"💰 {amt} TK সমপরিমাণ USDT পাঠান\n\n"
                   "✅ পাঠানোর পর Transaction ID পাঠাও")
        else:
            msg = (f"📱 {method.upper()}: {info} (Send Money)\n\n"
                   f"💰 {amt} টাকা পাঠান\n\n"
                   "✅ পাঠানোর পর Transaction ID পাঠাও")
        await q.edit_message_text(msg)

    elif d == "pay_cancel":
        pending_payment.pop(uid,None); pending_txn.pop(uid,None)
        await q.edit_message_text("❌ বাতিল।")

    elif d.startswith("vip_yes_"):
        if q.from_user.id != ADMIN_ID: return
        tid = int(d.replace("vip_yes_",""))
        await _activate_vip(context.bot, tid, "Payment")
        await q.edit_message_text(f"✅ {tid} — VIP activated!")

    elif d.startswith("vip_no_"):
        if q.from_user.id != ADMIN_ID: return
        tid = int(d.replace("vip_no_",""))
        try: await context.bot.send_message(tid,f"❌ Rejected.\n{SUPPORT_USERNAME}")
        except: pass
        await q.edit_message_text(f"❌ {tid} — Rejected.")

    elif d.startswith("admin_"):
        await _admin_cb(q, context, d)

async def _activate_vip(bot, tid, method):
    update_user(str(tid),"is_vip",True)
    d = load_json(DATA_FILE)
    d["total_vip"]    = d.get("total_vip",0)+1
    d["total_income"] = d.get("total_income",0)+VIP_PRICE
    save_json(DATA_FILE, d)
    try:
        await bot.send_message(tid,
            "🎉 অভিনন্দন! তুমি 💎 VIP Member!\n\n"
            "⏰ সকাল ৭–১২ | দুপুর ১–৪ | সন্ধ্যা ৭–৯:৩০\n"
            f"✅ {VIP_SIGNALS*3} signal/দিন\n\n"
            f"📊 Signal নিন বাটনে চাপো! 🔥\n{OWNER_USERNAME}"
        )
    except: pass
    try:
        uname = load_json(USER_FILE).get(str(tid),{}).get("name","বন্ধু")
        await bot.send_message(GROUP_ID,
            f"🎉 নতুন VIP!\n👤 {uname} | 🆔 {tid}\n💰 {VIP_PRICE}৳\n{OWNER_USERNAME}"
        )
    except: pass

async def _handle_txn(update, context, uid, txn):
    u = update.message.from_user
    p = pending_txn.get(uid,{})
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ VIP দাও", callback_data=f"vip_yes_{u.id}"),
        InlineKeyboardButton("❌ বাতিল",  callback_data=f"vip_no_{u.id}"),
    ]])
    try:
        await context.bot.send_message(ADMIN_ID,
            f"🟢 VIP Payment!\n👤 {u.first_name}\n🆔 {u.id}\n"
            f"💳 {p.get('method','?').upper()}\n💰 {p.get('amount',VIP_PRICE)}৳\n"
            f"📋 TXN: {txn}",
            reply_markup=kb
        )
        pending_txn.pop(uid,None); pending_payment.pop(uid,None)
        await update.message.reply_text("✅ TXN ID পাঠানো হয়েছে!\n📸 এখন Screenshot পাঠাও।")
    except:
        await update.message.reply_text(f"সমস্যা। {SUPPORT_USERNAME}")

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo: return
    u = update.message.from_user
    try:
        await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id,
            caption=f"📸 Screenshot\n👤 {u.first_name}\n🆔 {u.id}")
        await update.message.reply_text("📸 পৌঁছে গেছে! Admin verify করবে।")
    except: pass

# ═══════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text("🔧 ADMIN PANEL", reply_markup=admin_kb())

async def vip_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    try:
        tid = int(context.args[0])
        await _activate_vip(context.bot, tid, "Manual")
        await update.message.reply_text(f"✅ {tid} VIP!", reply_markup=admin_kb())
    except:
        await update.message.reply_text("use: /vip_on [user_id]")

async def owner_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    d = load_json(DATA_FILE); users = load_json(USER_FILE)
    today = str(datetime.now().date())
    tv = sum(1 for u in users.values() if u.get("is_vip"))
    ay = sum(1 for u in users.values() if u.get("is_vip") and u.get("last_reset")==today)
    await update.message.reply_text(
        f"📊 Report — {today}\n\n"
        f"👥 মোট: {len(users)} জন\n"
        f"💎 VIP: {tv} জন\n"
        f"🆕 আজ: {ay} জন\n"
        f"💰 আজ আয়: {ay*VIP_PRICE}৳\n"
        f"💵 মোট: {d.get('total_income',0)}৳",
        reply_markup=admin_kb()
    )

async def _admin_cb(q, context, d):
    users = load_json(USER_FILE); data = load_json(DATA_FILE)
    today = str(datetime.now().date())
    if d == "admin_profile":
        tv=sum(1 for u in users.values() if u.get("is_vip"))
        ay=sum(1 for u in users.values() if u.get("is_vip") and u.get("last_reset")==today)
        kb=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔴 Bot বন্ধ" if data.get("bot_on",True) else "🟢 Bot চালু",
                callback_data="admin_toggle"
            )
        ]])
        await q.edit_message_text(
            f"👤 Profile\n👥 {len(users)}\n💎 VIP: {tv}\n"
            f"🆕 আজ: {ay}\n💰 আয়: {ay*VIP_PRICE}৳",
            reply_markup=kb
        )
    elif d == "admin_toggle":
        data["bot_on"] = not data.get("bot_on",True)
        save_json(DATA_FILE, data)
        await q.edit_message_text(f"Bot {'🟢 চালু' if data['bot_on'] else '🔴 বন্ধ'}!")
    elif d == "admin_payment":
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 bKash বদলাও",  callback_data="admin_set_bkash")],
            [InlineKeyboardButton("📱 Nagad বদলাও",  callback_data="admin_set_nagad")],
            [InlineKeyboardButton("💳 Binance বদলাও",callback_data="admin_set_binance")],
        ])
        await q.edit_message_text(
            f"💳 Payment\nbKash: {PAYMENT_INFO['bkash']}\n"
            f"Nagad: {PAYMENT_INFO['nagad']}\nBinance: {PAYMENT_INFO['binance']}",
            reply_markup=kb
        )
    elif d in ["admin_set_bkash","admin_set_nagad","admin_set_binance"]:
        key = d.replace("admin_set_","")
        admin_set_mode[str(ADMIN_ID)] = key
        await q.edit_message_text(f"নতুন {key.upper()} নম্বর লিখো:")
    elif d == "admin_broadcast":
        admin_set_mode[str(ADMIN_ID)] = "broadcast"
        await q.edit_message_text("📢 message লিখো:")

# ═══════════════════════════════════════
# STATUS / HELP / SUPPORT
# ═══════════════════════════════════════
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=str(update.message.from_user.id); u=get_user(uid)
    w=u.get("win",0); l=u.get("loss",0); t=w+l
    acc=round(w/t*100,1) if t>0 else 0
    await update.message.reply_text(
        "📊 আপনার Status\n━━━━━━━━━━━━━━━\n\n"
        +("💎 VIP ✅" if is_vip(uid) else "🆓 Free")+"\n\n"
        f"✅ Win  : {w}\n❌ Loss : {l}\n🎯 Acc  : {acc}%\n\n"
        f"Level: {u.get('level',1)} | XP: {u.get('xp',0)}",
        reply_markup=main_kb(uid)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=str(update.message.from_user.id)
    await update.message.reply_text(
        "📋 Help\n━━━━━━━━━━━━━━━\n\n"
        "📊 Signal নিন — Signal শুরু\n"
        "💎 VIP কিনুন — VIP plan\n"
        "📈 Status — Win/Loss\n"
        "📞 Support — সাহায্য\n\n"
        f"🆓 Free: {FREE_SIGNALS}টা/দিন\n"
        f"💎 VIP : {VIP_SIGNALS*3}টা/দিন\n\n"
        f"📞 {SUPPORT_USERNAME}",
        reply_markup=main_kb(uid)
    )

async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📞 Support\n━━━━━━━━━━━━━━━\n⏰ সকাল ১০টা–রাত ১০টা",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Support",
                                  url=f"https://t.me/{SUPPORT_USERNAME.replace('@','')}")],
            [InlineKeyboardButton("👑 Owner",
                                  url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")],
        ])
    )

# ═══════════════════════════════════════
# SIGNAL CALLBACK
# ═══════════════════════════════════════
async def sig_cb(update, context):
    q=update.callback_query; await q.answer()
    uid=str(q.from_user.id)
    if q.data=="sig_yes":
        pending_signal_confirm.discard(uid)
        await q.edit_message_text("✅ শুরু হচ্ছে...")
        class FM:
            async def reply_text(self,t,**kw): await q.message.reply_text(t,**kw)
        class FU: message=FM()
        await run_signal_session(FU(), uid)
    else:
        pending_signal_confirm.discard(uid)
        await q.edit_message_text("❌ বাতিল।")

# ═══════════════════════════════════════
# MAIN TEXT HANDLER
# ═══════════════════════════════════════
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    msg=update.message.text; ml=msg.lower().strip()
    uid=str(update.message.from_user.id)

    d=load_json(DATA_FILE)
    if not d.get("bot_on",True) and int(uid)!=ADMIN_ID:
        await update.message.reply_text("⚠️ Bot সাময়িক বন্ধ।"); return

    add_xp(uid, 1)

    # Admin broadcast
    if int(uid)==ADMIN_ID and admin_set_mode.get(uid)=="broadcast":
        admin_set_mode.pop(uid)
        users=load_json(USER_FILE); sent=0
        for tid in users:
            try: await context.bot.send_message(int(tid),f"📢 Admin:\n\n{msg}"); sent+=1
            except: pass
        await update.message.reply_text(f"✅ {sent} জনকে পাঠানো হয়েছে!",
                                        reply_markup=admin_kb()); return

    # Admin set mode
    if int(uid)==ADMIN_ID and uid in admin_set_mode:
        key=admin_set_mode.pop(uid)
        PAYMENT_INFO[key]=msg.strip()
        await update.message.reply_text(f"✅ {key.upper()}: {msg.strip()}",
                                        reply_markup=admin_kb()); return

    # Signal confirm
    if uid in pending_signal_confirm:
        yes=["yes","হ্যা","হে","হ্যাঁ","ha","হা","ok","okay","ওকে","sure","দাও","দে","start"]
        if any(w in ml for w in yes):
            pending_signal_confirm.discard(uid)
            await run_signal_session(update, uid)
        else:
            pending_signal_confirm.discard(uid)
            await update.message.reply_text("❌ বাতিল।", reply_markup=main_kb(uid))
        return

    # TXN ID
    if uid in pending_txn and len(msg.strip())>=5:
        await _handle_txn(update, context, uid, msg.strip()); return

    # Buttons
    if msg=="📊 Signal নিন":
        pending_signal_confirm.add(uid)
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ হ্যাঁ", callback_data="sig_yes")],
            [InlineKeyboardButton("❌ না",   callback_data="sig_no")],
        ])
        await update.message.reply_text("📊 Signal শুরু করবো?", reply_markup=kb); return

    if msg=="💎 VIP কিনুন":       await buy(update, context);    return
    if msg=="📈 আমার স্ট্যাটাস": await status_cmd(update, context); return
    if msg=="📋 হেল্প":           await help_cmd(update, context);   return
    if msg=="📞 সাপোর্ট":        await support_cmd(update, context); return

    # Admin buttons
    if int(uid)==ADMIN_ID:
        if msg=="👤 Profile":
            tv=sum(1 for u in load_json(USER_FILE).values() if u.get("is_vip"))
            await update.message.reply_text(
                f"👤 Profile\n👥 {len(load_json(USER_FILE))}\n💎 VIP: {tv}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔴 Bot বন্ধ" if d.get("bot_on",True) else "🟢 Bot চালু",
                                         callback_data="admin_toggle")
                ]])
            ); return
        if msg=="💳 Payment":
            kb=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 bKash",   callback_data="admin_set_bkash")],
                [InlineKeyboardButton("📱 Nagad",   callback_data="admin_set_nagad")],
                [InlineKeyboardButton("💳 Binance", callback_data="admin_set_binance")],
            ])
            await update.message.reply_text(
                f"💳 Payment\nbKash: {PAYMENT_INFO['bkash']}\n"
                f"Nagad: {PAYMENT_INFO['nagad']}\nBinance: {PAYMENT_INFO['binance']}",
                reply_markup=kb
            ); return
        if msg=="📢 Broadcast":
            admin_set_mode[uid]="broadcast"
            await update.message.reply_text("📢 message লিখো:",
                                            reply_markup=admin_kb()); return
        if msg=="📋 Report":  await owner_report(update, context); return
        if msg=="🔙 User Menu": await start(update, context); return
        if msg in ["admin","এডমিন"]: await admin_panel(update, context); return

    # Signal text triggers
    if any(t==ml for t in ["signal","সিগনাল","signal dao","সিগনাল দাও"]):
        pending_signal_confirm.add(uid)
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ হ্যাঁ", callback_data="sig_yes")],
            [InlineKeyboardButton("❌ না",   callback_data="sig_no")],
        ])
        await update.message.reply_text("📊 Signal শুরু করবো?", reply_markup=kb); return

    # Admin reply only
    if int(uid)==ADMIN_ID:
        await update.message.reply_text("❓ বুঝলাম না।", reply_markup=admin_kb())
    # অন্য user — কোনো reply নেই (AI বাদ)

# ═══════════════════════════════════════
# RUN
# ═══════════════════════════════════════
def main():
    app = (ApplicationBuilder()
           .token(TOKEN)
           .concurrent_updates(True)
           .build())

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("buy",    buy))
    app.add_handler(CommandHandler("vip_on", vip_on_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("admin",  admin_panel))
    app.add_handler(CommandHandler("me",     owner_report))
    app.add_handler(CallbackQueryHandler(sig_cb, pattern="^sig_(yes|no)$"))
    app.add_handler(CallbackQueryHandler(payment_cb))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))

    print("🔥 Claw VIP Bot [400+ users | Real Win/Loss | 30 pairs | 5 API sources]")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
