import os
import random
import sqlite3
import threading
from datetime import date

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

    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_daily TEXT")
    except sqlite3.OperationalError:
        pass

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


def claim_daily(user_id):
    today = date.today().isoformat()

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "SELECT last_daily FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cur.fetchone()

    if row and row[0] == today:
        conn.close()
        return False

    cur.execute(
        "UPDATE users SET points = points + 5, last_daily=? WHERE user_id=?",
        (today, user_id)
    )

    conn.commit()
    conn.close()

    return True


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
# (question, correct answer, [3 wrong answers])
# -------------------------

QUESTIONS = [
    # ---- ኢትዮጵያ ----
    ("የኢትዮጵያ ዋና ከተማ የት ነው?",
     "አዲስ አበባ", ["ጎንደር", "መቀሌ", "ሀዋሳ"]),
    ("የአድዋን ጦርነት የመሩት ንጉሠ ነገሥት ማን ናቸው?",
     "ዳግማዊ ምኒልክ", ["ዳግማዊ ቴዎድሮስ", "ዳግማዊ ዮሐንስ", "ኃይለ ሥላሴ"]),
    ("የአድዋ ጦርነት የተካሄደው በስንት ዓ.ም. ነው (በኢትዮጵያ አቆጣጠር)?",
     "1888", ["1878", "1898", "1908"]),
    ("የዓባይ ወንዝ መነሻ የሆነው ሐይቅ የትኛው ነው?",
     "ጣና", ["ላንጋኖ", "ዝዋይ", "አባያ"]),
    ("በኢትዮጵያ ከፍተኛው ተራራ የትኛው ነው?",
     "ራስ ዳሽን", ["አባ ያሬድ", "ቱሉ ዲምቱ", "ዞኳላ"]),
    ("በአለት የተፈለፈሉ አብያተ ክርስቲያናት የሚገኙባት ከተማ የትኛዋ ናት?",
     "ላሊበላ", ["አክሱም", "ጎንደር", "ሐረር"]),
    ("አክሱም የሚገኘው በየትኛው ክልል ነው?",
     "ትግራይ", ["አማራ", "ኦሮሚያ", "ሶማሌ"]),
    ("የኢትዮጵያ አዲስ ዓመት የሚጀምረው በየትኛው ወር ነው?",
     "መስከረም", ["ጥቅምት", "ሐምሌ", "ጥር"]),
    ("የኢትዮጵያ የቀን አቆጣጠር ስንት ወራት አሉት?",
     "13", ["12", "11", "14"]),
    ("ታላቁ የኢትዮጵያ ህዳሴ ግድብ የተገነባው በየትኛው ወንዝ ላይ ነው?",
     "ዓባይ", ["አዋሽ", "ዋቢ ሸበሌ", "ኦሞ"]),
    ("አበበ ቢቂላ በ1960 እ.ኤ.አ. በሮም ኦሊምፒክ ያሸነፈው በየትኛው ውድድር ነው?",
     "ማራቶን", ["5000 ሜትር", "10000 ሜትር", "የዱላ ቅብብል"]),
    ("ቡና መገኛው የትኛው አገር ነው?",
     "ኢትዮጵያ", ["ብራዚል", "ኮሎምቢያ", "የመን"]),
    ("የኢትዮጵያ ገንዘብ ስም ማን ነው?",
     "ብር", ["ሽልንግ", "ናቅፋ", "ዶላር"]),
    ("ከዓለም በጣም ሞቃታማ ቦታዎች አንዱ የሆነው ዳሎል የሚገኘው በየትኛው ክልል ነው?",
     "አፋር", ["ሲዳማ", "ጋምቤላ", "ሐረሪ"]),
    ("ጥምቀት በዓል የሚከበረው በየትኛው ወር ነው?",
     "ጥር", ["መስከረም", "ሚያዝያ", "ሐምሌ"]),

    # ---- ሳይንስ ----
    ("የፀሐይ ቅርብ ፕላኔት የትኛው ነው?",
     "ሜርኩሪ", ["ምድር", "ማርስ", "ጁፒተር"]),
    ("በፀሐይ ሥርዓት ውስጥ ትልቁ ፕላኔት የትኛው ነው?",
     "ጁፒተር", ["ሳተርን", "ምድር", "ኔፕቱን"]),
    ("የውሃ ኬሚካላዊ ቀመር ምንድን ነው?",
     "H₂O", ["CO₂", "O₂", "NaCl"]),
    ("ተክሎች ከአየር የሚወስዱት ጋዝ የትኛው ነው?",
     "ካርቦን ዳይኦክሳይድ", ["ኦክሲጅን", "ናይትሮጅን", "ሃይድሮጅን"]),
    ("የሰው አካል ትልቁ አካል የትኛው ነው?",
     "ቆዳ", ["ጉበት", "ልብ", "ሳንባ"]),
    ("አንድ ጎልማሳ ሰው ስንት ጥርስ አለው?",
     "32", ["28", "30", "36"]),
    ("ምድር ፀሐይን አንድ ጊዜ ዞራ የምትጨርሰው በምን ያህል ጊዜ ነው?",
     "አንድ ዓመት", ["አንድ ወር", "አንድ ቀን", "አንድ ሳምንት"]),
    ("በተፈጥሮ ከሚገኙ ነገሮች ሁሉ እጅግ ጠንካራው የትኛው ነው?",
     "አልማዝ", ["ወርቅ", "ብረት", "ብር"]),
    ("በክፍል ሙቀት ፈሳሽ የሆነው ብረት የትኛው ነው?",
     "ሜርኩሪ", ["ብረት", "አሉሚኒየም", "መዳብ"]),
    ("በዓለም ላይ ትልቁ እንስሳ የትኛው ነው?",
     "ሰማያዊ ዌል", ["ዝሆን", "ቀጭኔ", "ጉማሬ"]),
    ("በመሬት ላይ ፈጣኑ እንስሳ የትኛው ነው?",
     "አቦሸማኔ", ["አንበሳ", "ፈረስ", "ነብር"]),

    # ---- አጠቃላይ እውቀት ----
    ("2 + 2 = ?",
     "4", ["3", "5", "6"]),
    ("15 × 4 = ?",
     "60", ["45", "50", "65"]),
    ("በዓለም ላይ ስንት አህጉራት አሉ?",
     "7", ["5", "6", "8"]),
    ("በዓለም ትልቁ ውቅያኖስ የትኛው ነው?",
     "ፓሲፊክ", ["አትላንቲክ", "ህንድ", "አርክቲክ"]),
    ("በስፋት ትልቋ አገር የትኛዋ ናት?",
     "ሩሲያ", ["ቻይና", "አሜሪካ", "ካናዳ"]),
    ("በዓለም ከፍተኛው ተራራ የትኛው ነው?",
     "ኤቨረስት", ["ኬ2", "ኪሊማንጃሮ", "ሞንት ብላንክ"]),
    ("የኬንያ ዋና ከተማ የት ነው?",
     "ናይሮቢ", ["ካምፓላ", "ዳሬ ሰላም", "ኪጋሊ"]),
    ("የፈረንሳይ ዋና ከተማ የት ነው?",
     "ፓሪስ", ["ሮም", "በርሊን", "ለንደን"]),
    ("የግብፅ ዋና ከተማ የት ነው?",
     "ካይሮ", ["አሌክሳንድሪያ", "ካርቱም", "ትሪፖሊ"]),
    ("የመዝለያ ዓመት (Leap year) ስንት ቀናት አሉት?",
     "366", ["365", "364", "367"]),
    ("ባለ ስድስት ጎን ቅርጽ ምን ይባላል?",
     "ሄክሳጎን", ["ፔንታጎን", "ኦክታጎን", "ትራፔዚየም"]),
    ("በጨረቃ ላይ የረገጠ የመጀመሪያው ሰው ማን ነው?",
     "ኒል አርምስትሮንግ", ["ዩሪ ጋጋሪን", "ቡዝ ኦልድሪን", "ጆን ግሌን"]),
    ("በእግር ኳስ ጨዋታ በሜዳ ላይ ከአንድ ቡድን ስንት ተጫዋቾች ይጫወታሉ?",
     "11", ["9", "10", "12"]),
]

