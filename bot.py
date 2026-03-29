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

# ── Configuration ─────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
PARENT_CHAT_ID = int(os.environ.get("PARENT_CHAT_ID", "0"))   # Fill after first /start
SON_CHAT_ID    = int(os.environ.get("SON_CHAT_ID",    "0"))   # Fill after first /start

DATA_FILE = Path("data.json")

# ── Default tasks with point values ───────────────────────────────────────────

DEFAULT_TASKS = [
    {"id": "homework",   "name": "📚 Homework / Studies",        "points": 20, "emoji": "📚"},
    {"id": "exercise",   "name": "🏃 Physical Exercise",          "points": 15, "emoji": "🏃"},
    {"id": "chores",     "name": "🧹 Chores / Household Tasks",   "points": 10, "emoji": "🧹"},
    {"id": "reading",    "name": "📖 Reading / Learning",         "points": 15, "emoji": "📖"},
    {"id": "teeth",      "name": "🦷 Brushing Teeth",             "points": 5,  "emoji": "🦷"},
]

# ── Default rewards ────────────────────────────────────────────────────────────

DEFAULT_REWARDS = [
    {"id": "screen30",  "name": "📱 30 min extra screen time",   "cost": 30},
    {"id": "screen60",  "name": "📱 1 hour extra screen time",   "cost": 55},
    {"id": "movie",     "name": "🎬 Movie night pick",           "cost": 100},
    {"id": "treat",     "name": "🍕 Favourite meal / treat",     "cost": 80},
    {"id": "cash50",    "name": "💵 50 cents cash",              "cost": 40},
    {"id": "cash100",   "name": "💵 $1.00 cash",                 "cost": 75},
    {"id": "gameday",   "name": "🎮 Full game day (weekend)",    "cost": 200},
]

# ── Data helpers ───────────────────────────────────────────────────────────────

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "tasks": DEFAULT_TASKS,
        "rewards": DEFAULT_REWARDS,
        "points": 0,
        "history": [],          # list of {date, task_id, points, note}
        "redemptions": [],      # list of {date, reward_id, cost, approved}
        "streak": 0,
        "last_full_day": None,
    }

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def today_completed(data: dict) -> list[str]:
    """Return list of task IDs completed today."""
    return [h["task_id"] for h in data["history"] if h["date"] == today_str()]

def all_tasks_done_today(data: dict) -> bool:
    done = today_completed(data)
    return all(t["id"] in done for t in data["tasks"])

# ── Keyboards ──────────────────────────────────────────────────────────────────

def son_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Mark task done"),  KeyboardButton("📊 My points")],
        [KeyboardButton("🎁 Rewards"),         KeyboardButton("📅 Today's tasks")],
        [KeyboardButton("🏆 My streak"),       KeyboardButton("📜 History")],
    ], resize_keyboard=True)

def parent_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📋 View all tasks"),   KeyboardButton("➕ Add task")],
        [KeyboardButton("🎁 Manage rewards"),   KeyboardButton("✏️ Edit points")],
        [KeyboardButton("📊 Son's progress"),   KeyboardButton("✅ Approve redemptions")],
        [KeyboardButton("📅 Set reminder time"),KeyboardButton("🔄 Reset today")],
    ], resize_keyboard=True)

# ── Shared utilities ───────────────────────────────────────────────────────────

def is_parent(update: Update) -> bool:
    return update.effective_chat.id == PARENT_CHAT_ID

def is_son(update: Update) -> bool:
    return update.effective_chat.id == SON_CHAT_ID

async def notify_parent(context: ContextTypes.DEFAULT_TYPE, msg: str):
    if PARENT_CHAT_ID:
        await context.bot.send_message(PARENT_CHAT_ID, msg, parse_mode="HTML")

async def notify_son(context: ContextTypes.DEFAULT_TYPE, msg: str):
    if SON_CHAT_ID:
        await context.bot.send_message(SON_CHAT_ID, msg, parse_mode="HTML")

# ── /start ─────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name

    if chat_id == PARENT_CHAT_ID:
        await update.message.reply_text(
            f"👋 Welcome back, <b>{name}</b>!\n\n"
            f"🏆 <b>ChampBot — Parent Panel</b>\n\n"
            "Use the buttons below to manage tasks, rewards and track your son's progress.",
            parse_mode="HTML",
            reply_markup=parent_main_keyboard()
        )
    elif chat_id == SON_CHAT_ID:
        data = load_data()
        pts = data["points"]
        await update.message.reply_text(
            f"🏆 <b>Hey {name}, welcome to ChampBot!</b>\n\n"
            f"Complete your daily tasks → earn points → unlock real rewards! 🎯\n\n"
            f"💰 Your balance: <b>{pts} pts</b>\n\n"
            "Tap a button below to get started, Champ! 💪",
            parse_mode="HTML",
            reply_markup=son_main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"🏆 <b>ChampBot</b>\n\n"
            f"Your Chat ID is: <code>{chat_id}</code>\n\n"
            "Send this to the parent to finish setup.",
            parse_mode="HTML"
        )

