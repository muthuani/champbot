"""
ChampBot - The Master Version (Formatting Fixed)
Includes: Categories, Photo Proof, Penalties, Streaks, Approvals, Redemptions, and Parent Controls.
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
    return {"tasks": DEFAULT_TASKS, "rewards": DEFAULT_REWARDS, "points": 0, "history": [], "redemptions": [], "morning_streak": 0}

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
        [KeyboardButton("✅ Approve Tasks"), KeyboardButton("🎁 Approve Rewards")],
        [KeyboardButton("📋 View all tasks"), KeyboardButton("📊 Son's progress")],
        [KeyboardButton("✏️ Edit Tasks/Points"), KeyboardButton("🔄 Reset today")]
    ], resize_keyboard=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == PARENT_CHAT_ID:
        await update.message.reply_text("<b>🏆 Parent Panel Active</b>", parse_mode="HTML", reply_markup=parent_main_keyboard())
    elif chat_id == SON_CHAT_ID:
        await update.message.reply_text("<b>🏆 Welcome Champ!</b>", parse_mode="HTML", reply_markup=son_main_keyboard())
    else:
        await update.message.reply_text(f"Your Chat ID: <code>{chat_id}</code>", parse_mode="HTML")

# --- Son Task Submission Logic ---
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
        msg = f"🔔 <b>Task Approval Needed</b>\nTask: {task['name']}\nPoints: {final_pts}"
        if photo_id: await context.bot.send_photo(PARENT_CHAT_ID, photo_id, caption=msg, parse_mode="HTML")
        else: await context.bot.send_message(PARENT_CHAT_ID, msg, parse_mode="HTML")

# --- Son Reward Redemption Logic ---
async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update): return
    if not context.args:
        await update.message.reply_text("Usage: <code>/redeem [reward_id]</code>\nCheck the 🎁 Rewards button for IDs.", parse_mode="HTML")
        return
    
    reward_id = context.args[0].lower()
    data = load_data()
    reward = next((r for r in data["rewards"] if r["id"] == reward_id), None)
    
    if not reward:
        await update.message.reply_text("Reward ID not found.")
        return
    if data["points"] < reward["cost"]:
        short = reward["cost"] - data["points"]
        await update.message.reply_text(f"You need {reward['cost']} pts. You are short by {short} pts! 💪")
        return

    # Deduct points immediately, send to pending
    data["points"] -= reward["cost"]
    data.setdefault("redemptions", []).append({
        "date": today_str(), "reward_id": reward["id"], "reward_name": reward["name"],
        "cost": reward["cost"], "status": "pending"
    })
    save_data(data)
    
    await update.message.reply_text(f"🎉 Requested <b>{reward['name']}</b>! Waiting for Dad's approval.", parse_mode="HTML")
    if PARENT_CHAT_ID:
        await context.bot.send_message(PARENT_CHAT_ID, f"🎁 <b>Reward Request!</b>\nChamp wants: {reward['name']}\nCost: {reward['cost']} pts", parse_mode="HTML")

# --- Parent Approvals (Tasks & Rewards) ---
async def approve_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    pending = [h for h in data["history"] if h.get("status") == "pending"]
    if not pending:
        await update.message.reply_text("No tasks waiting! ✨")
        return
    for h in pending:
        cb_id = f"T|{h['task_id']}|{h['date']}"
        keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"app|{cb_id}"), InlineKeyboardButton("❌ Deny", callback_data=f"rej|{cb_id}")]]
        await update.message.reply_text(f"📌 <b>{h['task_name']}</b> ({h['points']} pts)", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def approve_rewards_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    pending = [r for r in data.get("redemptions", []) if r.get("status") == "pending"]
    if not pending:
        await update.message.reply_text("No rewards waiting! ✨")
        return
    for r in pending:
        cb_id = f"R|{r['reward_id']}|{r['date']}"
        keyboard = [[InlineKeyboardButton("✅ Give Reward", callback_data=f"app|{cb_id}"), InlineKeyboardButton("❌ Deny & Refund", callback_data=f"rej|{cb_id}")]]
        await update.message.reply_text(f"🎁 <b>{r['reward_name']}</b> ({r['cost']} pts)", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Format: action | type (T/R) | id | date
    parts = query.data.split("|")
    if len(parts) != 4: return
    action, item_type, item_id, item_date = parts
    
    data = load_data()
    
    if item_type == "T": # Task Approval
        for h in data["history"]:
            if h["task_id"] == item_id and h["date"] == item_date and h["status"] == "pending":
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
                    await context.bot.send_message(SON_CHAT_ID, f"🌟 Approved: <b>{h['task_name']}</b> (+{h['points']} pts!)", parse_mode="HTML")
                else:
                    h["status"] = "denied"
                    await query.edit_message_text(f"❌ Denied: {h['task_name']}")
                    await context.bot.send_message(SON_CHAT_ID, f"⚠️ Task denied: <b>{h['task_name']}</b>. Try again!", parse_mode="HTML")
                break
                
    elif item_type == "R": # Reward Approval
        for r in data.get("redemptions", []):
            if r["reward_id"] == item_id and r["date"] == item_date and r["status"] == "pending":
                if action == "app":
                    r["status"] = "approved"
                    await query.edit_message_text(f"✅ Reward given: {r['reward_name']}")
                    await context.bot.send_message(SON_CHAT_ID, f"🎉 Parent approved your reward: <b>{r['reward_name']}</b>! Enjoy! 🥳", parse_mode="HTML")
                else:
                    r["status"] = "denied"
                    data["points"] += r["cost"] # Refund points
                    await query.edit_message_text(f"❌ Denied & Refunded: {r['reward_name']}")
                    await context.bot.send_message(SON_CHAT_ID, f"❌ Reward denied: <b>{r['reward_name']}</b>. Points have been refunded.", parse_mode="HTML")
                break

    save_data(data)

# --- Parent Commands (Add/Edit Tasks & Points) ---
async def edit_points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update): return
    if not context.args:
        await update.message.reply_text("Usage: <code>/points +50</code> or <code>/points -20</code>", parse_mode="HTML")
        return
    try:
        delta = int(context.args[0])
        data = load_data()
        data["points"] = max(0, data["points"] + delta)
        save_data(data)
        sign = "+" if delta >= 0 else ""
        await update.message.reply_text(f"Points updated! New total: {data['points']} pts")
        await context.bot.send_message(SON_CHAT_ID, f"💰 Dad updated your points by {sign}{delta}! Total: {data['points']} pts")
    except ValueError:
        await update.message.reply_text("Use a number like +50 or -20.")

async def add_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update): return
    if not context.args:
        await update.message.reply_text("Usage: <code>/addtask id|Name|points</code>\nExample: <code>/addtask homework|📚 Homework|20</code>", parse_mode="HTML")
        return
    parts = " ".join(context.args).split("|")
    if len(parts) != 3:
        await update.message.reply_text("Format must be: <code>id|Name|points</code>", parse_mode="HTML")
        return
    
    t_id, t_name, t_pts = parts[0].strip(), parts[1].strip(), int(parts[2].strip())
    data = load_data()
    
    # Overwrite if ID exists (Acts as an Edit function)
    for t in data["tasks"]:
        if t["id"] == t_id:
            t["name"], t["points"] = t_name, t_pts
            save_data(data)
            await update.message.reply_text(f"✅ Task UPDATED: {t_name} ({t_pts} pts)")
            return
            
    data["tasks"].append({"id": t_id, "name": t_name, "points": t_pts})
    save_data(data)
    await update.message.reply_text(f"✅ Task ADDED: {t_name} ({t_pts} pts)")

async def remove_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update): return
    if not context.args: return
    t_id = context.args[0]
    data = load_data()
    data["tasks"] = [t for t in data["tasks"] if t["id"] != t_id]
    save_data(data)
    await update.message.reply_text(f"✅ Task <code>{t_id}</code> removed.", parse_mode="HTML")

# --- Text Handler Menu ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = load_data()
    
    # --- SON BUTTONS ---
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
                lines.append(f"{icon} <code>{r['id']}</code> - {r['name']} ({r['cost']} pts)")
            lines.append("\n<b>To claim a reward, type:</b>\n<code>/redeem id</code>\nExample: <code>/redeem cash5</code>")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📜 History":
            recent = sorted(data["history"], key=lambda h: h["date"], reverse=True)[:15]
            if not recent: await update.message.reply_text("No history yet! 💪")
            else:
                lines = ["<b>📜 Recent Activity</b>\n"]
                for h in recent:
                    status = "⏳" if h["status"] == "pending" else "✅" if h["status"] == "approved" else "❌"
                    lines.append(f"• {h['date']} | {status} {h['task_name']} ({h['points']} pts)")
                await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    # --- PARENT BUTTONS ---
    elif is_parent(update):
        if text == "✅ Approve Tasks": await approve_tasks_menu(update, context)
        elif text == "🎁 Approve Rewards": await approve_rewards_menu(update, context)
        elif text == "📋 View all tasks":
            lines = ["<b>📋 Current Tasks</b>\n<i>Use ID to edit/remove</i>\n"]
            for t in data["tasks"]: lines.append(f"• ID: <code>{t['id']}</code> | {t['name']} ({t['points']} pts)")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📊 Son's progress":
            streak = data.get("morning_streak", 0)
            pending_t = len([h for h in data["history"] if h.get("status") == "pending"])
            pending_r = len([r for r in data.get("redemptions", []) if r.get("status") == "pending"])
            await update.message.reply_text(
                f"<b>📊 Progress Report</b>\n\n"
                f"💰 Total Points: <b>{data['points']}</b>\n"
                f"🔥 Morning Streak: <b>{streak} days</b>\n"
                f"📝 Tasks Pending: <b>{pending_t}</b>\n"
                f"🎁 Rewards Pending: <b>{pending_r}</b>", 
                parse_mode="HTML"
            )
        elif text == "✏️ Edit Tasks/Points":
            msg = (
                "<b>⚙️ Parent Commands</b>\n\n"
                "<b>Edit/Add a Task:</b>\n<code>/addtask id|Name|points</code>\n"
                "<b>Remove a Task:</b>\n<code>/removetask id</code>\n\n"
                "<b>Give/Take Points directly:</b>\n<code>/points +50</code> or <code>/points -20</code>"
            )
            await update.message.reply_text(msg, parse_mode="HTML")
        elif text == "🔄 Reset today":
            data["history"] = [h for h in data["history"] if h["date"] != today_str()]
            save_data(data)
            await update.message.reply_text("✅ Today's history has been wiped clean.")

# --- Background Jobs ---
async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    if SON_CHAT_ID:
        await context.bot.send_message(SON_CHAT_ID, "🏆 <b>Good Morning!</b> Don't forget to complete and submit your morning missions before 7:10 AM! 🏫", parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("points", edit_points_cmd))
    app.add_handler(CommandHandler("addtask", add_task_cmd))
    app.add_handler(CommandHandler("removetask", remove_task_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # 03:00 UTC = 07:00 Seychelles Time
    app.job_queue.run_daily(morning_reminder, time=time(3, 0)) 
    app.run_polling()

if __name__ == "__main__": main()
