# -*- coding: utf-8 -*-
import telebot
import random
import time
import threading
import os
import sqlite3

TOKEN = os.getenv('TOKEN')
if not TOKEN:
    raise ValueError("❗️ TOKEN не знайдено в змінних середовища!")

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

DB_FILE = 'users_data.db'
ADMIN_ID = 7262164512

sponsor_channels = ['@Vsi_PROMO', '@uaclub_casinoman']

jokes = [
    "Фарт постукав — не прикидайся, що тебе немає вдома.",
    "Краще один раз пощастити, ніж сто разів пошкодувати.",
    "Фарт — це коли за тебе грають навіть ліхтарі на вулиці.",
    "Якщо не пощастило, почекай – скоро повезе!",
]

# Ініціалізація бази даних
import shutil
import logging
# Логування у файл
logging.basicConfig(filename='bot_log.txt', level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Підключення до бази даних
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    last_bonus INTEGER DEFAULT 0,
    last_card INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    tickets INTEGER DEFAULT 0,
    last_active INTEGER DEFAULT 0,
    referral_from INTEGER,
    lottery_participation INTEGER DEFAULT 0
)
''')
conn.commit()

def save_user(user_id, **kwargs):
    fields = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    cursor.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None

def create_user(user_id, referral_from=None):
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, balance, last_bonus, last_card, streak, referrals, tickets, last_active, referral_from, lottery_participation)
        VALUES (?, 0, 0, 0, 0, 0, 0, ?, ?, 0)
    ''', (user_id, int(time.time()), referral_from))
    conn.commit()

def reset_user(user_id):
    cursor.execute('''
        UPDATE users SET balance = 0, last_bonus = 0, last_card = 0, streak = 0, referrals = 0,
        tickets = 0, last_active = ?, referral_from = NULL, lottery_participation = 0
        WHERE user_id = ?
    ''', (int(time.time()), user_id))
    conn.commit()

def check_subscriptions(user_id):
    try:
        for channel in sponsor_channels:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        return True
    except Exception as e:
        print("Subscription check error:", e)
        return False

def get_channels_buttons():
    markup = telebot.types.InlineKeyboardMarkup()
    for ch in sponsor_channels:
        markup.add(telebot.types.InlineKeyboardButton(text=ch, url=f"https://t.me/{ch.strip('@')}"))
    markup.add(telebot.types.InlineKeyboardButton(text="✅ Перевірити підписку", callback_data="check_subs"))
    return markup

main_keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.row('🎁 Щоденний фарт', '🃏 Фарт-картка')
main_keyboard.row('🏆 Розіграші', '👯 Запросити друга')
main_keyboard.row('📊 Мій профіль', '📢 Спонсори / Новини')
main_keyboard.row('⭐️ Топ 5 гравців')
main_keyboard.row('📣 Додати свій канал у Jackpot Pulse')

welcome_text = (
    "<b>🎰 Ласкаво просимо в Jackpot Pulse!</b>\n\n"
    "<b>✅ Що тут відбувається:</b>\n"
    "• 🎁 Щодня заходиш → отримуєш бонус PulseCoins (15–100)\n"
    "• 🃏 Відкриваєш Фарт-картки → ловиш призи\n"
    "• 👯 Запрошуєш друзів → ще більше PulseCoins\n"
    "• 🏆 Участь у розіграшах реальних грошей\n\n"
    "<b>⚠️ Щоб користуватися ботом, потрібно бути підписаним на наші спонсорські канали.</b>\n"
    "<i>⚠️ Якщо відписуєшся від будь-якого каналу — всі бонуси та участь анулюються!</i>\n"
    "<b>🔥 Натискай кнопку нижче, щоб почати свій шлях до джекпоту!</b>"
)

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    ref_id = None
    args = message.text.split()
    if len(args) > 1:
        try:
            ref_id = int(args[1])
        except:
            pass
    user = get_user(user_id)
    if not user:
        create_user(user_id, referral_from=ref_id)
        if ref_id and ref_id != user_id:
            ref_user = get_user(ref_id)
            if ref_user:
                new_referrals = ref_user['referrals'] + 1
                save_user(ref_id, referrals=new_referrals)
                try:
                    bot.send_message(ref_id, f"<b>🎉 У тебе новий реферал: {message.from_user.first_name} (@{message.from_user.username})</b>")
                except:
                    pass
    else:
        save_user(user_id, last_active=int(time.time()))

    bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard)
    bot.send_message(message.chat.id, "<b>🔗 Наші канали для підписки:</b>", reply_markup=get_channels_buttons())