# ── Son: today's task list ─────────────────────────────────────────────────────

async def show_today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    done = today_completed(data)

    lines = ["<b>📅 Today's Tasks</b>\n"]
    for t in data["tasks"]:
        status = "✅" if t["id"] in done else "⬜"
        lines.append(f"{status} {t['name']}  <i>(+{t['points']} pts)</i>")

    remaining = sum(t["points"] for t in data["tasks"] if t["id"] not in done)
    lines.append(f"\n💰 You can still earn <b>{remaining} pts</b> today!")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── Son: mark task done ────────────────────────────────────────────────────────

async def mark_done_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    done = today_completed(data)

    pending = [t for t in data["tasks"] if t["id"] not in done]
    if not pending:
        await update.message.reply_text(
            "🎉 You've completed ALL tasks today! Amazing work!\n"
            f"Total points so far: <b>{data['points']}</b>",
            parse_mode="HTML"
        )
        return

    buttons = [[KeyboardButton(f"✔ {t['name']}")] for t in pending]
    buttons.append([KeyboardButton("🔙 Back")])
    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(
        "Which task did you complete? 👇", reply_markup=markup
    )
    context.user_data["awaiting_task"] = True

async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when son taps a task button."""
    if not is_son(update):
        return
    text = update.message.text

    if text == "🔙 Back":
        context.user_data["awaiting_task"] = False
        await update.message.reply_text("OK!", reply_markup=son_main_keyboard())
        return

    if not text.startswith("✔ "):
        return

    task_name = text[2:].strip()
    data = load_data()
    done = today_completed(data)

    matched = next((t for t in data["tasks"] if t["name"] == task_name), None)
    if not matched:
        await update.message.reply_text("Hmm, I didn't recognise that task. Try again!")
        return

    if matched["id"] in done:
        await update.message.reply_text(
            f"🚫 <b>{matched['name']}</b> is already done today!
"
            "No extra points — one task per day, Champ! 😄",
            parse_mode="HTML",
            reply_markup=son_main_keyboard()
        )
        return

    # Double-check with a fresh load to prevent race conditions
    data = load_data()
    done = today_completed(data)
    if matched["id"] in done:
        await update.message.reply_text(
            f"🚫 Already logged! No duplicate points allowed. 😄",
            reply_markup=son_main_keyboard()
        )
        return

    # Award points
    data["history"].append({
        "date": today_str(),
        "task_id": matched["id"],
        "task_name": matched["name"],
        "points": matched["points"],
    })
    data["points"] += matched["points"]

    # Streak check
    if all_tasks_done_today(data):
        data["streak"] = data.get("streak", 0) + 1
        data["last_full_day"] = today_str()
        streak_msg = (
            f"\n\n🔥 <b>STREAK: {data['streak']} day(s) in a row!</b> Keep it up!"
        )
        await notify_parent(
            context,
            f"🎉 Your son completed ALL tasks today!\n"
            f"Streak: {data['streak']} day(s) 🔥"
        )
    else:
        streak_msg = ""

    save_data(data)

    context.user_data["awaiting_task"] = False
    await update.message.reply_text(
        f"{matched['emoji']} <b>{matched['name']}</b> done! ✅\n"
        f"+{matched['points']} points awarded!\n"
        f"💰 Total: <b>{data['points']} pts</b>{streak_msg}",
        parse_mode="HTML",
        reply_markup=son_main_keyboard()
    )
    await notify_parent(
        context,
        f"✅ <b>{matched['name']}</b> marked done by your son.\n"
        f"Points today: +{matched['points']} | Total: {data['points']}"
    )

# ── Son: points balance ────────────────────────────────────────────────────────

async def show_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    done_today = today_completed(data)
    earned_today = sum(
        h["points"] for h in data["history"] if h["date"] == today_str()
    )
    await update.message.reply_text(
        f"<b>💰 Your Points</b>\n\n"
        f"🏦 Total balance: <b>{data['points']} pts</b>\n"
        f"📅 Earned today: <b>{earned_today} pts</b>\n"
        f"✅ Tasks done today: {len(done_today)} / {len(data['tasks'])}",
        parse_mode="HTML"
    )

# ── Son: streak ────────────────────────────────────────────────────────────────

async def show_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    streak = data.get("streak", 0)
    emojis = "🔥" * min(streak, 10) if streak else "❄️"
    msg = (
        f"<b>🏆 Your Streak</b>\n\n"
        f"{emojis}\n"
        f"<b>{streak} day(s)</b> with all tasks completed!\n\n"
    )
    if streak == 0:
        msg += "Complete all tasks today to start your ChampBot streak!"
    elif streak < 3:
        msg += "Good start, Champ! Keep going!"
    elif streak < 7:
        msg += "You're on a roll! 🚀 Real champions don't stop!"
    else:
        msg += "Incredible consistency! You're a true Champ! 🏆💪"
    await update.message.reply_text(msg, parse_mode="HTML")

# ── Son: history ───────────────────────────────────────────────────────────────

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    recent = sorted(data["history"], key=lambda h: h["date"], reverse=True)[:15]
    if not recent:
        await update.message.reply_text("No history yet. Complete some tasks! 💪")
        return
    lines = ["<b>📜 Recent Activity</b>\n"]
    for h in recent:
        lines.append(f"• {h['date']}  {h['task_name']}  <i>+{h['points']} pts</i>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── Son: rewards list ──────────────────────────────────────────────────────────

async def show_rewards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    data = load_data()
    pts = data["points"]
    lines = [f"<b>🎁 Rewards</b>  (You have <b>{pts} pts</b>)\n"]
    for r in data["rewards"]:
        affordable = "✅" if pts >= r["cost"] else "🔒"
        lines.append(f"{affordable} {r['name']}  — <b>{r['cost']} pts</b>")
    lines.append(
        "\nTo redeem, type:\n<code>/redeem &lt;reward name&gt;</code>\n"
        "e.g. <code>/redeem screen30</code>"
    )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── Son: redeem reward ─────────────────────────────────────────────────────────

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/redeem &lt;reward_id&gt;</code>\n"
            "See reward IDs with the 🎁 Rewards button.",
            parse_mode="HTML"
        )
        return

    reward_id = context.args[0].lower()
    data = load_data()
    reward = next((r for r in data["rewards"] if r["id"] == reward_id), None)

    if not reward:
        await update.message.reply_text(
            "I don't know that reward. Check the 🎁 Rewards list for the correct ID."
        )
        return

    if data["points"] < reward["cost"]:
        short = reward["cost"] - data["points"]
        await update.message.reply_text(
            f"You need <b>{reward['cost']} pts</b> for this reward.\n"
            f"You're <b>{short} pts</b> short. Keep going! 💪",
            parse_mode="HTML"
        )
        return

    # Deduct and log (pending parent approval)
    data["points"] -= reward["cost"]
    data["redemptions"].append({
        "date": today_str(),
        "reward_id": reward["id"],
        "reward_name": reward["name"],
        "cost": reward["cost"],
        "approved": False,
    })
    save_data(data)

    await update.message.reply_text(
        f"🎉 Redemption request sent!\n\n"
        f"<b>{reward['name']}</b> — {reward['cost']} pts deducted.\n"
        f"Remaining: <b>{data['points']} pts</b>\n\n"
        "Waiting for parent to approve! ⏳",
        parse_mode="HTML"
    )
    await notify_parent(
        context,
        f"🎁 <b>Redemption request!</b>\n\n"
        f"Your son wants: <b>{reward['name']}</b>\n"
        f"Cost: {reward['cost']} pts\n\n"
        f"Use /approve or /deny to respond."
    )

# ── Parent: view progress ──────────────────────────────────────────────────────

async def parent_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data = load_data()
    done = today_completed(data)
    earned_today = sum(h["points"] for h in data["history"] if h["date"] == today_str())
    pending_redemptions = [r for r in data["redemptions"] if not r["approved"]]

    lines = [
        "<b>📊 Son's Progress</b>\n",
        f"💰 Total points: <b>{data['points']}</b>",
        f"🔥 Current streak: <b>{data.get('streak', 0)} day(s)</b>",
        f"📅 Tasks done today: <b>{len(done)} / {len(data['tasks'])}</b>",
        f"🏆 Points earned today: <b>{earned_today}</b>",
    ]
    if pending_redemptions:
        lines.append(f"\n⚠️ Pending redemptions: <b>{len(pending_redemptions)}</b>")
        for r in pending_redemptions:
            lines.append(f"  • {r['reward_name']} ({r['cost']} pts) — {r['date']}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── Parent: approve/deny redemption ───────────────────────────────────────────

async def approve_redemption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data = load_data()
    pending = [r for r in data["redemptions"] if not r["approved"]]
    if not pending:
        await update.message.reply_text("No pending redemptions! ✅")
        return
    r = pending[0]
    r["approved"] = True
    save_data(data)
    await update.message.reply_text(
        f"✅ Approved: <b>{r['reward_name']}</b>", parse_mode="HTML"
    )
    await notify_son(
        context,
        f"🎉 Parent approved your reward!\n\n<b>{r['reward_name']}</b> is yours! Enjoy! 🥳"
    )

async def deny_redemption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data = load_data()
    pending = [r for r in data["redemptions"] if not r["approved"]]
    if not pending:
        await update.message.reply_text("No pending redemptions.")
        return
    r = pending[0]
    data["redemptions"].remove(r)
    data["points"] += r["cost"]   # refund
    save_data(data)
    await update.message.reply_text(
        f"❌ Denied: <b>{r['reward_name']}</b>. Points refunded.", parse_mode="HTML"
    )
    await notify_son(
        context,
        f"❌ Your redemption for <b>{r['reward_name']}</b> was not approved this time.\n"
        "Your points have been refunded. Keep trying! 💪"
    )

# ── Parent: edit points manually ───────────────────────────────────────────────

async def edit_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /points +50  or  /points -20"""
    if not is_parent(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: <code>/points +50</code> or <code>/points -30</code>", parse_mode="HTML")
        return
    try:
        delta = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please use a number like <code>+50</code> or <code>-20</code>", parse_mode="HTML")
        return
    data = load_data()
    data["points"] = max(0, data["points"] + delta)
    save_data(data)
    sign = "+" if delta >= 0 else ""
    await update.message.reply_text(
        f"Points updated: {sign}{delta}\nNew total: <b>{data['points']}</b>",
        parse_mode="HTML"
    )
    await notify_son(
        context,
        f"💰 Your parent updated your points: {sign}{delta}\n"
        f"New total: <b>{data['points']} pts</b>"
    )

# ── Parent: view tasks ─────────────────────────────────────────────────────────

async def parent_view_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data = load_data()
    lines = ["<b>📋 Current Tasks</b>\n"]
    for t in data["tasks"]:
        lines.append(f"• <code>{t['id']}</code>  {t['name']}  — {t['points']} pts")
    lines.append("\nTo add: <code>/addtask id|Name|points</code>")
    lines.append("To remove: <code>/removetask id</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /addtask piano|🎹 Piano Practice|15"""
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
        await update.message.reply_text("Format: <code>id|Name|points</code>", parse_mode="HTML")
        return
    task_id, name, pts = parts[0].strip(), parts[1].strip(), parts[2].strip()
    data = load_data()
    if any(t["id"] == task_id for t in data["tasks"]):
        await update.message.reply_text(f"Task ID <code>{task_id}</code> already exists.", parse_mode="HTML")
        return
    data["tasks"].append({"id": task_id, "name": name, "points": int(pts), "emoji": "⭐"})
    save_data(data)
    await update.message.reply_text(f"✅ Task added: <b>{name}</b> ({pts} pts)", parse_mode="HTML")

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: <code>/removetask id</code>", parse_mode="HTML")
        return
    task_id = context.args[0]
    data = load_data()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) == before:
        await update.message.reply_text(f"Task <code>{task_id}</code> not found.", parse_mode="HTML")
        return
    save_data(data)
    await update.message.reply_text(f"✅ Task <code>{task_id}</code> removed.", parse_mode="HTML")

# ── Parent: reset today ────────────────────────────────────────────────────────

async def reset_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update):
        return
    data = load_data()
    data["history"] = [h for h in data["history"] if h["date"] != today_str()]
    save_data(data)
    await update.message.reply_text("✅ Today's completions have been reset.")

