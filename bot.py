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

# --- CONFIGURATION (RAILWAY ENV VARIABLES) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SON_CHAT_ID = int(os.environ.get("SON_CHAT_ID", "0"))

# Supports comma-separated IDs: "123456789,987654321"
PARENT_IDS_RAW = os.environ.get("PARENT_IDS", "0")
PARENT_IDS = [int(i.strip()) for i in PARENT_IDS_RAW.split(",") if i.strip().isdigit()]

DATA_FILE = Path("champ_data.json")

# --- MASTER DATA MODELS ---
DEFAULT_TASKS = [
    {"id": "waking",      "name": "🌅 Waking up @ 5am",                  "points": 15, "deadline": "05:05", "cat": "morning"},
    {"id": "teeth",       "name": "🦷 Brushing teeth",                   "points": 15, "deadline": "05:15", "cat": "morning"},
    {"id": "exercise",    "name": "🏃 Morning exercise",                 "points": 15, "deadline": "06:00", "cat": "morning"},
    {"id": "toilet",      "name": "🚿 Loo & Shower",                     "points": 15, "deadline": "06:30", "cat": "morning"},
    {"id": "uniform",     "name": "👔 Ironing uniform",                  "points": 15, "deadline": "06:45", "cat": "morning"},
    {"id": "cleanliness", "name": "🧼 Apply oil/clean shoe/wash socks",  "points": 15, "deadline": "07:00", "cat": "morning"},
    {"id": "to_school",   "name": "🏫 Leave home to school by 7:10am",   "points": 15, "deadline": "07:10", "cat": "morning"},
    
    {"id": "fromschool",  "name": "🍱 Keep uniform/clean lunch box",     "points": 15, "deadline": "16:30", "cat": "evening"},
    {"id": "homework",    "name": "📚 Homework",                         "points": 15, "deadline": "18:00", "cat": "evening"},
    {"id": "v_english",   "name": "🔤 English Vocabulary",               "points": 15, "deadline": "18:30", "cat": "evening"},
    {"id": "french",      "name": "🥖 Learning French",                  "points": 15, "deadline": "19:00", "cat": "evening"},
    {"id": "w_english",   "name": "✍️ Writing English",                  "points": 15, "deadline": "19:30", "cat": "evening"},
    {"id": "maths",       "name": "🔢 Maths",                            "points": 15, "deadline": "20:00", "cat": "evening"},
    {"id": "science",     "name": "🧪 Science",                          "points": 15, "deadline": "20:30", "cat": "evening"},
    {"id": "history",     "name": "📜 History",                          "points": 15, "deadline": "21:00", "cat": "evening"},
    {"id": "geo",         "name": "🌍 Geography",                        "points": 15, "deadline": "21:00", "cat": "evening"},
    {"id": "ict",         "name": "💻 ICT",                              "points": 15, "deadline": "21:00", "cat": "evening"},
    {"id": "w_french",    "name": "📝 Writing French",                   "points": 15, "deadline": "21:00", "cat": "evening"},
    {"id": "reading",     "name": "📖 Reading 10 pages",                 "points": 15, "deadline": "21:30", "cat": "evening"},
    {"id": "ev_exercise", "name": "🚴 Evening Exercise",                 "points": 15, "deadline": "21:30", "cat": "evening"},
    {"id": "chores",      "name": "🧹 Chores / Household Tasks",         "points": 10, "deadline": "21:30", "cat": "evening"},
]

DEFAULT_REWARDS = [
    {"id": "screen30", "name": "📱 30 min extra screen time", "cost": 150},
    {"id": "screen60", "name": "📱 1 hour extra screen time", "cost": 250},
    {"id": "movie",    "name": "🎬 Favorite movie",             "cost": 450},
    {"id": "treat",    "name": "🍕 Favourite meal / treat",     "cost": 600},
    {"id": "cash5",    "name": "💵 5 SCR cash",                 "cost": 200},
    {"id": "cash10",   "name": "💵 10 SCR cash",                "cost": 350},
    {"id": "gameday",  "name": "🎮 Full game day (weekend)",    "cost": 1800},
]

