"""
ChampBot - Final Version (Seychelles Edition)
Includes: 21 Tasks, Photo Proof, Exercise Penalties, Streak Bonuses, and ALL working buttons.
"""

import json
import os
import logging
from datetime import datetime, time
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, JobQueue
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
PARENT_CHAT_ID = int(os.environ.get("PARENT_CHAT_ID", "0"))
SON_CHAT_ID    = int(os.environ.get("SON_CHAT_ID",    "0"))
DATA_FILE      = Path("data.json")

# Task Definitions
PHOTO_REQUIRED_IDS = ["exercise", "ev_exercise", "homework", "uniform", "cleanliness"]
MORNING_IDS = ["waking", "teeth", "exercise", "toilet", "uniform", "cleanliness", "to_school"]
EVENING_IDS = ["fromschool", "homework", "v_english", "french", "w_english", "maths", "science", "history", "geo", "ict", "w_french", "reading", "ev_exercise", "chores"]

DEFAULT_TASKS = [
    {"id": "waking",      "name": "🌅 Waking up @ 5am",                "points": 15},
    {"id": "teeth",       "name": "🦷 Brushing teeth",                 "points": 15},
    {"id": "exercise",    "name": "🏃 Morning exercise",                "points": 15},
    {"id": "toilet",      "name": "🚿 Loo & Shower",                   "points": 15},
    {"id": "uniform",     "name": "👔 Ironing uniform",                "points": 15},
    {"id": "cleanliness", "name": "🧼 Apply oil/clean shoe/wash socks", "points": 15},
    {"id": "to_school",   "name": "🏫 Leave home to school by 7:10am",  "points": 15},
    {"id": "fromschool",  "name": "🍱 Keep uniform/clean lunch box",     "points": 15},
    {"id": "homework",    "name": "📚 Homework",                       "points": 15},
    {"id": "v_english",   "name": "🔤 English Vocabulary",             "points": 15},
    {"id": "french",      "name": "🥖 Learning French",                "points": 15},
    {"id": "w_english",   "name": "✍️ Writing English",                "points": 15},
    {"id": "maths",       "name": "🔢 Maths",                          "points": 15},
    {"id": "science",     "name": "🧪 Science",                        "points": 15},
    {"id": "history",     "name": "📜 History",                        "points": 15},
    {"id": "geo",         "name": "🌍 Geography",                      "points": 15},
    {"id": "ict",         "name": "💻 ICT",                            "points": 15},
    {"id": "w_french",    "name": "📝 Writing French",                 "points": 15},
    {"id": "reading",     "name": "📖 Reading 10 pages",               "points": 15},
    {"id": "ev_exercise", "name": "🚴 Evening Exercise",               "points": 15},
    {"id": "chores",      "name": "🧹 Chores / Household Tasks",       "points": 10},
]

DEFAULT_REWARDS = [
    {"id": "screen30", "name": "📱 30 min extra screen time", "cost": 150},
    {"id": "screen60", "name": "📱 1 hour extra screen time", "cost": 250},
    {"id": "movie",    "name": "🎬 Favorite movie",           "cost": 450},
    {"id": "treat",    "name": "🍕 Favourite meal / treat",   "cost": 600},
    {"id": "cash5",    "name": "💵 5 SCR cash",               "cost": 200},
    {"id": "cash10",   "name": "💵 10 SCR cash",              "cost": 350},
    {"id": "gameday",  "name": "🎮 Full game day (weekend)",  "cost": 1800},
]

def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f: return json.load(f)
    return {"tasks": DEFAULT_TASKS, "rewards": DEFAULT_REWARDS, "points": 0, "history": [], "morning_streak": 0}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2, default=str)

# --- Helper Functions ---
def is_parent(update): return update.effective_chat.id == PARENT_CHAT_ID
def is_son(update): return update.effective_chat.id == SON_CHAT_ID
def today_str(): return datetime.now().strftime("%Y-%m-%d")

