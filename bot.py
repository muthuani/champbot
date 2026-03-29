"""
ChampBot - Telegram bot to track daily activities and reward points
"""

import json
import os
import logging
from datetime import datetime, time
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, JobQueue
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
PARENT_CHAT_ID = int(os.environ.get("PARENT_CHAT_ID", "0"))
SON_CHAT_ID    = int(os.environ.get("SON_CHAT_ID",    "0"))
DATA_FILE      = Path("data.json")

DEFAULT_TASKS = [
    {"id": "homework", "name": "📚 Homework / Studies",      "points": 20, "emoji": "📚"},
    {"id": "exercise", "name": "🏃 Physical Exercise",        "points": 15, "emoji": "🏃"},
    {"id": "chores",   "name": "🧹 Chores / Household Tasks", "points": 10, "emoji": "🧹"},
    {"id": "reading",  "name": "📖 Reading / Learning",       "points": 15, "emoji": "📖"},
    {"id": "teeth",    "name": "🦷 Brushing Teeth",           "points": 5,  "emoji": "🦷"},
]

DEFAULT_REWARDS = [
    {"id": "screen30", "name": "📱 30 min extra screen time", "cost": 30},
    {"id": "screen60", "name": "📱 1 hour extra screen time", "cost": 55},
    {"id": "movie",    "name": "🎬 Movie night pick",         "cost": 100},
    {"id": "treat",    "name": "🍕 Favourite meal / treat",   "cost": 80},
    {"id": "cash50",   "name": "💵 50 cents cash",            "cost": 40},
    {"id": "cash100",  "name": "💵 $1.00 cash",               "cost": 75},
    {"id": "gameday",  "name": "🎮 Full game day (weekend)",  "cost": 200},
]

def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "tasks": DEFAULT_TASKS,
        "rewards": DEFAULT_REWARDS,
        "points": 0,
        "history": [],
        "redemptions": [],
        "streak": 0,
        "last_full_day": None,
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def today_completed(data):
    return [h["task_id"] for h in data["history"] if h["date"] == today_str()]

def all_tasks_done_today(data):
    done = today_completed(data)
    return all(t["id"] in done for t in data["tasks"])

def son_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Mark task done"), KeyboardButton("📊 My points")],
        [KeyboardButton("🎁 Rewards"),        KeyboardButton("📅 Today's tasks")],
        [KeyboardButton("🏆 My streak"),      KeyboardButton("📜 History")],
    ], resize_keyboard=True)

def parent_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 View all tasks"),    KeyboardButton("➕ Add task")],
        [KeyboardButton("🎁 Manage rewards"),    KeyboardButton("✏️ Edit points")],
        [KeyboardButton("📊 Son's progress"),    KeyboardButton("✅ Approve redemptions")],
        [KeyboardButton("📅 Set reminder time"), KeyboardButton("🔄 Reset today")],
    ], resize_keyboard=True)

def is_parent(update):
    return update.effective_chat.id == PARENT_CHAT_ID

def is_son(update):
    return update.effective_chat.id == SON_CHAT_ID

async def notify_parent(context, msg):
    if PARENT_CHAT_ID:
        await context.bot.send_message(PARENT_CHAT_ID, msg, parse_mode="HTML")