def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {"tasks": DEFAULT_TASKS, "rewards": DEFAULT_REWARDS, "points": 0, "history": [], "redemptions": [], "weekly_goal": 700}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2, default=str)

# --- SECURITY HELPERS ---
def is_parent(user_id): return user_id in PARENT_IDS
def is_son(user_id): return user_id == SON_CHAT_ID
def today_str(): return datetime.now().strftime("%Y-%m-%d")

# --- KEYBOARDS ---
def son_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("☀️ Morning Missions"), KeyboardButton("🌙 Evening & Study")],
        [KeyboardButton("📊 My Points"), KeyboardButton("🎁 Rewards")],
        [KeyboardButton("📜 History"), KeyboardButton("⚖️ Rules")]
    ], resize_keyboard=True)

def parent_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⚙️ Manage Tasks"), KeyboardButton("🎡 Manage Rewards")],
        [KeyboardButton("📈 Weekly Progress"), KeyboardButton("💰 Edit Points")],
        [KeyboardButton("🔄 Reset Today")]
    ], resize_keyboard=True)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_parent(uid):
        await update.message.reply_text("<b>🏆 Parent Control Active</b>", parse_mode="HTML", reply_markup=parent_main_keyboard())
    elif is_son(uid):
        await update.message.reply_text("<b>🚀 Welcome Champ!</b>", parse_mode="HTML", reply_markup=son_main_keyboard())
    else:
        await update.message.reply_text(f"Your ID: <code>{uid}</code>\nSend this to Dad.", parse_mode="HTML")

# --- SON LOGIC: TASK SUBMISSIONS ---
async def show_category_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, cat):
    data = load_data()
    done = [h["task_id"] for h in data["history"] if h["date"] == today_str() and h["status"] != "denied"]
    tasks = [t for t in data["tasks"] if t.get("cat") == cat and t["id"] not in done]

    if not tasks:
        await update.message.reply_text("🎉 All missions complete for this category!")
        return

    buttons = []
    for t in tasks:
        try:
            d_time = datetime.strptime(t.get("deadline", "23:59"), "%H:%M")
            formatted_time = d_time.strftime("%I:%M %p")
        except ValueError:
            formatted_time = "11:59 PM"
            
        button_label = f"{t['name']} ⏰ Due: {formatted_time}"
        buttons.append([InlineKeyboardButton(button_label, callback_data=f"confirm|{t['id']}")])

    await update.message.reply_text(f"Select a {cat} mission:", reply_markup=InlineKeyboardMarkup(buttons))

