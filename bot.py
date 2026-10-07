import time
import random
import sqlite3
import requests

# ============================================================
# ====================== НАСТРОЙКИ ===========================
# ============================================================
BOT_TOKEN = "8888267318:AAEDr28Hdo4t56ltDD4OHqqfzm-Ma6JbnRk"
ADMIN_ID = 8888267318

REF_REWARD = 100
START_BONUS = 500
MIN_WITHDRAW = 1000
MIN_REFS_FOR_WITHDRAW = 10

DEFAULT_CHANNELS = [
    "@GiftTelegramstars1",
    "@GifterStarsTg",
    "https://t.me/GiftStarsTelegrams",
]

HELP_TEXT = "Связь с админом: @SpamBot"
DB_PATH = "gift_stars.db"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET = 0
ADMIN_STATE = {}

# ============================================================
# ======================== БАЗА ==============================
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance INTEGER DEFAULT 0,
        ref_id INTEGER,
        ref_count INTEGER DEFAULT 0,
        captcha_passed INTEGER DEFAULT 0,
        subscribed INTEGER DEFAULT 0,
        state TEXT DEFAULT 'start',
        captcha_answer TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL UNIQUE
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM channels")
    if cur.fetchone()[0] == 0:
        for ch in DEFAULT_CHANNELS:
            chat = ch if ch.startswith("@") else "@" + ch
            cur.execute("INSERT OR IGNORE INTO channels (chat_id) VALUES (?)", (chat,))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def add_user(user_id, username, first_name, ref_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO users (user_id, username, first_name, ref_id, b>
                   VALUES (?, ?, ?, ?, ?)""", (user_id, username, first_name, ref_id, ST>
    if ref_id:
        cur.execute("UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 W>
                    (REF_REWARD, ref_id))
    conn.commit()
    conn.close()
def update_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    cur.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
    conn.commit()
    conn.close()

def get_channels():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, chat_id FROM channels ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows

def add_channel(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO channels (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def delete_channel(channel_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM users")
    total_users, total_balance = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM users WHERE subscribed = 1")
    subscribed = cur.fetchone()[0]
    conn.close()
    return total_users, total_balance, subscribed

def get_withdrawals():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, amount FROM withdrawals WHERE status = 'pending'")
    rows = cur.fetchall()
    conn.close()
    return rows

def close_withdrawal(wid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE withdrawals SET status = 'done' WHERE id = ?", (wid,))
    conn.commit()
    conn.close()

# ============================================================
# ==================== HTTP HELPERS ==========================
# ============================================================
def api(method, **params):
    try:
        r = requests.post(f"{API}/{method}", json=params, timeout=15)
        return r.json()
    except Exception as e:
        print("API error:", e)
        return {"ok": False}

def send(chat_id, text, reply_markup=None):
    p = {"chat_id": chat_id, "text": text}
    if reply_markup: p["reply_markup"] = reply_markup
    return api("sendMessage", **p)

def send_photo(chat_id, photo_url, caption, reply_markup=None):
    p = {"chat_id": chat_id, "photo": photo_url, "caption": caption}
    if reply_markup: p["reply_markup"] = reply_markup
    return api("sendPhoto", **p)

def edit(chat_id, message_id, text, reply_markup=None):
    p = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup: p["reply_markup"] = reply_markup
    return api("editMessageText", **p)

def answer_cb(cb_id, text=None, alert=False):
    p = {"callback_query_id": cb_id}
    if text:
        p["text"] = text
        p["show_alert"] = alert
    return api("answerCallbackQuery", **p)

def kb(rows):
    return {"inline_keyboard": rows}

def get_me():
    return api("getMe").get("result", {})

# ============================================================
# ============ ПРОВЕРКА ПОДПИСКИ (ЖЁСТКАЯ) ==================
# ============================================================
def check_all_subs(user_id):
    channels = get_channels()
    not_subbed = []
    for cid, chat in channels:
        try:
            res = api("getChatMember", chat_id=chat, user_id=user_id)
            if res.get("ok"):
                status = res["result"].get("status")
                if status in ("left", "kicked", "restricted"):
                    not_subbed.append(chat)
            else:
                not_subbed.append(chat)
        except:
            not_subbed.append(chat)
    return (len(not_subbed) == 0, not_subbed)

def require_sub(user_id, chat_id, message_id=None):
    ok, not_subbed = check_all_subs(user_id)
    if ok:
        update_user(user_id, subscribed=1)
        return True

    update_user(user_id, subscribed=0)
    text = ("⚠️ Ты не подписан на каналы!\n\n"
            "Чтобы пользоваться ботом, подпишись на все каналы ниже и нажми «Проверить п>
            "Не подписан на:\n" + "\n".join(f"• {c}" for c in not_subbed))
    if message_id:
        edit(chat_id, message_id, text, reply_markup=sub_kb())
    else:
        send(chat_id, text, reply_markup=sub_kb())
    return False

# ============================================================
# ====================== КАПЧА ===============================
# ============================================================
CAPTCHA_NAMES = {
    "cap_heart": "сердце ❤️",
    "cap_star": "звезду ⭐",
    "cap_circle": "круг 🔴",
    "cap_square": "квадрат 🟦",
    "cap_rhomb": "ромб 🔷",
}

def new_captcha(user_id):
    correct = random.choice(list(CAPTCHA_NAMES.keys()))
    update_user(user_id, captcha_answer=correct)
    return correct

def captcha_kb():
    return kb([
        [{"text": "❤️ сердце", "callback_data": "cap_heart"}],
        [{"text": "🔴 круг", "callback_data": "cap_circle"}],
        [{"text": "⭐ звезда", "callback_data": "cap_star"}],
        [{"text": "🟦 квадрат", "callback_data": "cap_square"}],
        [{"text": "Помощь", "callback_data": "help"}],
    ])

def captcha_kb2():
   return kb([
        [{"text": "🟦 квадрат", "callback_data": "cap_square"}],
        [{"text": "🔷 ромб", "callback_data": "cap_rhomb"}],
        [{"text": "⭐ звезда", "callback_data": "cap_star"}],
        [{"text": "❤️ сердце", "callback_data": "cap_heart"}],
        [{"text": "Помощь", "callback_data": "help"}],
    ])

def captcha_prompt(user_id):
    correct = new_captcha(user_id)
    return f"Проверка: Нажми на {CAPTCHA_NAMES[correct]}\n\nВыбери один вариант."

# ============================================================
# ==================== КЛАВИАТУРЫ ============================
# ============================================================
def sub_kb():
    rows = []
    for cid, chat in get_channels():
        rows.append([{"text": f"📢 {chat}", "url": f"https://t.me/{chat.lstrip('@')}"}])
    rows.append([{"text": "Проверить подписку", "callback_data": "check_sub"}])
    rows.append([{"text": "Помощь", "callback_data": "help"}])
    return kb(rows)

def main_kb(user_id):
    me = get_me().get("username", "bot")
    rows = [
        [{"text": "Поделиться ссылкой",
          "url": f"https://t.me/{me}?start=ref_{user_id}"}],
        [{"text": "Вывести звёзды", "callback_data": "withdraw"}],
        [{"text": "Обновить", "callback_data": "refresh"}],
        [{"text": "Помощь", "callback_data": "help"}],
    ]
    if user_id == ADMIN_ID:
        rows.append([{"text": "⚙️ Админ-панель", "callback_data": "admin"}])
    return kb(rows)

def admin_kb():
    return kb([
        [{"text": "📊 Статистика", "callback_data": "adm_stats"}],
        [{"text": "📢 Каналы", "callback_data": "adm_channels"}],
        [{"text": "📥 Заявки на вывод", "callback_data": "adm_withdrawals"}],
        [{"text": "⬅️ Назад", "callback_data": "refresh"}],
    ])

def channels_kb():
    rows = []
    for cid, chat in get_channels():
        rows.append([
            {"text": f"📢 {chat}", "callback_data": "noop"},
            {"text": "❌ Удалить", "callback_data": f"adm_del_ch_{cid}"}
        ])
    rows.append([{"text": "➕ Добавить канал", "callback_data": "adm_add_ch"}])
    rows.append([{"text": "⬅️ Назад", "callback_data": "admin"}])
    return kb(rows)

# ============================================================
# =================== ОБРАБОТЧИКИ ============================
# ============================================================
def handle_start(msg):
    user_id = msg["from"]["id"]
    username = msg["from"].get("username", "")
    first_name = msg["from"].get("first_name", "друг")
    text = msg.get("text", "")
    args = text.split()

    ref_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].split("_")[1])
        except:
            pass

    user = get_user(user_id)

    # 1) Новый юзер — капча
    if not user:
        add_user(user_id, username, first_name, ref_id)
        
        intro = (
            "Что умеет этот бот?\n\n"
            "⭐ TELEGRAM GIFT STARS\n"
            "Получайте Telegram Stars за подписки и приглашения друзей.\n\n"
            "🎁 Стартовое вознаграждение — 500 ⭐\n"
            "👥 За каждого следующего приглашённого — +50 ⭐\n"
            "⚡ Быстрые выплаты прямо на ваш Telegram-аккаунт."
        )
        send_photo(user_id,
                   "https://i.ibb.co/6bJm0ZK/telegram-gift-stars.jpg",
                   intro)

        send(user_id,
             f"Приветствую, {first_name}!\n\n"
             "Здесь можно получать звёзды за подписки и приглашённых друзей.\n\n"
             "Сначала — короткая проверка, что ты человек.\n\n" + captcha_prompt(user_id>
             reply_markup=captcha_kb())
        return

    # 2) Капча не пройдена — снова капча
    if not user[6]:
        send(user_id,
             f"Приветствую, {first_name}!\n\n"
             "Сначала — короткая проверка, что ты человек.\n\n" + captcha_prompt(user_id>
             reply_markup=captcha_kb())
        return

    # 3) Не подписан — экран подписки
    ok, not_subbed = check_all_subs(user_id)
    if not ok:
        update_user(user_id, subscribed=0)
        send(user_id,
             "⚠️ Ты не подписан на каналы!\n\n"
             "Чтобы пользоваться ботом, подпишись на все каналы ниже и нажми «Проверить >
             "Не подписан на:\n" + "\n".join(f"• {c}" for c in not_subbed),
             reply_markup=sub_kb())
        return

    # 4) Всё ок — главное меню с реферальной инфой
    update_user(user_id, subscribed=1, state="main")
    me = get_me().get("username", "bot")
    text = (f"С возвращением, {first_name}!\n\n"
            f"Твоя ссылка:\nhttps://t.me/{me}?start=ref_{user_id}\n"
            f"За каждого приглашённого — {REF_REWARD}⭐.\n"
            f"Пока приглашено — {user[5]}\n\n"
            f"К выводу ничего")
    send(user_id, text, reply_markup=main_kb(user_id))

def handle_callback(cb):
    user_id = cb["from"]["id"]
    data = cb["data"]
    msg = cb["message"]
    chat_id = msg["chat"]["id"]
    message_id = msg["message_id"]
    cb_id = cb["id"]

    # --- КАПЧА ---
    if data.startswith("cap_"):
        user = get_user(user_id)
        if user and user[9] == data:
            update_user(user_id, captcha_passed=1, state="sub", captcha_answer=None)
            answer_cb(cb_id, "Верно!")
            edit(chat_id, message_id,
                 "Готово, проверка пройдена.\n\n"
                 "Осталось подписаться на каналы.\n\n"
                 f"Нужно: {len(get_channels())}. Открывай по одному и подписывайся, пото>
                 reply_markup=sub_kb())
        else:
            answer_cb(cb_id, "Не то. Попробуй ещё раз — осталось попыток: 1.", alert=Tru>
            edit(chat_id, message_id,
                 captcha_prompt(user_id),
                 reply_markup=captcha_kb2())
        return

    # --- ПРОВЕРКА ПОДПИСКИ ---
    if data == "check_sub":
        ok, not_subbed = check_all_subs(user_id)
        if not ok:
            answer_cb(cb_id, "Ты не подписался на: " + ", ".join(not_subbed), alert=True)
            return
        update_user(user_id, subscribed=1, state="main")
        user = get_user(user_id)
        me = get_me().get("username", "bot")
        text = (f"Подписки подтверждены. Ты внутри.\n\n"
                f"Твоя ссылка:\nhttps://t.me/{me}?start=ref_{user_id}\n"
                f"За каждого друга, который зайдёт и подпишется — {REF_REWARD}⭐.\n"
                f"Приглашено: {user[5]}\n\n"
                f"К выводу пока ничего.")
        edit(chat_id, message_id, text, reply_markup=main_kb(user_id))
        return

    # --- ВСЁ ОСТАЛЬНОЕ — ТОЛЬКО ПОСЛЕ ПОДПИСКИ ---
    if data not in ("help", "admin", "adm_stats", "adm_channels",
                    "adm_add_ch", "adm_withdrawals", "noop") \
       and not data.startswith("adm_"):
        if not require_sub(user_id, chat_id, message_id):
            return

    # --- ВЫВОД ---
    if data == "withdraw":
        user = get_user(user_id)
        refs = user[5]
        balance = user[3]

        if refs < MIN_REFS_FOR_WITHDRAW:
            answer_cb(cb_id,
                      f"Пригласи {MIN_REFS_FOR_WITHDRAW} человек в свою рефералку! "
                      f"У тебя сейчас: {refs}",
                      alert=True)
            return

        if balance < MIN_WITHDRAW:
            answer_cb(cb_id, f"Минимум для вывода — {MIN_WITHDRAW}⭐. У тебя: {balance}[>
            return

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO withdrawals (user_id, amount) VALUES (?, ?)", (user_id,>
        conn.commit()
        conn.close()
        update_user(user_id, balance=0)
        answer_cb(cb_id, "Заявка отправлена админу.", alert=True)
        send(ADMIN_ID, f"💸 Новая заявка на вывод: {balance}⭐ от {user_id} (друзей: {re>

    # --- ОБНОВИТЬ ---
    elif data == "refresh":
        user = get_user(user_id)
        me = get_me().get("username", "bot")
        text = (f"С возвращением, {user[2]}!\n\n"
                f"Твоя ссылка:\nhttps://t.me/{me}?start=ref_{user_id}\n"
                f"За каждого приглашённого — {REF_REWARD}⭐.\n"
                f"Пока приглашено — {user[5]}\n\n"
                f"К выводу ничего")
        edit(chat_id, message_id, text, reply_markup=main_kb(user_id))

    # --- ПОМОЩЬ ---
    elif data == "help":
        answer_cb(cb_id, HELP_TEXT, alert=True)

    # --- АДМИН ---
    elif data == "admin":
        if user_id != ADMIN_ID: return
        edit(chat_id, message_id, "Админ-панель:", reply_markup=admin_kb())

    elif data == "adm_stats":
        if user_id != ADMIN_ID: return
        total, balance, subs = get_stats()
        text = f"📊 Статистика\n\n👥 Всего: {total}\n✅ Подписались: {subs}\n💰 Баланс: >
        edit(chat_id, message_id, text,
             reply_markup=kb([[{"text": "⬅️ Назад", "callback_data": "admin"}]]))

    elif data == "adm_channels":
        if user_id != ADMIN_ID: return
        edit(chat_id, message_id, "📢 Список каналов:", reply_markup=channels_kb())

    elif data.startswith("adm_del_ch_"):
        if user_id != ADMIN_ID: return
        cid = int(data.split("_")[-1])
        delete_channel(cid)
        edit(chat_id, message_id, "📢 Список каналов:", reply_markup=channels_kb())

    elif data == "adm_add_ch":
        if user_id != ADMIN_ID: return
        ADMIN_STATE[user_id] = "await_channel"
        edit(chat_id, message_id, "Отправь @username канала:",
             reply_markup=kb([[{"text": "⬅️ Отмена", "callback_data": "adm_channels"}]]))

    elif data == "adm_withdrawals":
        if user_id != ADMIN_ID: return
        rows = get_withdrawals()
        if not rows:
            edit(chat_id, message_id, "Заявок нет.",
                 reply_markup=kb([[{"text": "⬅️ Назад", "callback_data": "admin"}]]))
        else:
            kb_rows = []
            for r in rows:
                kb_rows.append([
                    {"text": f"#{r[0]} | {r[1]} | {r[2]}⭐", "callback_data": "noop"},
                    {"text": "✅", "callback_data": f"adm_done_wd_{r[0]}"}
                ])
            kb_rows.append([{"text": "⬅️ Назад", "callback_data": "admin"}])
            edit(chat_id, message_id, "📥 Заявки на вывод:", reply_markup=kb(kb_rows))

    elif data.startswith("adm_done_wd_"):
        if user_id != ADMIN_ID: return
        wid = int(data.split("_")[-1])
        close_withdrawal(wid)
        answer_cb(cb_id, "Заявка закрыта.", alert=True)
        rows = get_withdrawals()
        if not rows:
            edit(chat_id, message_id, "Заявок нет.",
                 reply_markup=kb([[{"text": "⬅️ Назад", "callback_data": "admin"}]]))
        else:
            kb_rows = []
            for r in rows:
                kb_rows.append([
                    {"text": f"#{r[0]} | {r[1]} | {r[2]}⭐", "callback_data": "noop"},
                    {"text": "✅", "callback_data": f"adm_done_wd_{r[0]}"}
                ])
            kb_rows.append([{"text": "⬅️ Назад", "callback_data": "admin"}])
            edit(chat_id, message_id, "📥 Заявки на вывод:", reply_markup=kb(kb_rows))

    elif data == "noop":
        answer_cb(cb_id)

def handle_message(msg):
    if "text" not in msg: return
    user_id = msg["from"]["id"]
    text = msg["text"]

    if user_id == ADMIN_ID and ADMIN_STATE.get(user_id) == "await_channel":
        chat = text.strip()
        if not chat.startswith("@"):
            chat = "@" + chat
        add_channel(chat)
        ADMIN_STATE.pop(user_id, None)
        send(user_id, f"✅ Канал {chat} добавлен.",
             reply_markup=kb([[{"text": "⚙️ Админ-панель", "callback_data": "admin"}]]))
        return

# ============================================================
# ====================== POLLING =============================
# ============================================================
def poll():
    global OFFSET
    print("Бот запущен...")
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"offset": OFFSET, "timeout": 30},
                             timeout=40).json()
            if not r.get("ok"):
                time.sleep(2)
                continue
            for upd in r["result"]:
                OFFSET = upd["update_id"] + 1
                if "message" in upd:
                    m = upd["message"]
                    if m.get("text", "").startswith("/start"):
                        handle_start(m)
                    else:
                        handle_message(m)
                elif "callback_query" in upd:
                    handle_callback(upd["callback_query"])
        except Exception as e:
            print("Poll error:", e)
            time.sleep(3)

if __name__ == "__main__":
    init_db()
    poll()