async def notify_son(context, msg):
    if SON_CHAT_ID:
        await context.bot.send_message(SON_CHAT_ID, msg, parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name    = update.effective_user.first_name
    if chat_id == PARENT_CHAT_ID:
        await update.message.reply_text(
            "<b>🏆 ChampBot — Parent Panel</b>\n\n"
            "Welcome back! Use the buttons below to manage "
            "tasks, rewards and track your son's progress.",
            parse_mode="HTML",
            reply_markup=parent_main_keyboard()
        )
    elif chat_id == SON_CHAT_ID:
        data = load_data()
        await update.message.reply_text(
            "<b>🏆 Welcome to ChampBot, " + name + "!</b>\n\n"
            "Complete your daily tasks, earn points and\n"
            "unlock real rewards! 🎯\n\n"
            "💰 Your balance: <b>" + str(data["points"]) + " pts</b>\n\n"
            "Tap a button below to get started, Champ! 💪",
            parse_mode="HTML",
            reply_markup=son_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "<b>🏆 ChampBot</b>\n\n"
            "Your Chat ID is: <code>" + str(chat_id) + "</code>\n\n"
            "Send this number to the parent to finish setup.",
            parse_mode="HTML"
        )

async def show_today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    done = today_completed(data)
    lines = ["<b>📅 Today's Tasks</b>\n"]
    for t in data["tasks"]:
        status = "✅" if t["id"] in done else "⬜"
        lines.append(status + " " + t["name"] + "  <i>(+" + str(t["points"]) + " pts)</i>")
    remaining = sum(t["points"] for t in data["tasks"] if t["id"] not in done)
    lines.append("\n💰 You can still earn <b>" + str(remaining) + " pts</b> today!")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def mark_done_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data    = load_data()
    done    = today_completed(data)
    pending = [t for t in data["tasks"] if t["id"] not in done]
    if not pending:
        await update.message.reply_text(
            "🎉 You've completed ALL tasks today! Amazing work!\n"
            "Total points so far: <b>" + str(data["points"]) + "</b>",
            parse_mode="HTML"
        )
        return
    buttons = [[KeyboardButton("✔ " + t["name"])] for t in pending]
    buttons.append([KeyboardButton("🔙 Back")])
    await update.message.reply_text(
        "Which task did you complete? 👇",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )

async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    text = update.message.text

    if text == "🔙 Back":
        await update.message.reply_text("OK!", reply_markup=son_main_keyboard())
        return

    if not text.startswith("✔ "):
        return

    task_name = text[2:].strip()

    # Always load fresh data to prevent stale reads
    data = load_data()
    done = today_completed(data)

    matched = next((t for t in data["tasks"] if t["name"] == task_name), None)
    if not matched:
        await update.message.reply_text(
            "Hmm, I did not recognise that task. Try again!",
            reply_markup=son_main_keyboard()
        )
        return

    # Duplicate guard — blocks multiple submissions of the same task
    if matched["id"] in done:
        await update.message.reply_text(
            "🚫 <b>" + matched["name"] + "</b> is already done today!\n"
            "No extra points — one task per day, Champ! 😄",
            parse_mode="HTML",
            reply_markup=son_main_keyboard()
        )
        return

    # Award points
    data["history"].append({
        "date":      today_str(),
        "task_id":   matched["id"],
        "task_name": matched["name"],
        "points":    matched["points"],
    })
    data["points"] += matched["points"]

    # Streak check
    streak_msg = ""
    if all_tasks_done_today(data):
        data["streak"]        = data.get("streak", 0) + 1
        data["last_full_day"] = today_str()
        streak_msg = (
            "\n\n🔥 <b>STREAK: " + str(data["streak"]) +
            " day(s) in a row!</b> Keep it up!"
        )
        await notify_parent(
            context,
            "🎉 Your son completed ALL tasks today!\n"
            "Streak: " + str(data["streak"]) + " day(s) 🔥"
        )

    save_data(data)

    await update.message.reply_text(
        matched["emoji"] + " <b>" + matched["name"] + "</b> done! ✅\n"
        "+" + str(matched["points"]) + " points awarded!\n"
        "💰 Total: <b>" + str(data["points"]) + " pts</b>" + streak_msg,
        parse_mode="HTML",
        reply_markup=son_main_keyboard()
    )
    await notify_parent(
        context,
        "✅ <b>" + matched["name"] + "</b> marked done by your son.\n"
        "Points: +" + str(matched["points"]) + " | Total: " + str(data["points"])
    )

async def show_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data         = load_data()
    done_today   = today_completed(data)
    earned_today = sum(h["points"] for h in data["history"] if h["date"] == today_str())
    await update.message.reply_text(
        "<b>💰 Your Points</b>\n\n"
        "🏦 Total balance: <b>" + str(data["points"]) + " pts</b>\n"
        "📅 Earned today: <b>" + str(earned_today) + " pts</b>\n"
        "✅ Tasks done today: " + str(len(done_today)) + " / " + str(len(data["tasks"])),
        parse_mode="HTML"
    )

async def show_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data   = load_data()
    streak = data.get("streak", 0)
    emojis = "🔥" * min(streak, 10) if streak else "❄️"
    if streak == 0:
        note = "Complete all tasks today to start your streak!"
    elif streak < 3:
        note = "Good start, Champ! Keep going!"
    elif streak < 7:
        note = "You are on a roll! 🚀 Real champions do not stop!"
    else:
        note = "Incredible consistency! You are a true Champ! 🏆💪"
    await update.message.reply_text(
        "<b>🏆 Your Streak</b>\n\n"
        + emojis + "\n"
        "<b>" + str(streak) + " day(s)</b> with all tasks completed!\n\n"
        + note,
        parse_mode="HTML"
    )

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data   = load_data()
    recent = sorted(data["history"], key=lambda h: h["date"], reverse=True)[:15]
    if not recent:
        await update.message.reply_text("No history yet. Complete some tasks! 💪")
        return
    lines = ["<b>📜 Recent Activity</b>\n"]
    for h in recent:
        lines.append(
            "• " + h["date"] + "  " + h["task_name"] +
            "  <i>+" + str(h["points"]) + " pts</i>"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def show_rewards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data  = load_data()
    pts   = data["points"]
    lines = ["<b>🎁 Rewards</b>  (You have <b>" + str(pts) + " pts</b>)\n"]
    for r in data["rewards"]:
        icon = "✅" if pts >= r["cost"] else "🔒"
        lines.append(icon + " " + r["name"] + "  — <b>" + str(r["cost"]) + " pts</b>")
    lines.append(
        "\nTo redeem, type:\n"
        "<code>/redeem reward_id</code>\n"
        "e.g. <code>/redeem screen30</code>"
    )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/redeem reward_id</code>\n"
            "See IDs with the 🎁 Rewards button.",
            parse_mode="HTML"
        )
        return
    reward_id = context.args[0].lower()
    data      = load_data()
    reward    = next((r for r in data["rewards"] if r["id"] == reward_id), None)
    if not reward:
        await update.message.reply_text("I do not know that reward ID. Check the 🎁 Rewards list.")
        return
    if data["points"] < reward["cost"]:
        short = reward["cost"] - data["points"]
        await update.message.reply_text(
            "You need <b>" + str(reward["cost"]) + " pts</b> for this reward.\n"
            "You are <b>" + str(short) + " pts</b> short. Keep going! 💪",
            parse_mode="HTML"
        )
        return
    data["points"] -= reward["cost"]
    data["redemptions"].append({
        "date":        today_str(),
        "reward_id":   reward["id"],
        "reward_name": reward["name"],
        "cost":        reward["cost"],
        "approved":    False,
    })
    save_data(data)
    await update.message.reply_text(
        "🎉 Redemption request sent!\n\n"
        "<b>" + reward["name"] + "</b> — " + str(reward["cost"]) + " pts deducted.\n"
        "Remaining: <b>" + str(data["points"]) + " pts</b>\n\n"
        "Waiting for parent to approve! ⏳",
        parse_mode="HTML"
    )
    await notify_parent(
        context,
        "🎁 <b>Redemption request!</b>\n\n"
        "Your son wants: <b>" + reward["name"] + "</b>\n"
        "Cost: " + str(reward["cost"]) + " pts\n\n"
        "Use /approve or /deny to respond."
    )

async def parent_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data    = load_data()
    done    = today_completed(data)
    earned  = sum(h["points"] for h in data["history"] if h["date"] == today_str())
    pending = [r for r in data["redemptions"] if not r["approved"]]
    lines = [
        "<b>📊 Son's Progress</b>\n",
        "💰 Total points: <b>" + str(data["points"]) + "</b>",
        "🔥 Current streak: <b>" + str(data.get("streak", 0)) + " day(s)</b>",
        "📅 Tasks done today: <b>" + str(len(done)) + " / " + str(len(data["tasks"])) + "</b>",
        "🏆 Points earned today: <b>" + str(earned) + "</b>",
    ]
    if pending:
        lines.append("\n⚠️ Pending redemptions: <b>" + str(len(pending)) + "</b>")
        for r in pending:
            lines.append(
                "  • " + r["reward_name"] + " (" + str(r["cost"]) + " pts) — " + r["date"]
            )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def approve_redemption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data    = load_data()
    pending = [r for r in data["redemptions"] if not r["approved"]]
    if not pending:
        await update.message.reply_text("No pending redemptions! ✅")
        return
    r = pending[0]
    r["approved"] = True
    save_data(data)
    await update.message.reply_text(
        "✅ Approved: <b>" + r["reward_name"] + "</b>", parse_mode="HTML"
    )
    await notify_son(
        context,
        "🎉 Parent approved your reward!\n\n"
        "<b>" + r["reward_name"] + "</b> is yours! Enjoy! 🥳"
    )

async def deny_redemption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data    = load_data()
    pending = [r for r in data["redemptions"] if not r["approved"]]
    if not pending:
        await update.message.reply_text("No pending redemptions.")
        return
    r = pending[0]
    data["redemptions"].remove(r)
    data["points"] += r["cost"]
    save_data(data)
    await update.message.reply_text(
        "❌ Denied: <b>" + r["reward_name"] + "</b>. Points refunded.", parse_mode="HTML"
    )
    await notify_son(
        context,
        "❌ Your redemption for <b>" + r["reward_name"] + "</b> was not approved.\n"
        "Your points have been refunded. Keep trying! 💪"
    )

async def edit_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/points +50</code> or <code>/points -20</code>",
            parse_mode="HTML"
        )
        return
    try:
        delta = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Please use a number like <code>+50</code> or <code>-20</code>",
            parse_mode="HTML"
        )
        return
    data           = load_data()
    data["points"] = max(0, data["points"] + delta)
    save_data(data)
    sign = "+" if delta >= 0 else ""
    await update.message.reply_text(
        "Points updated: " + sign + str(delta) + "\n"
        "New total: <b>" + str(data["points"]) + "</b>",
        parse_mode="HTML"
    )
    await notify_son(
        context,
        "💰 Your parent updated your points: " + sign + str(delta) + "\n"
        "New total: <b>" + str(data["points"]) + " pts</b>"
    )

