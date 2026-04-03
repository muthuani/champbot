import json
import os
import logging
from datetime import datetime, time
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- LOGGING ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SON_CHAT_ID = int(os.environ.get("SON_CHAT_ID", "0"))

# Parse multiple Parent IDs from Railway: "ID1,ID2"
PARENT_IDS_RAW = os.environ.get("PARENT_IDS", "0")
PARENT_IDS = [int(i.strip()) for i in PARENT_IDS_RAW.split(",") if i.strip().isdigit()]

DATA_FILE = Path("champ_data.json")

# --- DATA MODELS ---
DEFAULT_TASKS = [
    {"id": "waking",      "name": "🌅 Waking up @ 5am",                "points": 15, "deadline": "05:05", "cat": "morning"},
    {"id": "teeth",       "name": "🦷 Brushing teeth",                 "points": 15, "deadline": "05:15", "cat": "morning"},
    {"id": "exercise",    "name": "🏃 Morning exercise",               "points": 15, "deadline": "06:00", "cat": "morning"},
    {"id": "toilet",      "name": "🚿 Loo & Shower",                   "points": 15, "deadline": "06:30", "cat": "morning"},
    {"id": "uniform",     "name": "👔 Ironing uniform",                "points": 15, "deadline": "06:45", "cat": "morning"},
    {"id": "cleanliness", "name": "🧼 Oil/Shoes/Socks",                "points": 15, "deadline": "07:00", "cat": "morning"},
    {"id": "to_school",   "name": "🏫 Leave for school",               "points": 15, "deadline": "07:10", "cat": "morning"},
    {"id": "fromschool",  "name": "🍱 Keep uniform/Clean lunch box",   "points": 15, "deadline": "16:30", "cat": "evening"},
    {"id": "homework",    "name": "📚 Homework",                       "points": 15, "deadline": "18:00", "cat": "evening"},
    {"id": "v_english",   "name": "🔤 English Vocabulary",             "points": 15, "deadline": "18:30", "cat": "evening"},
    {"id": "french",      "name": "🥖 Learning French",                "points": 15, "deadline": "19:00", "cat": "evening"},
    {"id": "maths",       "name": "🔢 Maths",                          "points": 15, "deadline": "19:30", "cat": "evening"},
    {"id": "science",     "name": "🧪 Science",                        "points": 15, "deadline": "20:00", "cat": "evening"},
    {"id": "ict",         "name": "💻 ICT",                            "points": 15, "deadline": "20:30", "cat": "evening"},
    {"id": "reading",     "name": "📖 Reading 10 pages",               "points": 15, "deadline": "21:00", "cat": "evening"},
]

DEFAULT_REWARDS = [
    {"id": "screen30", "name": "📱 30 min extra screen time", "cost": 150},
    {"id": "movie",    "name": "🎬 Favorite movie",             "cost": 450},
    {"id": "treat",    "name": "🍕 Favourite meal / treat",     "cost": 600},
    {"id": "cash10",   "name": "💵 10 SCR cash",                "cost": 350},
]

def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f: return json.load(f)
    return {"tasks": DEFAULT_TASKS, "rewards": DEFAULT_REWARDS, "points": 0, "history": [], "redemptions": [], "weekly_goal": 700}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2, default=str)

# --- HELPERS ---
def is_parent(user_id): return user_id in PARENT_IDS
def is_son(user_id): return user_id == SON_CHAT_ID
def today_str(): return datetime.now().strftime("%Y-%m-%d")

# --- KEYBOARDS ---
def son_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("☀️ Morning Missions"), KeyboardButton("🌙 Evening & Study")],
        [KeyboardButton("📊 My Points"), KeyboardButton("🎁 Rewards")],
        [KeyboardButton("📜 History")]
    ], resize_keyboard=True)

def parent_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Approve Tasks"), KeyboardButton("🎁 Approve Rewards")],
        [KeyboardButton("⚙️ Manage Tasks"), KeyboardButton("🎡 Manage Rewards")],
        [KeyboardButton("📈 Weekly Progress"), KeyboardButton("🔄 Reset Today")]
    ], resize_keyboard=True)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_parent(uid):
        await update.message.reply_text("<b>🏆 Parent Panel Active</b>", parse_mode="HTML", reply_markup=parent_main_keyboard())
    elif is_son(uid):
        await update.message.reply_text("<b>🚀 Welcome Champ!</b>", parse_mode="HTML", reply_markup=son_main_keyboard())
    else:
        await update.message.reply_text(f"Your ID: <code>{uid}</code>\nSend this to Dad.", parse_mode="HTML")

