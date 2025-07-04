
# -*- coding: utf-8 -*-
import telebot
import random
import time
import threading
import os
import sqlite3
import shutil
import logging

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
    "<b>🎰 Ласкаво просимо в Jackpot Pulse!</b>

"
    "<b>✅ Що тут відбувається:</b>
"
    "• 🎁 Щодня заходиш → отримуєш бонус PulseCoins (15–100)
"
    "• 🃏 Відкриваєш Фарт-картки → ловиш призи
"
    "• 👯 Запрошуєш друзів → ще більше PulseCoins
"
    "• 🏆 Участь у розіграшах реальних грошей

"
    "<b>⚠️ Щоб користуватися ботом, потрібно бути підписаним на наші спонсорські канали.</b>
"
    "<i>⚠️ Якщо відписуєшся від будь-якого каналу — всі бонуси та участь анулюються!</i>
"
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

@bot.message_handler(commands=['bonus'])
def give_bonus(message):
    user_id = message.from_user.id
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
    f"<b>🔮 Пульс удачі б’ється рівно 👊</b>
"
    f"<b>+{bonus} PulseCoins 💸</b>
"
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
    f"<b>🃏 Твоя фарт-картка показує:</b>

{text}",
    reply_markup=main_keyboard)

@bot.message_handler(func=lambda m: m.text == '📊 Мій профіль')
def my_profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "<b>❗️ Профіль ще порожній. Натисни /start</b>", reply_markup=main_keyboard)
        return

    save_user(user_id, last_active=int(time.time()))

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    bot.send_message(
        message.chat.id,
        f"<b>📊 Твій профіль:</b>
"
        f"🪙 PulseCoins: {user['balance']}
"
        f"📆 Стрік: {user['streak']} дні(в)
"
        f"👥 Запрошено друзів: {user['referrals']}
"
        f"🎟 Квитків на розіграш: {user['tickets']}",
        reply_markup=main_keyboard
    )

@bot.message_handler(func=lambda m: m.text == '👯 Запросити друга')
def invite_friend(message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/JackpotPulse_bot?start={user_id}"
    bot.send_message(
        message.chat.id,
        f"<b>👯 Запроси друзів!</b>
"
        f"🔗 Твоє посилання: {ref_link}
"
        f"✅ За кожного — +20 PulseCoins
🎯 Активність 3 дні — ще +10",
        reply_markup=main_keyboard
    )

@bot.message_handler(func=lambda m: m.text == '✨ Топ 5 гравців')
def show_top5(message):
    cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5")
    top5 = cursor.fetchall()

    if not top5:
        bot.send_message(message.chat.id, "<b>❌ Поки що немає гравців.</b>", parse_mode='HTML')
        return

    text = "<b>🏆 Топ 5 гравців за PulseCoins:</b>
"
    for i, (uid, balance) in enumerate(top5, start=1):
        try:
            user_info = bot.get_chat(uid)
            uname = f"@{user_info.username}" if user_info.username else f"<code>{uid}</code>"
        except Exception:
            uname = f"<code>{uid}</code>"

        text += f"{i}. {uname} — {balance}🪙 PulseCoins
"

    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == '🏆 Розіграші')
def lottery(message):
    user_id = message.from_user.id
    if not check_subscriptions(user_id):
        bot.send_message(message.chat.id, "<b>⚠️ Спершу підпишись на всі наші спонсорські канали!</b>", reply_markup=main_keyboard)
        return

    user = get_user(user_id)
    tickets = user['tickets']

cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5")
top5 = cursor.fetchall()

if not top5:
    bot.send_message(message.chat.id, "❌ Немає гравців у топі.")

text = "<b>🏆 Топ 5 гравців за PulseCoins:</b>
"

for i, (uid, balance) in enumerate(top5, start=1):
    try:
        user_info = bot.get_chat(uid)
        uname = f"@{user_info.username}" if user_info.username else f"<code>{uid}</code>"
    except:
        uname = f"<code>{uid}</code>"

    text += f"{i}. {uname} — <b>{balance}</b>🪙 PulseCoins
"

bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=main_keyboard)

markup = telebot.types.InlineKeyboardMarkup()
markup.add(telebot.types.InlineKeyboardButton("✅ Взяти участь", callback_data="join_lottery"))
bot.send_message(message.chat.id, info, reply_markup=markup)