async def parent_view_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data  = load_data()
    lines = ["<b>📋 Current Tasks</b>\n"]
    for t in data["tasks"]:
        lines.append(
            "• <code>" + t["id"] + "</code>  " + t["name"] + "  — " + str(t["points"]) + " pts"
        )
    lines.append("\nTo add: <code>/addtask id|Name|points</code>")
    lines.append("To remove: <code>/removetask id</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/addtask id|Name|points</code>\n"
            "e.g. <code>/addtask piano|🎹 Piano Practice|15</code>",
            parse_mode="HTML"
        )
        return
    parts = " ".join(context.args).split("|")
    if len(parts) != 3:
        await update.message.reply_text(
            "Format must be: <code>id|Name|points</code>", parse_mode="HTML"
        )
        return
    task_id = parts[0].strip()
    name    = parts[1].strip()
    pts     = parts[2].strip()
    data    = load_data()
    if any(t["id"] == task_id for t in data["tasks"]):
        await update.message.reply_text(
            "Task ID <code>" + task_id + "</code> already exists.", parse_mode="HTML"
        )
        return
    data["tasks"].append({"id": task_id, "name": name, "points": int(pts), "emoji": "⭐"})
    save_data(data)
    await update.message.reply_text(
        "✅ Task added: <b>" + name + "</b> (" + pts + " pts)", parse_mode="HTML"
    )

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/removetask id</code>", parse_mode="HTML"
        )
        return
    task_id = context.args[0]
    data    = load_data()
    before  = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) == before:
        await update.message.reply_text(
            "Task <code>" + task_id + "</code> not found.", parse_mode="HTML"
        )
        return
    save_data(data)
    await update.message.reply_text(
        "✅ Task <code>" + task_id + "</code> removed.", parse_mode="HTML"
    )