def son_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("☀️ Morning Missions"), KeyboardButton("🌙 Evening & Study")],
        [KeyboardButton("📊 My points"), KeyboardButton("🏆 My streak")],
        [KeyboardButton("🎁 Rewards"), KeyboardButton("📜 History")],
    ], resize_keyboard=True)

def parent_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Approve Tasks"), KeyboardButton("📊 Son's progress")],
        [KeyboardButton("📋 View all tasks"), KeyboardButton("🔄 Reset today")]
    ], resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == PARENT_CHAT_ID:
        await update.message.reply_text("<b>🏆 Parent Panel Active</b>", parse_mode="HTML", reply_markup=parent_main_keyboard())
    elif chat_id == SON_CHAT_ID:
        await update.message.reply_text("<b>🏆 Welcome Champ!</b>", parse_mode="HTML", reply_markup=son_main_keyboard())
    else:
        await update.message.reply_text(f"Your Chat ID: <code>{chat_id}</code>", parse_mode="HTML")

async def mark_done_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, cat):
    data = load_data()
    done = [h["task_id"] for h in data["history"] if h["date"] == today_str() and h["status"] != "denied"]
    ids = MORNING_IDS if cat == "morning" else EVENING_IDS
    pending = [t for t in data["tasks"] if t["id"] in ids and t["id"] not in done]
    
    if not pending:
        await update.message.reply_text("🎉 All tasks in this category are complete!", reply_markup=son_main_keyboard())
        return

    buttons = [[KeyboardButton("✔ " + t["name"])] for t in pending]
    buttons.append([KeyboardButton("🔙 Back")])
    await update.message.reply_text("Select task:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

async def handle_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text[2:].strip()
    data = load_data()
    matched = next((t for t in data["tasks"] if t["name"] == text), None)
    
    if matched:
        if matched["id"] in PHOTO_REQUIRED_IDS:
            context.user_data["pending_task"] = matched
            await update.message.reply_text(f"📸 This task requires a photo! Please send a photo of your {matched['name']} now.")
        else:
            await submit_to_parent(update, context, matched)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update) or "pending_task" not in context.user_data: return
    task = context.user_data.pop("pending_task")
    photo_id = update.message.photo[-1].file_id
    await submit_to_parent(update, context, task, photo_id)

async def submit_to_parent(update, context, task, photo_id=None):
    data = load_data()
    final_pts = task["points"]
    now_hour = datetime.now().hour
    now_min = datetime.now().minute
    
    # Penalties
    if task["id"] == "exercise" and (now_hour > 6 or (now_hour == 6 and now_min > 30)):
        final_pts = 5
        await update.message.reply_text("⚠️ Late morning exercise! Points reduced to 5.")
    elif task["id"] == "ev_exercise" and now_hour >= 20 and now_min >= 30:
        final_pts = 5
        await update.message.reply_text("⚠️ Late evening exercise! Points reduced to 5.")

    submission = {
        "date": today_str(), "task_id": task["id"], "task_name": task["name"],
        "points": final_pts, "status": "pending", "photo": photo_id
    }
    data["history"].append(submission)
    save_data(data)
    await update.message.reply_text("✅ Sent to Dad for approval!", reply_markup=son_main_keyboard())
    if PARENT_CHAT_ID:
        msg = f"🔔 <b>{task['name']}</b> submitted for approval."
        if photo_id: await context.bot.send_photo(PARENT_CHAT_ID, photo_id, caption=msg, parse_mode="HTML")
        else: await context.bot.send_message(PARENT_CHAT_ID, msg, parse_mode="HTML")