CORRECT_POINTS = 10


# -------------------------
# Main menu
# -------------------------

def build_menu():
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

    text = (
        "🎉 እንኳን ወደ Amharic Quiz በደህና መጡ!\n\n"
        "🧠 Quiz ይጫወቱ\n"
        "🏆 Points ያግኙ\n"
        "🔥 Daily Challenge ይሞክሩ\n"
        "⭐ Premium ይጠቀሙ\n\n"
        "👇 ከታች ይምረጡ፦"
    )

    return text, InlineKeyboardMarkup(keyboard)


# -------------------------
# Start
# -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    add_user(
        user.id,
        user.first_name or "User"
    )

    text, reply_markup = build_menu()

    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )


# -------------------------
# Quiz
# -------------------------

def next_question_index(user_data):
    queue = user_data.get("queue")

    if not queue:
        queue = list(range(len(QUESTIONS)))
        random.shuffle(queue)

    index = queue.pop()
    user_data["queue"] = queue

    return index


async def show_quiz(query, context):

    user_data = context.user_data

    note = ""
    if "queue" in user_data and not user_data["queue"]:
        note = "🔄 ሁሉንም ጥያቄዎች ጨርሰዋል! እንደገና እንጀምር።\n\n"

    index = next_question_index(user_data)
    question, correct, wrongs = QUESTIONS[index]

    options = [correct] + list(wrongs)
    random.shuffle(options)

    user_data["current"] = {
        "correct": options.index(correct),
        "text": correct
    }

    keyboard = []

    for i, answer in enumerate(options):
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
        f"{note}🧠 Quiz\n\n{question}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def after_answer_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➡️ ቀጣይ ጥያቄ", callback_data="quiz")
        ],
        [
            InlineKeyboardButton("🏠 Menu", callback_data="menu")
        ]
    ])