@bot.message_handler(func=lambda m: m.text == '🎁 Щоденний фарт')
def daily_bonus(message):
    user_id = message.from_user.id
    if not check_subscriptions(user_id):
        bot.send_message(message.chat.id, "<b>⚠️ Спершу підпишись на всі наші спонсорські канали!</b>", reply_markup=main_keyboard)
        return

    user = get_user(user_id)
    now = int(time.time())
    if now - user['last_bonus'] < 86400:
        bot.send_message(message.chat.id, "<b>🕐 Ти вже сьогодні отримав фарт! Завітай завтра 😉</b>", reply_markup=main_keyboard)
        return

    bonus = random.randint(15, 100)
    new_balance = user['balance'] + bonus
    new_streak = user['streak'] + 1

    save_user(user_id, balance=new_balance, last_bonus=now, streak=new_streak, last_active=now)

bot.send_message(message.chat.id,
    f"<b>🔮 Пульс удачі б’ється рівно 👊</b>\n"
    f"<b>+{bonus} PulseCoins 💸</b>\n"
    f"<b>🔥 Стрік:</b> {new_streak} дні(в)",
    reply_markup=main_keyboard)



@bot.message_handler(func=lambda m: m.text == '🃏 Фарт-картка')
def fart_card(message):
    user_id = message.from_user.id
    if not check_subscriptions(user_id):
        bot.send_message(message.chat.id, "<b>⚠️ Спершу підпишись на всі наші спонсорські канали!</b>", reply_markup=main_keyboard)
        return

    user = get_user(user_id)
    now = int(time.time())
    if now - user['last_card'] < 86400:
        bot.send_message(message.chat.id, "<b>⏳ Фарт-картку можна відкривати лише раз на добу. Заходь завтра!</b>", reply_markup=main_keyboard)
        return

    outcomes = [
        ("💰 <b>+50 PulseCoins!</b>", 50),
        ("🎟 <b>Квиток на розіграш!</b>", 0),
        (f"🤣 <i>{random.choice(jokes)}</i>", 0),
        ("🤷‍♂️ <b>Нічого не випало цього разу. Спробуй ще!</b>", 0)
    ]

    text, coins = random.choice(outcomes)
    tickets = user['tickets'] + 1 if "Квиток" in text else user['tickets']
    balance = user['balance'] + coins if coins > 0 else user['balance']

    save_user(user_id, last_card=now, last_active=now, tickets=tickets, balance=balance)

    bot.send_message(
    message.chat.id,
    f"<b>🃏 Твоя фарт-картка показує:</b>\n\n{text}",
    reply_markup=main_keyboard
)



@bot.message_handler(func=lambda m: m.text == '📊 Мій профіль')
def my_profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "<b>❗️ Профіль ще порожній. Натисни /start</b>", reply_markup=main_keyboard)
        return

    save_user(user_id, last_active=int(time.time()))

bot.send_message(
    message.chat.id,
    f"<b>📊 Твій профіль:</b>\n"
    f"🪙 PulseCoins: {user['balance']}\n"
    f"📆 Стрік: {user['streak']} дні(в)\n"
    f"👥 Запрошено друзів: {user['referrals']}\n"
    f"🎟 Квитків на розіграш: {user['tickets']}",
    reply_markup=main_keyboard
)