# --- REDEEM COMMAND (SON) ---
async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: `/redeem [reward_id]`\nCheck the 🎁 Rewards button for IDs.", parse_mode="Markdown")
        return
    
    reward_id = context.args[0].lower()
    data = load_data()
    reward = next((r for r in data["rewards"] if r["id"] == reward_id), None)
    
    if not reward:
        await update.message.reply_text("Reward ID not found.")
        return
    if data["points"] < reward["cost"]:
        await update.message.reply_text(f"You need {reward['cost']} pts. You are short by {reward['cost'] - data['points']} pts! 💪")
        return

    data["points"] -= reward["cost"]
    data.setdefault("redemptions", []).append({
        "date": today_str(), "reward_id": reward["id"], "reward_name": reward["name"], "cost": reward["cost"], "status": "pending"
    })
    save_data(data)
    
    await update.message.reply_text(f"🎉 Requested <b>{reward['name']}</b>! Waiting for Parent approval.", parse_mode="HTML")
    
    for pid in PARENT_IDS:
        kb = [[InlineKeyboardButton("✅ Give Reward", callback_data=f"p_app|R|{reward['id']}|{today_str()}"),
               InlineKeyboardButton("❌ Deny & Refund", callback_data=f"p_rej|R|{reward['id']}|{today_str()}")]]
        await context.bot.send_message(pid, f"🎁 <b>Reward Request!</b>\nDhakshan wants: {reward['name']}\nCost: {reward['cost']} pts", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# --- CALLBACK ROUTER (HANDLES ALL BUTTON CLICKS) ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    action = parts[0]
    data = load_data()
    uid = update.effective_user.id

    if action == "confirm":
        t_id = parts[1]
        task = next((t for t in data["tasks"] if t["id"] == t_id), None)
        if not task: return
        kb = [[InlineKeyboardButton("✅ Yes, I'm Done!", callback_data=f"submit|{t_id}")],
              [InlineKeyboardButton("❌ Oops, Go Back", callback_data="cancel_sub")]]
        await query.edit_message_text(f"Confirming: <b>{task['name']}</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "submit":
        t_id = parts[1]
        task = next(t for t in data["tasks"] if t["id"] == t_id)
        
        now = datetime.now()
        try:
            d_time = datetime.strptime(task.get("deadline", "23:59"), "%H:%M").time()
            deadline_dt = now.replace(hour=d_time.hour, minute=d_time.minute, second=0, microsecond=0)
        except ValueError:
            deadline_dt = now
        
        pts = task["points"]
        status_txt = "On Time! ✅"
        
        if now > deadline_dt:
            diff_mins = (now - deadline_dt).total_seconds() / 60
            if diff_mins <= 30: 
                pts = int(pts * 0.5)
                status_txt = "Late (50%) ⚠️"
            else: 
                pts = 2
                status_txt = "Very Late (2pts) 🐢"

        data["history"].append({"date": today_str(), "task_id": t_id, "task_name": task["name"], "points": pts, "status": "pending"})
        save_data(data)
        await query.edit_message_text(f"✅ Submitted: {task['name']} ({pts} expected pts)")
        
        for pid in PARENT_IDS:
            kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"p_app|T|{t_id}|{today_str()}"),
                   InlineKeyboardButton("❌ Deny", callback_data=f"p_rej|T|{t_id}|{today_str()}")]]
            await context.bot.send_message(pid, f"🔔 <b>New Task</b>\n{task['name']}\nStatus: {status_txt}\nPoints: {pts}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "cancel_sub":
        await query.edit_message_text("Action cancelled. Use the menu below.")

    elif action.startswith("p_") and is_parent(uid):
        act, itype, iid, idate = parts[0], parts[1], parts[2], parts[3]
        parent_name = update.effective_user.first_name

        if itype == "T":
            for h in data["history"]:
                if h["task_id"] == iid and h["date"] == idate and h["status"] == "pending":
                    if act == "p_app":
                        h["status"] = "approved"
                        data["points"] += h["points"]
                        await query.edit_message_text(f"✅ Approved by {parent_name}")
                        await context.bot.send_message(SON_CHAT_ID, f"🌟 <b>{h['task_name']}</b> approved! +{h['points']} pts!", parse_mode="HTML")
                    else:
                        h["status"] = "denied"
                        await query.edit_message_text(f"❌ Denied by {parent_name}")
                    break
                    
        elif itype == "R":
            for r in data.get("redemptions", []):
                if r["reward_id"] == iid and r["date"] == idate and r["status"] == "pending":
                    if act == "p_app":
                        r["status"] = "approved"
                        await query.edit_message_text(f"✅ Reward given by {parent_name}: {r['reward_name']}")
                        await context.bot.send_message(SON_CHAT_ID, f"🎉 Reward approved: <b>{r['reward_name']}</b>! Enjoy! 🥳", parse_mode="HTML")
                    else:
                        r["status"] = "denied"
                        data["points"] += r["cost"]
                        await query.edit_message_text(f"❌ Denied & Refunded by {parent_name}: {r['reward_name']}")
                        await context.bot.send_message(SON_CHAT_ID, f"❌ Reward denied: <b>{r['reward_name']}</b>. Points refunded.", parse_mode="HTML")
                    break
        save_data(data)

# --- MAIN MENU TEXT ROUTER ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    data = load_data()

    if is_son(uid):
        if text == "☀️ Morning Missions": await show_category_tasks(update, context, "morning")
        elif text == "🌙 Evening & Study": await show_category_tasks(update, context, "evening")
        elif text == "📊 My Points": await update.message.reply_text(f"💰 Balance: <b>{data['points']} pts</b>", parse_mode="HTML")
        elif text == "🎁 Rewards":
            lines = [f"<b>🎁 Rewards (Balance: {data['points']} pts)</b>\n<i>Type /redeem [id] to claim!</i>\n"]
            for r in data["rewards"]: lines.append(f"• <code>{r['id']}</code>: {r['name']} ({r['cost']} pts)")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        elif text == "📜 History":
            hist = data["history"][-10:]
            msg = "<b>📜 Recent Activity:</b>\n" + "\n".join([f"• {h['task_name']} ({h['status']})" for h in hist])
            await update.message.reply_text(msg if hist else "No history yet.", parse_mode="HTML")
        elif text == "⚖️ Rules":
            msg = (
                "<b>⚠️ Mission Rules & Penalties</b>\n\n"
                "• <b>On Time:</b> 100% Points ✅\n"
                "• <b>Up to 30 mins late:</b> 50% Points ⚠️\n"
                "• <b>More than 30 mins late:</b> 2 Points 🐢\n\n"
                "<i>Keep an eye on the clock on your buttons, Champ!</i>"
            )
            await update.message.reply_text(msg, parse_mode="HTML")

    elif is_parent(uid):
        if text == "⚙️ Manage Tasks": 
            msg = "<b>⚙️ Task Management</b>\n<i>Adding an existing ID edits it.</i>\n\n• <b>Add/Edit:</b> `/addtask id|Name|Pts|HH:MM|cat`\n• <b>Delete:</b> `/deltask id`"
            await update.message.reply_text(msg, parse_mode="HTML")
            
        elif text == "🎡 Manage Rewards":
            msg = "<b>🎡 Reward Management</b>\n<i>Adding an existing ID edits it.</i>\n\n• <b>Add/Edit:</b> `/addreward id|Name|Cost`\n• <b>Delete:</b> `/delreward id`"
            await update.message.reply_text(msg, parse_mode="HTML")
            
        elif text == "📈 Weekly Progress": 
            goal = data.get("weekly_goal", 700)
            pts = data.get("points", 0)
            pending_t = len([h for h in data["history"] if h.get("status") == "pending"])
            pending_r = len([r for r in data.get("redemptions", []) if r.get("status") == "pending"])
            msg = (
                f"<b>📊 Dhakshan's Progress</b>\n\n"
                f"💰 Total Points: <b>{pts}</b>\n"
                f"🎯 Weekly Goal: <b>{goal}</b>\n"
                f"🚀 Remaining: <b>{max(0, goal - pts)} pts</b>\n\n"
                f"⏳ Tasks Pending Approval: <b>{pending_t}</b>\n"
                f"🎁 Rewards Pending Approval: <b>{pending_r}</b>\n\n"
                f"<i>To change the weekly goal, type:</i>\n`/setgoal 800`"
            )
            await update.message.reply_text(msg, parse_mode="HTML")
            
        elif text == "💰 Edit Points":
            msg = (
                "<b>💰 Manual Point Adjustment</b>\n\n"
                "To add or remove points instantly, type:\n"
                "• Add 50 points: `/points +50`\n"
                "• Remove 20 points: `/points -20`\n\n"
                "<i>Dhakshan will be notified automatically!</i>"
            )
            await update.message.reply_text(msg, parse_mode="HTML")
            
        elif text == "🔄 Reset Today":
            data["history"] = [h for h in data["history"] if h["date"] != today_str()]
            save_data(data)
            await update.message.reply_text("✅ Today's history has been wiped.")

# --- ADMIN CRUD COMMANDS ---
async def edit_points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Usage: `/points +50` or `/points -20`")
        return
    try:
        delta = int(context.args[0])
        data = load_data()
        data["points"] = max(0, data["points"] + delta)
        save_data(data)
        sign = "+" if delta >= 0 else ""
        await update.message.reply_text(f"✅ Points updated! New total: {data['points']} pts")
        await context.bot.send_message(SON_CHAT_ID, f"💰 A Parent updated your points by {sign}{delta}! Total: {data['points']} pts")
    except ValueError:
        await update.message.reply_text("Please use a number like +50 or -20.")

async def set_goal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    if not context.args: return
    try:
        data = load_data()
        data["weekly_goal"] = int(context.args[0])
        save_data(data)
        await update.message.reply_text(f"✅ Weekly goal set to {data['weekly_goal']} pts.")
    except: await update.message.reply_text("Format: `/setgoal 800`")

async def add_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    try:
        p = " ".join(context.args).split("|")
        data = load_data()
        data["tasks"] = [t for t in data["tasks"] if t["id"] != p[0]]
        data["tasks"].append({"id": p[0], "name": p[1], "points": int(p[2]), "deadline": p[3], "cat": p[4].lower()})
        save_data(data)
        await update.message.reply_text(f"✅ Saved Task: {p[1]}")
    except: await update.message.reply_text("Format: `/addtask id|Name|Pts|HH:MM|cat`")

async def del_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    if not context.args: return
    t_id = context.args[0]
    data = load_data()
    data["tasks"] = [t for t in data["tasks"] if t["id"] != t_id]
    save_data(data)
    await update.message.reply_text(f"✅ Task `{t_id}` deleted.", parse_mode="Markdown")

async def add_reward_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    try:
        p = " ".join(context.args).split("|")
        data = load_data()
        data["rewards"] = [r for r in data["rewards"] if r["id"] != p[0]]
        data["rewards"].append({"id": p[0], "name": p[1], "cost": int(p[2])})
        save_data(data)
        await update.message.reply_text(f"✅ Saved Reward: {p[1]}")
    except: await update.message.reply_text("Format: `/addreward id|Name|Cost`")

async def del_reward_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    if not context.args: return
    r_id = context.args[0]
    data = load_data()
    data["rewards"] = [r for r in data["rewards"] if r["id"] != r_id]
    save_data(data)
    await update.message.reply_text(f"✅ Reward `{r_id}` deleted.", parse_mode="Markdown")

# --- BACKGROUND REMINDERS ---
async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    if SON_CHAT_ID:
        await context.bot.send_message(SON_CHAT_ID, "🏆 <b>Good Morning Champ!</b> Don't forget to complete your morning missions before school! 🏫", parse_mode="HTML")

async def evening_reminder(context: ContextTypes.DEFAULT_TYPE):
    if SON_CHAT_ID:
        await context.bot.send_message(SON_CHAT_ID, "🌙 <b>Good Evening!</b> Time to knock out that homework and evening studies! 📚", parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("setgoal", set_goal_cmd))
    app.add_handler(CommandHandler("points", edit_points_cmd))
    app.add_handler(CommandHandler("addtask", add_task_cmd))
    app.add_handler(CommandHandler("deltask", del_task_cmd))
    app.add_handler(CommandHandler("addreward", add_reward_cmd))
    app.add_handler(CommandHandler("delreward", del_reward_cmd))
    
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # 02:00 UTC = 06:00 AM Seychelles Time
    app.job_queue.run_daily(morning_reminder, time=time(2, 0))
    # 13:00 UTC = 05:00 PM Seychelles Time
    app.job_queue.run_daily(evening_reminder, time=time(13, 0))
    
    app.run_polling()

if __name__ == "__main__": main()