# --- SON TASK LOGIC ---
async def show_category_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, cat):
    data = load_data()
    done = [h["task_id"] for h in data["history"] if h["date"] == today_str() and h["status"] != "denied"]
    tasks = [t for t in data["tasks"] if t.get("cat") == cat and t["id"] not in done]

    if not tasks:
        await update.message.reply_text("🎉 All missions complete for this category!")
        return

    buttons = [[InlineKeyboardButton(t["name"], callback_data=f"confirm|{t['id']}")] for t in tasks]
    await update.message.reply_text(f"Select a {cat} mission:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("|")
    action = parts[0]
    data = load_data()
    uid = update.effective_user.id

    if action == "confirm":
        t_id = parts[1]
        task = next(t for t in data["tasks"] if t["id"] == t_id)
        kb = [[InlineKeyboardButton("✅ Confirm Done", callback_data=f"submit|{t_id}")],
              [InlineKeyboardButton("❌ Oops, Go Back", callback_data="cancel_sub")]]
        await query.edit_message_text(f"Confirming: <b>{task['name']}</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "submit":
        t_id = parts[1]
        task = next(t for t in data["tasks"] if t["id"] == t_id)
        
        # Timing Logic
        now = datetime.now()
        deadline_time = datetime.strptime(task.get("deadline", "23:59"), "%H:%M").time()
        deadline_dt = now.replace(hour=deadline_time.hour, minute=deadline_time.minute)
        
        pts = task["points"]
        status_txt = "On Time! ✅"
        if now > deadline_dt:
            diff = (now - deadline_dt).total_seconds() / 60
            if diff <= 30: pts, status_txt = int(pts * 0.5), "Late (50%) ⚠️"
            else: pts, status_txt = 2, "Very Late (2pts) 🐢"

        data["history"].append({"date": today_str(), "task_id": t_id, "task_name": task["name"], "points": pts, "status": "pending"})
        save_data(data)
        await query.edit_message_text(f"✅ Submitted: {task['name']} ({pts} expected pts)")
        
        for pid in PARENT_IDS:
            kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"p_app|T|{t_id}|{today_str()}"),
                   InlineKeyboardButton("❌ Deny", callback_data=f"p_rej|T|{t_id}|{today_str()}")]]
            await context.bot.send_message(pid, f"🔔 <b>New Task</b>\n{task['name']}\nStatus: {status_txt}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action.startswith("p_") and is_parent(uid):
        act, itype, iid, idate = parts[0], parts[1], parts[2], parts[3]
        for h in data["history"]:
            if h["task_id"] == iid and h["date"] == idate and h["status"] == "pending":
                if act == "p_app":
                    h["status"] = "approved"
                    data["points"] += h["points"]
                    await query.edit_message_text(f"✅ Approved by {update.effective_user.first_name}")
                    await context.bot.send_message(SON_CHAT_ID, f"🌟 <b>{h['task_name']}</b> approved! +{h['points']} pts!", parse_mode="HTML")
                else:
                    h["status"] = "denied"
                    await query.edit_message_text(f"❌ Denied")
                break
        save_data(data)

    elif action == "cancel_sub":
        await query.edit_message_text("Cancelled.")

# --- HANDLER ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    data = load_data()

    if is_son(uid):
        if text == "☀️ Morning Missions": await show_category_tasks(update, context, "morning")
        elif text == "🌙 Evening & Study": await show_category_tasks(update, context, "evening")
        elif text == "📊 My Points": await update.message.reply_text(f"💰 Balance: <b>{data['points']} pts</b>", parse_mode="HTML")
        elif text == "🎁 Rewards":
            lines = [f"<b>🎁 Rewards (Balance: {data['points']} pts)</b>"]
            for r in data["rewards"]: lines.append(f"• <code>{r['id']}</code>: {r['name']} ({r['cost']} pts)")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📜 History":
            hist = data["history"][-8:]
            msg = "\n".join([f"• {h['task_name']} ({h['status']})" for h in hist])
            await update.message.reply_text(msg or "No history.")

    elif is_parent(uid):
        if text == "⚙️ Manage Tasks": await update.message.reply_text("Use `/addtask id|Name|Pts|Time|cat`")
        elif text == "📈 Weekly Progress": await update.message.reply_text(f"Weekly Goal: {data['weekly_goal']} pts\nTotal Points: {data['points']}")
        elif text == "🔄 Reset Today":
            data["history"] = [h for h in data["history"] if h["date"] != today_str()]
            save_data(data)
            await update.message.reply_text("Today reset.")

async def add_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    try:
        p = " ".join(context.args).split("|")
        data = load_data()
        data["tasks"] = [t for t in data["tasks"] if t["id"] != p[0]]
        data["tasks"].append({"id": p[0], "name": p[1], "points": int(p[2]), "deadline": p[3], "cat": p[4]})
        save_data(data)
        await update.message.reply_text(f"✅ Saved Task: {p[1]}")
    except: await update.message.reply_text("Format: `/addtask id|Name|Pts|Time|cat`")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtask", add_task_cmd))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__": main()