# -------------------------
# Button Handler
# -------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "quiz":
        await show_quiz(query, context)

    elif query.data.startswith("answer_"):

        current = context.user_data.get("current")

        if not current:
            await query.edit_message_text(
                "⚠️ ይህ ጥያቄ አልፏል።\n\n"
                "አዲስ ጥያቄ ለማግኘት ከታች ይጫኑ።",
                reply_markup=after_answer_keyboard()
            )
            return

        context.user_data["current"] = None

        chosen = int(query.data.split("_")[1])

        if chosen == current["correct"]:

            add_points(user_id, CORRECT_POINTS)

            await query.edit_message_text(
                "✅ ትክክል!\n\n"
                f"🎉 +{CORRECT_POINTS} Points",
                reply_markup=after_answer_keyboard()
            )

        else:

            await query.edit_message_text(
                "❌ ስህተት!\n\n"
                f"ትክክለኛው መልስ፦ {current['text']}",
                reply_markup=after_answer_keyboard()
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

        if claim_daily(user_id):
            await query.edit_message_text(
                "🔥 Daily Challenge!\n\n"
                "🎁 Daily reward: +5 Points\n\n"
                "ነገ ለሌላ ሽልማት ተመልሰው ይምጡ!\n\n"
                "👉 /start"
            )
        else:
            await query.edit_message_text(
                "⏳ የዛሬውን ሽልማት አስቀድመው ወስደዋል።\n\n"
                "ነገ ተመልሰው ይምጡ!\n\n"
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

        text, reply_markup = build_menu()

        await query.edit_message_text(
            text,
            reply_markup=reply_markup
        )


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

    print("Amharic Quiz Bot is running...", flush=True)

    application.run_polling()


if __name__ == "__main__":
    main()