async def approve_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    pending = [h for h in data["history"] if h.get("status") == "pending"]
    if not pending:
        await update.message.reply_text("No tasks waiting! ✨")
        return
    for h in pending:
        cb_id = f"{h['task_id']}_{h['date']}"
        keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{cb_id}"), 
                     InlineKeyboardButton("❌ Deny", callback_data=f"rej_{cb_id}")]]
        await update.message.reply_text(f"📌 {h['task_name']} ({h['points']} pts)", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, t_id, t_date = query.data.split("_")
    data = load_data()
    for h in data["history"]:
        if h["task_id"] == t_id and h["date"] == t_date and h["status"] == "pending":
            if action == "app":
                h["status"] = "approved"
                data["points"] += h["points"]
                # Streak Logic
                done_today = [x["task_id"] for x in data["history"] if x["date"] == today_str() and x["status"] == "approved"]
                if all(m in done_today for m in MORNING_IDS):
                    data["morning_streak"] = data.get("morning_streak", 0) + 1
                    if data["morning_streak"] == 5:
                        data["points"] += 50
                        data["morning_streak"] = 0
                        await context.bot.send_message(SON_CHAT_ID, "🔥 <b>5-DAY STREAK! +50 Bonus Points!</b>", parse_mode="HTML")
                await query.edit_message_text(f"✅ Approved: {h['task_name']}")
            else:
                h["status"] = "denied"
                await query.edit_message_text(f"❌ Denied: {h['task_name']}")
            break
    save_data(data)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = load_data()
    
    # --- SON COMMANDS ---
    if is_son(update):
        if text == "☀️ Morning Missions": await mark_done_prompt(update, context, "morning")
        elif text == "🌙 Evening & Study": await mark_done_prompt(update, context, "evening")
        elif text.startswith("✔ "): await handle_submission(update, context)
        elif text == "🔙 Back": await update.message.reply_text("Main Menu", reply_markup=son_main_keyboard())
        elif text == "📊 My points":
            await update.message.reply_text(f"💰 Balance: <b>{data['points']} pts</b>", parse_mode="HTML")
        elif text == "🏆 My streak":
            streak = data.get("morning_streak", 0)
            await update.message.reply_text(f"🔥 Morning Streak: <b>{streak}/5 days</b>\nComplete 5 perfect mornings for 50 bonus points!", parse_mode="HTML")
        elif text == "🎁 Rewards":
            lines = [f"<b>🎁 Rewards (Balance: {data['points']} pts)</b>\n"]
            for r in data["rewards"]:
                icon = "✅" if data["points"] >= r["cost"] else "🔒"
                lines.append(f"{icon} {r['name']} — {r['cost']} pts")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📜 History":
            recent = sorted(data["history"], key=lambda h: h["date"], reverse=True)[:15]
            if not recent:
                await update.message.reply_text("No history yet! 💪")
            else:
                lines = ["<b>📜 Recent Activity</b>\n"]
                for h in recent:
                    status = "⏳" if h["status"] == "pending" else "✅" if h["status"] == "approved" else "❌"
                    lines.append(f"• {h['date']} | {status} {h['task_name']} ({h['points']} pts)")
                await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    # --- PARENT COMMANDS ---
    elif is_parent(update):
        if text == "✅ Approve Tasks": await approve_tasks_menu(update, context)
        elif text == "📋 View all tasks":
            lines = ["<b>📋 Current Tasks</b>\n"]
            for t in data["tasks"]: lines.append(f"• {t['name']} ({t['points']} pts)")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📊 Son's progress":
            streak = data.get("morning_streak", 0)
            pending = len([h for h in data["history"] if h.get("status") == "pending"])
            await update.message.reply_text(
                f"<b>📊 Progress Report</b>\n\n"
                f"💰 Total Points: <b>{data['points']}</b>\n"
                f"🔥 Morning Streak: <b>{streak} days</b>\n"
                f"⏳ Pending Approvals: <b>{pending}</b>", 
                parse_mode="HTML"
            )
        elif text == "🔄 Reset today":
            data["history"] = [h for h in data["history"] if h["date"] != today_str()]
            save_data(data)
            await update.message.reply_text("✅ Today's history has been wiped clean.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_daily(lambda c: c.bot.send_message(SON_CHAT_ID, "🏆 <b>Good Morning!</b> Start your missions!"), time=time(3, 0))
    app.run_polling()

if __name__ == "__main__": main()
