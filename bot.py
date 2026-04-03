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

# --- CONFIGURATION (RAILWAY ENVIRONMENT VARIABLES) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SON_CHAT_ID = int(os.environ.get("SON_CHAT_ID", "0"))

# Supports comma-separated IDs: "12345,67890"
PARENT_IDS_RAW = os.environ.get("PARENT_IDS", "0")
PARENT_IDS = [int(i.strip()) for i in PARENT_IDS_RAW.split(",") if i.strip().isdigit()]

DATA_FILE = Path("champ_data.json")

# --- DATA PERSISTENCE ---
def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: pass
    return {
        "tasks": [
            {"id": "waking", "name": "🌅 Waking up @ 5am", "points": 15, "deadline": "05:05", "cat": "morning"},
            {"id": "teeth", "name": "🦷 Brushing teeth", "points": 15, "deadline": "05:15", "cat": "morning"},
            {"id": "to_school", "name": "🏫 Leave for school", "points": 15, "deadline": "07:10", "cat": "morning"}
        ],
        "rewards": [
            {"id": "screen30", "name": "📱 30 min screen time", "cost": 150},
            {"id": "cash5", "name": "💵 5 SCR cash", "cost": 200}
        ],
        "points": 0,
        "history": [],
        "redemptions": [],
        "weekly_goal": 700
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

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

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_parent(uid):
        await update.message.reply_text("<b>👨‍👩‍👦 Parent Control Active</b>", parse_mode="HTML", reply_markup=parent_main_keyboard())
    elif is_son(uid):
        await update.message.reply_text("<b>🚀 Welcome Champ!</b>", parse_mode="HTML", reply_markup=son_main_keyboard())
    else:
        await update.message.reply_text(f"Your ID: <code>{uid}</code>\nSend this to Dad.", parse_mode="HTML")

# --- SON SUBMISSION LOGIC ---
async def show_category_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, cat):
    data = load_data()
    done = [h["task_id"] for h in data["history"] if h["date"] == today_str() and h["status"] != "denied"]
    tasks = [t for t in data["tasks"] if t.get("cat") == cat and t["id"] not in done]

    if not tasks:
        await update.message.reply_text("🎉 You've finished all missions in this category!")
        return

    buttons = [[InlineKeyboardButton(t["name"], callback_data=f"confirm|{t['id']}")] for t in tasks]
    await update.message.reply_text(f"Select your {cat} mission:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("|")
    action = parts[0]
    data = load_data()
    uid = update.effective_user.id

    # --- SON ACTIONS ---
    if action == "confirm":
        t_id = parts[1]
        task = next((t for t in data["tasks"] if t["id"] == t_id), None)
        kb = [[InlineKeyboardButton("✅ Yes, I'm Done!", callback_data=f"submit|{t_id}")],
              [InlineKeyboardButton("❌ Oops, Go Back", callback_data="cancel_sub")]]
        await query.edit_message_text(f"Confirming: <b>{task['name']}</b>\nIs this correct?", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "submit":
        t_id = parts[1]
        task = next(t for t in data["tasks"] if t["id"] == t_id)
        
        # --- PENALTY CALCULATION ---
        now = datetime.now()
        deadline_time = datetime.strptime(task.get("deadline", "23:59"), "%H:%M").time()
        deadline_dt = now.replace(hour=deadline_time.hour, minute=deadline_time.minute)
        
        earned_pts = task["points"]
        timing_status = "On Time! ✅"
        
        if now > deadline_dt:
            diff_mins = (now - deadline_dt).total_seconds() / 60
            if diff_mins <= 30:
                earned_pts = int(task["points"] * 0.5)
                timing_status = f"Late by {int(diff_mins)}m (50% pts) ⚠️"
            else:
                earned_pts = 2
                timing_status = "Very Late (2 pts) 🐢"

        data["history"].append({
            "date": today_str(), "task_id": task["id"], "task_name": task["name"],
            "points": earned_pts, "status": "pending"
        })
        save_data(data)
        await query.edit_message_text(f"✅ Sent to Parents: {task['name']}\nPoints expected: {earned_pts}")
        
        for pid in PARENT_IDS:
            msg = f"🔔 <b>Task Approval</b>\nTask: {task['name']}\nStatus: {timing_status}\nPoints: {earned_pts}"
            kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"p_app|T|{t_id}|{today_str()}"),
                   InlineKeyboardButton("❌ Deny", callback_data=f"p_rej|T|{t_id}|{today_str()}")]]
            await context.bot.send_message(pid, msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "cancel_sub":
        await query.edit_message_text("Action cancelled. Use the menu below.")

    # --- PARENT ACTIONS ---
    elif action.startswith("p_") and is_parent(uid):
        p_act, itype, iid, idate = parts[0], parts[1], parts[2], parts[3]
        parent_name = update.effective_user.first_name

        if itype == "T":
            for h in data["history"]:
                if h["task_id"] == iid and h["date"] == idate and h["status"] == "pending":
                    if p_act == "p_app":
                        h["status"] = "approved"
                        data["points"] += h["points"]
                        await query.edit_message_text(f"✅ Approved by {parent_name}")
                        await context.bot.send_message(SON_CHAT_ID, f"🌟 Approved: <b>{h['task_name']}</b> (+{h['points']} pts!)", parse_mode="HTML")
                    else:
                        h["status"] = "denied"
                        await query.edit_message_text(f"❌ Denied by {parent_name}")
                    break
        save_data(data)

# --- PARENT TEXT HANDLERS ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    data = load_data()

    if is_son(uid):
        if text == "☀️ Morning Missions": await show_category_tasks(update, context, "morning")
        elif text == "🌙 Evening & Study": await show_category_tasks(update, context, "evening")
        elif text == "📊 My Points": await update.message.reply_text(f"💰 Current Balance: <b>{data['points']} pts</b>", parse_mode="HTML")
        elif text == "🎁 Rewards":
            lines = [f"<b>🎁 Rewards (Balance: {data['points']} pts)</b>"]
            for r in data["rewards"]: lines.append(f"• <code>{r['id']}</code>: {r['name']} ({r['cost']} pts)")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📜 History":
            recent = data["history"][-10:]
            msg = "<b>📜 Recent Activity:</b>\n" + "\n".join([f"• {h['task_name']} ({h['status']})" for h in recent])
            await update.message.reply_text(msg if recent else "No history yet.", parse_mode="HTML")

    elif is_parent(uid):
        if text == "⚙️ Manage Tasks":
            msg = "<b>Manage Tasks:</b>\n`/addtask id|Name|Pts|HH:MM|cat`\n`/deltask id`"
            await update.message.reply_text(msg, parse_mode="HTML")
        elif text == "📈 Weekly Progress":
            await update.message.reply_text(f"💰 Total Points: {data['points']}\n🎯 Weekly Goal: {data['weekly_goal']}")
        elif text == "🔄 Reset Today":
            data["history"] = [h for h in data["history"] if h["date"] != today_str()]
            save_data(data)
            await update.message.reply_text("Today's history cleared.")

async def add_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    try:
        p = " ".join(context.args).split("|")
        data = load_data()
        # Overwrite if exists, else append
        data["tasks"] = [t for t in data["tasks"] if t["id"] != p[0]]
        data["tasks"].append({"id": p[0], "name": p[1], "points": int(p[2]), "deadline": p[3], "cat": p[4]})
        save_data(data)
        await update.message.reply_text(f"✅ Task {p[1]} saved.")
    except:
        await update.message.reply_text("Format: `/addtask homework|Maths|20|18:00|evening`", parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtask", add_task_cmd))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__": main()