@bot.message_handler(func=lambda m: m.text == '👯 Запросити друга')
def invite_friend(message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/JackpotPulse_bot?start={user_id}"
    bot.send_message(message.chat.id,
bot.send_message(
    message.chat.id,
    f"<b>👯 Запроси друзів!</b>\n"
    f"🔗 Твоє посилання: {ref_link}\n"
    f"✅ За кожного — +20 PulseCoins\n🎯 Активність 3 дні — ще +10",
    reply_markup=main_keyboard
)



@bot.message_handler(func=lambda m: m.text == '⭐️ Топ 5 гравців')
def show_top5(message):
    cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5")
    top5 = cursor.fetchall()

    if not top5:
        bot.send_message(message.chat.id, "<b>❌ Поки що немає гравців.</b>")
        return

text = "<b>🏆 Топ 5 гравців за PulseCoins:</b>\n"

for i, (uid, balance) in enumerate(top5, start=1):
    try:
        user_info = bot.get_chat(uid)
        uname = f"@{user_info.username}" if user_info.username else f"<code>{uid}</code>"
    except Exception:
        uname = f"<code>{uid}</code>"
    text += f"{i}. {uname} — <b>{balance}</b> PulseCoins\n"

bot.send_message(message.chat.id, text, parse_mode='HTML')


    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == '🏆 Розіграші')
def lottery(message):
    user_id = message.from_user.id
    if not check_subscriptions(user_id):
        bot.send_message(message.chat.id, "<b>⚠️ Спершу підпишись на всі наші спонсорські канали!</b>", reply_markup=main_keyboard)
        return

    user = get_user(user_id)
    tickets = user['tickets']

    info = (
text = "<b>🏆 Топ 5 гравців за PulseCoins:</b>\n"

for i, (uid, balance) in enumerate(top5, start=1):
    try:
        user_info = bot.get_chat(uid)
        uname = f"@{user_info.username}" if user_info.username else f"<code>{uid}</code>"
    except:
        # Просто ігноруємо будь-яку помилку
        uname = f"<code>{uid}</code>"
    text += f"{i}. {uname} — <b>{balance}</b> PulseCoins\n"

bot.send_message(message.chat.id, text, parse_mode='HTML')

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Взяти участь", callback_data="join_lottery"))
    bot.send_message(message.chat.id, info, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "join_lottery")
def handle_join_lottery(call):
    user_id = call.from_user.id
    user = get_user(user_id)
    if not user:
        bot.answer_callback_query(call.id, "❗️ Спочатку натисни /start")
        return

    method = None
    if user['tickets'] >= 15:
        save_user(user_id, tickets=user['tickets'] - 15)
        method = "квитки"
    elif user['balance'] >= 1000:
        save_user(user_id, balance=user['balance'] - 1000)
        method = "PulseCoins"
    elif user['referrals'] >= 25:
        save_user(user_id, referrals=user['referrals'] - 25)
        method = "друзі"
    else:
        bot.answer_callback_query(call.id, "❌ Недостатньо умов для участі!")
        return

    save_user(user_id, lottery_participation=1)
    bot.answer_callback_query(call.id, "✅ Ти зареєстрований у розіграші!")

    try:
        user_info = bot.get_chat(user_id)
        uname = f"@{user_info.username}" if user_info.username else user_info.first_name
        bot.send_message(ADMIN_ID, f"🎟 Новий учасник розіграшу: <b>{uname}</b>, через {method}")
    except:
        pass


@bot.message_handler(func=lambda m: m.text == '📢 Спонсори / Новини')
def sponsors_news(message):
    text = "<b>📢 Наші спонсорські канали та новини:</b>"
    markup = get_channels_buttons()
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "check_subs")
def callback_check_subs(call):
    user_id = call.from_user.id
    if check_subscriptions(user_id):
        bot.answer_callback_query(call.id, "✅ Всі канали підписані!")
    else:
        reset_user(user_id)
        bot.answer_callback_query(call.id, "❌ Ти відписався від одного з каналів. Твої бонуси анульовані!")
        bot.send_message(user_id, "<b>❗️ Ти відписався від наших спонсорських каналів.
Усі бонуси скинуто. Підпишись знову, щоб грати!</b>")


@bot.message_handler(func=lambda m: m.text == '📣 Додати свій канал у Jackpot Pulse')
def add_channel_request(message):
    bot.send_message(
    message.chat.id,
    "<b>📣 Хочеш додати свій канал у Jackpot Pulse?</b>\n"
    "Звертайся до наших менеджерів:\n"
    "👤 @vsi_promo_admin\n"
    "👤 @oleksandra_managerr\n"
    "Вони допоможуть тобі з рекламою та співпрацею!",
    reply_markup=main_keyboard,
    parse_mode='HTML'
)



@bot.message_handler(commands=['send_promo'])
def send_promo_to_all(message):
    if message.from_user.id != ADMIN_ID:
        return

    promo_text = (
        "<b>📣 УВАГА ВСІМ ВЛАСНИКАМ КАНАЛІВ!</b>
        "⭐️ <b>Хочеш отримати безкоштовне спонсорство в Jackpot Pulse?</b> ⭐️
        "🎯 Приведи найбільше рефералів сьогодні — і твій канал БЕЗКОШТОВНО отримає рекламу в нашому боті на 1 день! 🚀
        "🔥 <i>Це чудовий шанс збільшити свою аудиторію і отримати крутий бонус!</i>
        "👥 Чим більше активних підписників ти приведеш — тим більша твоя перемога!
        "📩 Пиши менеджерам для участі:
        "👤 @vsi_promo_admin
        "👤 @oleksandra_managerr
        "Не пропусти! 🎉"
    )

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    count = 0

    for (uid,) in users:
        try:
            bot.send_message(uid, promo_text)
            count += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"Помилка надсилання {uid}: {e}")

    bot.send_message(message.chat.id, f"Повідомлення надіслано {count} користувачам.")


@bot.message_handler(commands=['runlottery'])
def run_lottery(message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT user_id FROM users WHERE lottery_participation = 1")
    participants = [row[0] for row in cursor.fetchall()]

    if not participants:
        bot.send_message(message.chat.id, "<b>❌ Немає учасників для розіграшу.</b>")
        return

    random.shuffle(participants)
    winners = participants[:5]

    result = "<b>🎉 Результати розіграшу:</b>

    for idx, uid in enumerate(winners, start=1):
        try:
            user_info = bot.get_chat(uid)
            uname = f"@{user_info.username}" if user_info.username else f"<code>{uid}</code>"
            result += f"{idx}. {uname}
            cursor.execute("UPDATE users SET lottery_participation = 0 WHERE user_id = ?", (uid,))
            conn.commit()
        except Exception as e:
            result += f"{idx}. ❌ Користувач {uid} (помилка: {e})
            logging.error(f"Помилка надсилання результатів розіграшу: {uid}: {e}")

    bot.send_message(message.chat.id, result)

# Автоматичне резервне копіювання бази кожні 12 годин
def backup_database():
    while True:
        try:
            shutil.copyfile(DB_FILE, 'users_data_backup.db')
            logging.info("📦 Резервна копія бази збережена")
        except Exception as e:
            logging.error(f"❌ Помилка резервного копіювання: {e}")
        time.sleep(43200)  # кожні 12 годин

# Автоматичний запуск розіграшу щовівторка о 19:00
def auto_lottery():
    while True:
        now = time.localtime()
        if now.tm_wday == 1 and now.tm_hour == 19 and now.tm_min == 0:
            class DummyMessage:
                from_user = type('user', (), {'id': ADMIN_ID})
                chat = type('chat', (), {'id': ADMIN_ID})
            run_lottery(DummyMessage())
            time.sleep(60)
        time.sleep(30)

# Команда /stats — статистика користувачів
@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (int(time.time()) - 86400,))
    active_today = cursor.fetchone()[0]

    bot.send_message(message.chat.id, f"👥 Усього користувачів: {total}
🕒 Активні за 24 год: {active_today}")

# Фонова перевірка підписок кожні 2 години

def auto_check_subscriptions():
    while True:
        logging.info("🔍 Почато перевірку підписок...")
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        for (user_id,) in all_users:
            if not check_subscriptions(user_id):
                reset_user(user_id)
                try:
                    bot.send_message(user_id, "<b>❗️ Ти відписався від спонсорських каналів, усі бонуси анульовано. Підпишись знову, щоб грати!</b>")
                    logging.info(f"🚫 Відписався: {user_id} — скинуто дані")
                except Exception as e:
                    logging.error(f"Помилка надсилання повідомлення {user_id}: {e}")
        time.sleep(7200)  # кожні 2 години
threading.Thread(target=backup_database, daemon=True).start()
threading.Thread(target=auto_lottery, daemon=True).start()
threading.Thread(target=auto_check_subscriptions, daemon=True).start()

# Фонове нагадування щодня вранці

def daily_reminder():
    while True:
        now = time.localtime()
        if now.tm_hour == 10 and now.tm_min == 0:  # нагадування о 10:00 ранку
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            for (uid,) in users:
                try:
                    bot.send_message(uid, "<b>🔔 Не забудь сьогодні зайти в Jackpot Pulse, щоб отримати щоденний фарт і призи!</b>")
                    time.sleep(0.1)
                except Exception as e:
                    logging.warning(f"❗️ Не вдалося надіслати нагадування {uid}: {e}")
            time.sleep(60)  # щоб уникнути повторного надсилання протягом хвилини
        time.sleep(30)

threading.Thread(target=daily_reminder, daemon=True).start()
