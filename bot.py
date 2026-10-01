
import os
import sqlite3
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

# -------------------------
# Database
# -------------------------

DB = "quizbot.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            points INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, name):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, name, points) VALUES (?, ?, 0)",
        (user_id, name)
    )

    cur.execute(
        "UPDATE users SET name=? WHERE user_id=?",
        (name, user_id)
    )

    conn.commit()
    conn.close()


def get_points(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "SELECT points FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else 0


def add_points(user_id, amount):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (amount, user_id)
    )

    conn.commit()
    conn.close()


def get_leaderboard():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT name, points
        FROM users
        ORDER BY points DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


# -------------------------
# Questions
# -------------------------

QUESTIONS = [
    {
        "question": "የኢትዮጵያ ዋና ከተማ የት ነው?",
        "answers": ["አዲስ አበባ", "ጎንደር", "መቀሌ", "ሀዋሳ"],
        "correct": 0
    },
    {
        "question": "2 + 2 = ?",
        "answers": ["3", "4", "5", "6"],
        "correct": 1
    },
    {
        "question": "የፀሐይ ቅርብ ፕላኔት የትኛው ነው?",
        "answers": ["ምድር", "ማርስ", "ሜርኩሪ", "ጁፒተር"],
        "correct": 2
    }
]


# -------------------------
# Start
# -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(
        user.id,
        user.first_name or "User"
    )

    keyboard = [
        [
            InlineKeyboardButton("🧠 Start Quiz", callback_data="quiz")
        ],
        [
            InlineKeyboardButton("🔥 Daily Challenge", callback_data="daily")
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")
        ],
        [
            InlineKeyboardButton("💰 My Points", callback_data="points")
        ],
        [
            InlineKeyboardButton("👤 My Profile", callback_data="profile")
        ],
        [
            InlineKeyboardButton("⭐ Premium", callback_data="premium")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎉 እንኳን ወደ Amharic Quiz በደህና መጡ!\n\n"
        "🧠 Quiz ይጫወቱ\n"
        "🏆 Points ያግኙ\n"
        "🔥 Daily Challenge ይሞክሩ\n"
        "⭐ Premium ይጠቀሙ\n\n"
        "👇 ከታች ይምረጡ፦",
        reply_markup=reply_markup
    )


# -------------------------
# Quiz
# -------------------------

async def show_quiz(query):

    question = QUESTIONS[0]

    keyboard = []

    for i, answer in enumerate(question["answers"]):
        keyboard.append([
            InlineKeyboardButton(
                answer,
                callback_data=f"answer_{i}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🏠 Menu", callback_data="menu")
    ])

    await query.edit_message_text(
        f"🧠 Quiz\n\n{question['question']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# -------------------------
# Button Handler
# -------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "quiz":
        await show_quiz(query)

    elif query.data == "answer_0":

        add_points(user_id, 10)

        await query.edit_message_text(
            "✅ ትክክል!\n\n"
            "🎉 +10 Points\n\n"
            "ቀጣዩን Quiz ለመጫወት /start ይጫኑ።"
        )

    elif query.data.startswith("answer_"):

        await query.edit_message_text(
            "❌ ስህተት!\n\n"
            "እንደገና ይሞክሩ።\n\n"
            "👉 /start"
        )

    elif query.data == "points":

        points = get_points(user_id)

        await query.edit_message_text(
            f"💰 Your Points\n\n"
            f"⭐ {points} Points\n\n"
            f"100 Points = 1 Reward Unit\n\n"
            f"👉 /start"
        )

    elif query.data == "profile":

        points = get_points(user_id)

        await query.edit_message_text(
            f"👤 My Profile\n\n"
            f"Name: {query.from_user.first_name}\n"
            f"⭐ Points: {points}\n\n"
            f"👉 /start"
        )

    elif query.data == "leaderboard":

        rows = get_leaderboard()

        text = "🏆 TOP PLAYERS\n\n"

        if not rows:
            text += "No players yet."

        else:
            for i, row in enumerate(rows, start=1):
                text += f"{i}. {row[0]} — ⭐ {row[1]}\n"

        await query.edit_message_text(
            text + "\n\n👉 /start"
        )

    elif query.data == "daily":

        add_points(user_id, 5)

        await query.edit_message_text(
            "🔥 Daily Challenge!\n\n"
            "🎁 Daily reward: +5 Points\n\n"
            "Come back tomorrow for another reward!\n\n"
            "👉 /start"
        )

    elif query.data == "premium":

        await query.edit_message_text(
            "⭐ PREMIUM\n\n"
            "Premium features are coming soon.\n\n"
            "• More quizzes\n"
            "• Special questions\n"
            "• Premium rewards\n"
            "• Exclusive challenges\n\n"
            "👉 /start"
        )

    elif query.data == "menu":

        await query.message.delete()


# -------------------------
# Flask server for Render
# -------------------------

web = Flask(__name__)

@web.route("/")
def home():
    return "Amharic Quiz Bot is running! ✅"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    web.run(
        host="0.0.0.0",
        port=port
    )


# -------------------------
# Main
# -------------------------

def main():

    init_db()

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    print("Amharic Quiz Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