# ── Scheduled morning reminder ─────────────────────────────────────────────────

async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    tasks_text = "\n".join(
        f"⬜ {t['name']}  (+{t['points']} pts)" for t in data["tasks"]
    )
    if SON_CHAT_ID:
        await context.bot.send_message(
            SON_CHAT_ID,
            f"🏆 <b>Good morning, Champ!</b>\n\nHere are today's missions:\n\n{tasks_text}\n\n"
            "Complete them all for a full streak day! 🔥\n"
            "Tap '✅ Mark task done' each time you finish one. You've got this! 💪",
            parse_mode="HTML"
        )

# ── Message router ─────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Son button handlers
    if is_son(update):
        if text.startswith("✔ "):
            await handle_task_selection(update, context)
            return
        if text == "✅ Mark task done":
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
            context.user_data["awaiting_task"] = False
            await update.message.reply_text("OK!", reply_markup=son_main_keyboard())

    # Parent button handlers
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
            data = load_data()
            lines = ["<b>🎁 Current Rewards</b>\n"]
            for r in data["rewards"]:
                lines.append(f"• <code>{r['id']}</code>  {r['name']}  — {r['cost']} pts")
            lines.append("\nTo add: <code>/addreward id|Name|cost</code>")
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
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

    # Text messages (keyboard buttons)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduled morning reminder at 7:00 AM daily
    job_queue: JobQueue = app.job_queue
    job_queue.run_daily(morning_reminder, time=time(7, 0, 0))

    logger.info("ChampBot is running! 🏆")
    app.run_polling()

if __name__ == "__main__":
    main()