async def reset_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data            = load_data()
    data["history"] = [h for h in data["history"] if h["date"] != today_str()]
    save_data(data)
    await update.message.reply_text("✅ Today's completions have been reset.")

async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    data       = load_data()
    tasks_text = "\n".join(
        "⬜ " + t["name"] + "  (+" + str(t["points"]) + " pts)"
        for t in data["tasks"]
    )
    if SON_CHAT_ID:
        await context.bot.send_message(
            SON_CHAT_ID,
            "🏆 <b>Good morning, Champ!</b>\n\n"
            "Here are today's missions:\n\n" + tasks_text + "\n\n"
            "Complete them all for a full streak day! 🔥\n"
            "Tap 'Mark task done' each time you finish one. You've got this! 💪",
            parse_mode="HTML"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if is_son(update):
        if text.startswith("✔ "):
            await handle_task_selection(update, context)
        elif text == "✅ Mark task done":
            await mark_done_prompt(update, context)
        elif text == "📊 My points":
            await show_points(update, context)
        elif text == "🎁 Rewards":
            await show_rewards(update, context)
        elif text == "📅 Today's tasks":
            await show_today_tasks(update, context)
        elif text == "🏆 My streak":
            await show_streak(update, context)
        elif text == "📜 History":
            await show_history(update, context)
        elif text == "🔙 Back":
            await update.message.reply_text("OK!", reply_markup=son_main_keyboard())

    elif is_parent(update):
        if text == "📋 View all tasks":
            await parent_view_tasks(update, context)
        elif text == "📊 Son's progress":
            await parent_progress(update, context)
        elif text == "✅ Approve redemptions":
            await approve_redemption(update, context)
        elif text == "✏️ Edit points":
            await update.message.reply_text(
                "Use <code>/points +50</code> or <code>/points -20</code> to adjust points.",
                parse_mode="HTML"
            )
        elif text == "🔄 Reset today":
            await reset_today(update, context)
        elif text == "🎁 Manage rewards":
            data  = load_data()
            lines = ["<b>🎁 Current Rewards</b>\n"]
            for r in data["rewards"]:
                lines.append(
                    "• <code>" + r["id"] + "</code>  " + r["name"] +
                    "  — " + str(r["cost"]) + " pts"
                )
            lines.append("\nTo add: <code>/addreward id|Name|cost</code>")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("redeem",     redeem))
    app.add_handler(CommandHandler("approve",    approve_redemption))
    app.add_handler(CommandHandler("deny",       deny_redemption))
    app.add_handler(CommandHandler("points",     edit_points))
    app.add_handler(CommandHandler("addtask",    add_task))
    app.add_handler(CommandHandler("removetask", remove_task))
    app.add_handler(CommandHandler("tasks",      parent_view_tasks))
    app.add_handler(CommandHandler("progress",   parent_progress))
    app.add_handler(CommandHandler("reset",      reset_today))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Morning reminder — 03:00 UTC = 07:00 Seychelles time (UTC+4)
    job_queue: JobQueue = app.job_queue
    job_queue.run_daily(morning_reminder, time=time(3, 0, 0))

    logger.info("ChampBot is running! 🏆")
    app.run_polling()

if __name__ == "__main__":
    main()
