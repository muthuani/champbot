import json
import os
import logging
import random
from datetime import datetime, time
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- AI SETUP (Groq - Free, no credit card required) ---
try:
    from groq import Groq as GroqClient
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    if GROQ_API_KEY:
        groq_client = GroqClient(api_key=GROQ_API_KEY)
        GROQ_MODEL = "llama-3.3-70b-versatile"  # Free tier, ~500k tokens/day
        ai_model = True  # Flag: AI is available
    else:
        groq_client = None
        ai_model = None
except ImportError:
    groq_client = None
    ai_model = None

async def groq_generate(prompt: str) -> str:
    """Call Groq API asynchronously."""
    import asyncio
    loop = asyncio.get_event_loop()
    def _call():
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    return await loop.run_in_executor(None, _call)

# --- LOGGING ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION (RAILWAY ENV VARIABLES) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SON_CHAT_ID = int(os.environ.get("SON_CHAT_ID", "0"))
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

CONGRATS_MSGS = [
    "Amazing work! Keep crushing it! 🔥", "You're on fire today, Champ! 🌟",
    "That's how champions do it! 💪", "Superstar move right there! ⭐",
    "Nailed it! Keep going! 🏆", "Brilliant effort, Rajkumar! 🎯",
]

def is_quota_error(e): return "429" in str(e).lower() or "quota" in str(e).lower() or "rate" in str(e).lower()

async def notify_parents_quota(context):
    for pid in PARENT_IDS:
        try:
            await context.bot.send_message(pid, "⚠️ <b>Bot Alert: AI Quota Exceeded</b>\nThe Groq free tier rate limit was briefly exceeded. This auto-resets.", parse_mode="HTML")
        except: pass

def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {"tasks": DEFAULT_TASKS, "rewards": DEFAULT_REWARDS, "points": 0, "history": [], "redemptions": [], "weekly_goal": 700, "current_quiz": ""}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2, default=str)

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

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_parent(uid):
        await update.message.reply_text("<b>🏆 Parent Control Active</b>", parse_mode="HTML", reply_markup=parent_main_keyboard())
    elif is_son(uid):
        msg = (
            "<b>🚀 Welcome Champ!</b>\n\n"
            "<i>Here are your AI Superpowers:</i>\n"
            "• <code>/tutor [question]</code> - For homework help\n"
            "• <code>/write_en [text]</code> - Check English writing\n"
            "• <code>/write_fr [text]</code> - Check French writing\n"
            "• <code>/quiz</code> - Get a fun logic/trivia question\n"
            "• <code>/answer [guess]</code> - Give your quiz answer\n\n"
            "<i>Or just chat with me to log tasks!</i>"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=son_main_keyboard())
    else:
        await update.message.reply_text(f"Your ID: <code>{uid}</code>", parse_mode="HTML")

# --- AI TUTOR (GENERAL) ---
async def ai_tutor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not ai_model: return await update.message.reply_text("AI Tutor is offline. Dad needs to add the API Key!")
    question = " ".join(context.args)
    if not question: return await update.message.reply_text("What do you need help with? Example: `/tutor What is photosynthesis?`")
    
    await update.message.reply_text("🧠 Thinking...")
    prompt = f"You are a helpful tutor for Rajkumar. He asks: '{question}'. Guide him conceptually. Use plain text only."
    try:
        response = await groq_generate(prompt)
        await update.message.reply_text(f"👨‍🏫 Tutor:\n\n{response}")
    except Exception as e:
        logger.error(f"Tutor Error: {e}")
        if is_quota_error(e):
            await update.message.reply_text("🤖 My brain needs a rest — try again later! 😊")
            await notify_parents_quota(context)
        else: await update.message.reply_text("Oops, something went wrong! Ask Mom or Dad for help. 😊")

# --- AI WRITING TUTORS ---
async def write_en_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not ai_model: return await update.message.reply_text("AI Tutor is offline.")
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("What did you write? Example: `/write_en I goed to the store.`")
    
    await update.message.reply_text("📝 Checking your English...")
    prompt = f"You are an encouraging English writing tutor for a student named Rajkumar. He wrote: '{text}'. Correct any grammar or spelling mistakes, explain what he did wrong in a friendly way, and suggest a better way to write it. Do NOT use Markdown formatting. Use plain text only."
    try:
        response = await groq_generate(prompt)
        await update.message.reply_text(f"📝 English Tutor:\n\n{response}")
    except Exception as e:
        logger.error(f"Write EN Error: {e}")
        await update.message.reply_text("Oops, my brain is taking a nap. Try again later! 😊")

async def write_fr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not ai_model: return await update.message.reply_text("AI Tutor is offline.")
    text = " ".join(context.args)
    if not text: return await update.message.reply_text("What did you write? Example: `/write_fr Je suis contente.`")
    
    await update.message.reply_text("🥖 Checking your French...")
    prompt = f"You are an encouraging French writing tutor for a student named Rajkumar. He wrote: '{text}'. Correct any grammar or spelling mistakes, explain the corrections in English (so he understands the rules), and provide the correct French version. Do NOT use Markdown formatting. Use plain text only."
    try:
        response = await groq_generate(prompt)
        await update.message.reply_text(f"🥖 French Tutor:\n\n{response}")
    except Exception as e:
        logger.error(f"Write FR Error: {e}")
        await update.message.reply_text("Oops, my brain is taking a nap. Try again later! 😊")

# --- AI QUIZ MASTER ---
async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not ai_model: return await update.message.reply_text("AI is offline.")

    await update.message.reply_text("🎲 Cooking up a fun question for you...")
    prompt = "Generate a fun, engaging General Knowledge or Logic puzzle suitable for a smart kid named Rajkumar. Ask ONLY the question. Keep it brief. Use plain text only."

    try:
        question = await groq_generate(prompt)
        data = load_data()
        data["current_quiz"] = question
        save_data(data)

        msg = f"🧠 <b>Quiz Time!</b>\n\n{question}\n\n👉 <i>Type <code>/answer [your guess]</code> to see if you are right!</i>"
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Quiz Error: {e}")
        await update.message.reply_text("Oops, my brain is taking a nap. Try again later! 😊")

async def answer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not ai_model: return await update.message.reply_text("AI is offline.")

    data = load_data()
    current_quiz = data.get("current_quiz", "")
    if not current_quiz:
        return await update.message.reply_text("I haven't asked you a question yet! Type `/quiz` to get one.")

    user_answer = " ".join(context.args)
    if not user_answer:
        return await update.message.reply_text("You forgot to type your answer! Example: `/answer Paris`")

    await update.message.reply_text("🤔 Let's see if you got it right...")
    prompt = f"You asked Rajkumar this question: '{current_quiz}'. He answered: '{user_answer}'. Tell him if he is correct or not in a fun, encouraging way, and explain the true answer. Use plain text only."

    try:
        response = await groq_generate(prompt)
        await update.message.reply_text(f"🎯 Result:\n\n{response}")
        
        # Clear the quiz so he can ask for a new one
        data["current_quiz"] = ""
        save_data(data)
    except Exception as e:
        logger.error(f"Answer Error: {e}")
        await update.message.reply_text("Oops, I got confused. Try your answer again! 😊")

# --- SMART PROOF (FALLBACK TO BUTTONS FOR GROQ) ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    await update.message.reply_text("📸 Great proof photo! Which mission did you just complete? Pick it below 👇")
    cat = "morning" if datetime.now().hour < 13 else "evening"
    data = load_data()
    done = [h["task_id"] for h in data["history"] if h["date"] == today_str() and h["status"] != "denied"]
    tasks = [t for t in data["tasks"] if t.get("cat") == cat and t["id"] not in done]
    if not tasks:
        other_cat = "evening" if cat == "morning" else "morning"
        tasks = [t for t in data["tasks"] if t.get("cat") == other_cat and t["id"] not in done]
    if not tasks: return await update.message.reply_text("🎉 All missions are already completed today!")
    
    buttons = []
    for t in tasks:
        try: ft = datetime.strptime(t.get("deadline", "23:59"), "%H:%M").strftime("%I:%M %p")
        except ValueError: ft = "11:59 PM"
        buttons.append([InlineKeyboardButton(f"{t['name']} ⏰ {ft}", callback_data=f"confirm|{t['id']}")])
    await update.message.reply_text("Select your mission:", reply_markup=InlineKeyboardMarkup(buttons))

# --- REDEEM COMMAND (SON) ---
async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_son(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("Usage: `/redeem [reward_id]`", parse_mode="Markdown")
    reward_id = context.args[0].lower()
    data = load_data()
    reward = next((r for r in data["rewards"] if r["id"] == reward_id), None)
    if not reward: return await update.message.reply_text("Reward ID not found.")
    if data["points"] < reward["cost"]: return await update.message.reply_text(f"You need {reward['cost']} pts!")
    
    data["points"] -= reward["cost"]
    data.setdefault("redemptions", []).append({
        "date": today_str(), "reward_id": reward["id"], "reward_name": reward["name"], "cost": reward["cost"], "status": "pending"
    })
    save_data(data)
    await update.message.reply_text(f"🎉 Requested <b>{reward['name']}</b>! Waiting for Parent approval.", parse_mode="HTML")
    
    for pid in PARENT_IDS:
        kb = [[InlineKeyboardButton("✅ Give Reward", callback_data=f"p_app|R|{reward['id']}|{today_str()}"), InlineKeyboardButton("❌ Deny & Refund", callback_data=f"p_rej|R|{reward['id']}|{today_str()}")]]
        try: await context.bot.send_message(pid, f"🎁 <b>Reward Request!</b>\nRajkumar wants: {reward['name']}\nCost: {reward['cost']} pts", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        except: pass

# --- MENU BUTTONS & NLP LOGGER ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    data = load_data()

    if text == "☀️ Morning Missions" and is_son(uid): await show_category_tasks(update, context, "morning")
    elif text == "🌙 Evening & Study" and is_son(uid): await show_category_tasks(update, context, "evening")
    elif text == "📊 My Points" and is_son(uid): await update.message.reply_text(f"💰 Balance: <b>{data['points']} pts</b>", parse_mode="HTML")
    elif text == "🎁 Rewards" and is_son(uid):
        lines = [f"<b>🎁 Rewards (Balance: {data['points']} pts)</b>\n<i>Type /redeem [id] to claim!</i>\n"]
        for r in data["rewards"]: lines.append(f"• <code>{r['id']}</code>: {r['name']} ({r['cost']} pts)")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    elif text == "📜 History" and is_son(uid):
        hist = data["history"][-10:]
        msg = "<b>📜 Recent Activity:</b>\n" + "\n".join([f"• {h['task_name']} ({h['status']})" for h in hist])
        await update.message.reply_text(msg if hist else "No history yet.", parse_mode="HTML")
    elif text == "⚖️ Rules" and is_son(uid):
        msg = "<b>⚠️ Mission Rules</b>\n• <b>On Time:</b> 100% Points ✅\n• <b>Up to 30 mins late:</b> 50% Points ⚠️\n• <b>Very late:</b> 2 Points 🐢"
        await update.message.reply_text(msg, parse_mode="HTML")
        
    elif text == "⚙️ Manage Tasks" and is_parent(uid):
        msg = "<b>⚙️ Task Management</b>\n\nNo tasks currently exist." if not data["tasks"] else "<b>⚙️ Task Management</b>\n\n<b>Current Tasks:</b>\n" + "".join([f"• <code>{t['id']}</code>: {t['name']} - <b>{t['points']} pts</b>\n" for t in data["tasks"]])
        kb = [[InlineKeyboardButton("➕ Add New Task", callback_data="tsk_add")],
              [InlineKeyboardButton("✏️ Edit Task", callback_data="tsk_edit"), InlineKeyboardButton("🗑️ Delete Task", callback_data="tsk_del")],
              [InlineKeyboardButton("📜 Task Archive", callback_data="tsk_archive")]]
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        
    elif text == "🎡 Manage Rewards" and is_parent(uid):
        msg = "<b>🎡 Reward Management</b>\n\nNo rewards currently exist." if not data["rewards"] else "<b>🎡 Reward Management</b>\n\n<b>Current Rewards:</b>\n" + "".join([f"• <code>{r['id']}</code>: {r['name']} - <b>{r['cost']} pts</b>\n" for r in data["rewards"]])
        kb = [[InlineKeyboardButton("➕ Add New Reward", callback_data="rew_add")],
              [InlineKeyboardButton("✏️ Edit Reward", callback_data="rew_edit"), InlineKeyboardButton("🗑️ Delete Reward", callback_data="rew_del")],
              [InlineKeyboardButton("📜 Reward Archive", callback_data="rew_archive")]]
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        
    elif text == "📈 Weekly Progress" and is_parent(uid): 
        goal, pts = data.get("weekly_goal", 700), data.get("points", 0)
        pending_t = len([h for h in data["history"] if h.get("status") == "pending"])
        pending_r = len([r for r in data.get("redemptions", []) if r.get("status") == "pending"])
        msg = f"<b>📊 Rajkumar's Progress</b>\n\n💰 Total Points: <b>{pts}</b>\n🎯 Weekly Goal: <b>{goal}</b>\n🚀 Remaining: <b>{max(0, goal - pts)} pts</b>\n\n⏳ Tasks Pending Approval: <b>{pending_t}</b>\n🎁 Rewards Pending Approval: <b>{pending_r}</b>\n\n<i>To change the weekly goal, type:</i> `/setgoal 800`"
        await update.message.reply_text(msg, parse_mode="HTML")
        
    elif text == "💰 Edit Points" and is_parent(uid):
        await update.message.reply_text("<b>💰 Manual Point Adjustment</b>\n\nType:\n• `/points +50`\n• `/points -20`\n\n<i>Rajkumar will be notified automatically!</i>", parse_mode="HTML")
        
    elif text == "🔄 Reset Today" and is_parent(uid):
        data["history"] = [h for h in data["history"] if h["date"] != today_str()]
        save_data(data)
        await update.message.reply_text("✅ Today's history has been wiped.")
        
    elif is_son(uid) and ai_model:
        await update.message.reply_text("🤖 Translating your message...")
        task_list = [{"id": t["id"], "name": t["name"]} for t in data["tasks"]]
        prompt = f"Rajkumar just said: '{text}'. Based on this text, which task IDs did he complete? Available tasks: {task_list}. Reply ONLY with a comma-separated list of IDs (e.g., waking, teeth). Do NOT use quotes or extra words. If none match, reply NONE."
        try:
            response = await groq_generate(prompt)
            clean_text = response.replace("'", "").replace('"', '').replace('`', '').replace('*', '').replace('\n', '').strip()
            detected_ids = [i.strip().lower() for i in clean_text.split(",") if i.strip() and i.strip().lower() != "none"]
            matched = [t for t in data["tasks"] if t["id"].lower() in detected_ids]
            if matched:
                for t in matched:
                    kb = [[InlineKeyboardButton("✅ Confirm", callback_data=f"submit|{t['id']}"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_sub")]]
                    await update.message.reply_text(f"Did you complete: <b>{t['name']}</b>?", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
            else: await update.message.reply_text(f"I thought you meant '{clean_text}', but I couldn't match it. Try using the menu buttons! 🎯")
        except Exception as e:
            logger.error(f"AI Logger Error: {e}")
            if is_quota_error(e):
                await update.message.reply_text("🤖 My brain is full! Use the menu buttons instead.")
                await notify_parents_quota(context)
            else: await update.message.reply_text("I couldn't understand that. Try the menu buttons! 🎯")

# --- UI & CALLBACK LOGIC ---
async def show_category_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, cat):
    data = load_data()
    done = [h["task_id"] for h in data["history"] if h["date"] == today_str() and h["status"] != "denied"]
    tasks = [t for t in data["tasks"] if t.get("cat") == cat and t["id"] not in done]
    if not tasks: return await update.message.reply_text("🎉 All missions complete for this category!")
    buttons = []
    for t in tasks:
        try: ft = datetime.strptime(t.get("deadline", "23:59"), "%H:%M").strftime("%I:%M %p")
        except ValueError: ft = "11:59 PM"
        buttons.append([InlineKeyboardButton(f"{t['name']} ⏰ {ft}", callback_data=f"confirm|{t['id']}")])
    await update.message.reply_text(f"Select a {cat} mission:", reply_markup=InlineKeyboardMarkup(buttons))

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")
    action = parts[0]
    data = load_data()
    uid = update.effective_user.id

    if action == "cancel_sub":
        try: await query.message.delete()
        except: await query.edit_message_text("❌ Cancelled.")
        return

    # --- REWARD MENUS ---
    elif action == "rew_add":
        await query.edit_message_text("<b>➕ Add a New Reward</b>\n\nTap to copy and send:\n<code>/addreward id|Name|Cost</code>", parse_mode="HTML")
    elif action == "rew_edit":
        if not data["rewards"]: return await query.edit_message_text("No rewards to edit.")
        kb = [[InlineKeyboardButton(f"✏️ {r['name']}", callback_data=f"editr|{r['id']}")] for r in data["rewards"]] + [[InlineKeyboardButton("🔙 Cancel", callback_data="cancel_sub")]]
        await query.edit_message_text("Select a reward to edit:", reply_markup=InlineKeyboardMarkup(kb))
    elif action == "editr":
        r = next((r for r in data["rewards"] if r["id"] == parts[1]), None)
        if r: await query.edit_message_text(f"<b>✏️ Edit: {r['name']}</b>\n\nTap to copy and edit:\n<code>/addreward {r['id']}|{r['name']}|{r['cost']}</code>", parse_mode="HTML")
    elif action == "rew_del":
        if not data["rewards"]: return await query.edit_message_text("No rewards to delete.")
        kb = [[InlineKeyboardButton(f"❌ {r['name']}", callback_data=f"delr|{r['id']}")] for r in data["rewards"]] + [[InlineKeyboardButton("🔙 Cancel", callback_data="cancel_sub")]]
        await query.edit_message_text("Select a reward to delete:", reply_markup=InlineKeyboardMarkup(kb))
    elif action == "delr":
        data["rewards"] = [r for r in data["rewards"] if r["id"] != parts[1]]
        save_data(data)
        await query.edit_message_text("✅ Reward deleted.", parse_mode="HTML")
    elif action == "rew_archive":
        hist = [r for r in data.get("redemptions", []) if r.get("status") in ["approved", "denied"]][-10:]
        msg = "<b>📜 Reward Archive:</b>\n\n" + ("\n".join([f"{'✅' if r['status']=='approved' else '❌'} {r['reward_name']} ({r['cost']} pts)" for r in hist]) if hist else "No history.")
        await query.edit_message_text(msg, parse_mode="HTML")

    # --- TASK MENUS ---
    elif action == "tsk_add":
        await query.edit_message_text("<b>➕ Add Task</b>\n\nTap to copy and send:\n<code>/addtask id|Name|Pts|HH:MM|morning</code>", parse_mode="HTML")
    elif action == "tsk_edit":
        if not data["tasks"]: return await query.edit_message_text("No tasks to edit.")
        kb = [[InlineKeyboardButton(f"✏️ {t['name']}", callback_data=f"editt|{t['id']}")] for t in data["tasks"]] + [[InlineKeyboardButton("🔙 Cancel", callback_data="cancel_sub")]]
        await query.edit_message_text("Select a task to edit:", reply_markup=InlineKeyboardMarkup(kb))
    elif action == "editt":
        t = next((t for t in data["tasks"] if t["id"] == parts[1]), None)
        if t: await query.edit_message_text(f"<b>✏️ Edit: {t['name']}</b>\n\nTap to copy and edit:\n<code>/addtask {t['id']}|{t['name']}|{t['points']}|{t.get('deadline','23:59')}|{t.get('cat','evening')}</code>", parse_mode="HTML")
    elif action == "tsk_del":
        if not data["tasks"]: return await query.edit_message_text("No tasks to delete.")
        kb = [[InlineKeyboardButton(f"❌ {t['name']}", callback_data=f"delt|{t['id']}")] for t in data["tasks"]] + [[InlineKeyboardButton("🔙 Cancel", callback_data="cancel_sub")]]
        await query.edit_message_text("Select a task to delete:", reply_markup=InlineKeyboardMarkup(kb))
    elif action == "delt":
        data["tasks"] = [t for t in data["tasks"] if t["id"] != parts[1]]
        save_data(data)
        await query.edit_message_text("✅ Task deleted.", parse_mode="HTML")
    elif action == "tsk_archive":
        hist = data.get("history", [])[-15:]
        msg = "<b>📜 Task Archive:</b>\n\n" + ("\n".join([f"{'✅' if h['status']=='approved' else '❌' if h['status']=='denied' else '⏳'} {h['task_name']} ({h['points']} pts)" for h in hist]) if hist else "No history.")
        await query.edit_message_text(msg, parse_mode="HTML")

    # --- TASK SUBMISSION & APPROVAL ---
    elif action == "confirm":
        t = next((t for t in data["tasks"] if t["id"] == parts[1]), None)
        kb = [[InlineKeyboardButton("✅ Yes, I'm Done!", callback_data=f"submit|{parts[1]}")], [InlineKeyboardButton("❌ Oops, Go Back", callback_data="cancel_sub")]]
        await query.edit_message_text(f"Confirming: <b>{t['name']}</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "submit":
        t = next(t for t in data["tasks"] if t["id"] == parts[1])
        now = datetime.now()
        try:
            dt = datetime.strptime(t.get("deadline", "23:59"), "%H:%M").time()
            deadline_dt = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
        except ValueError: deadline_dt = now
        
        pts, status_txt = t["points"], "On Time! ✅"
        if now > deadline_dt:
            if (now - deadline_dt).total_seconds() / 60 <= 30: pts, status_txt = int(pts * 0.5), "Late (50%) ⚠️"
            else: pts, status_txt = 2, "Very Late (2pts) 🐢"

        data["history"].append({"date": today_str(), "task_id": parts[1], "task_name": t["name"], "points": pts, "status": "pending"})
        save_data(data)
        await query.edit_message_text(f"✅ Submitted: {t['name']} ({pts} pts)")
        
        for pid in PARENT_IDS:
            kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"p_app|T|{parts[1]}|{today_str()}"), InlineKeyboardButton("❌ Deny", callback_data=f"p_rej|T|{parts[1]}|{today_str()}")]]
            try: await context.bot.send_message(pid, f"🔔 <b>New Task</b>\n{t['name']}\nStatus: {status_txt}\nPoints: {pts}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
            except: pass

    elif action.startswith("p_") and is_parent(uid):
        act, itype, iid, idate = parts[0], parts[1], parts[2], parts[3]
        parent_name = update.effective_user.first_name

        if itype == "T":
            task_found = False
            for h in data["history"]:
                if h["task_id"] == iid and h["date"] == idate:
                    if h["status"] == "pending":
                        task_found = True
                        if act == "p_app":
                            h["status"] = "approved"
                            data["points"] += h["points"]
                            await query.edit_message_text(f"✅ Approved by {parent_name}")
                            try:
                                prompt = f"Write a fast, 1-sentence fun congratulatory message for a kid named Rajkumar for completing his task: '{h['task_name']}'. Include an emoji."
                                custom_msg = await groq_generate(prompt) if ai_model else random.choice(CONGRATS_MSGS)
                            except: custom_msg = random.choice(CONGRATS_MSGS)
                            await context.bot.send_message(SON_CHAT_ID, f"🌟 <b>{h['task_name']}</b> approved! +{h['points']} pts!\n\n🤖 <i>{custom_msg}</i>", parse_mode="HTML")
                        else:
                            h["status"] = "denied"
                            await query.edit_message_text(f"❌ Denied by {parent_name}")
                        
                        # Notify the OTHER parent immediately
                        for pid in PARENT_IDS:
                            if pid != uid:
                                try: await context.bot.send_message(pid, f"ℹ️ <b>{h['task_name']}</b> was {h['status']} by {parent_name}.", parse_mode="HTML")
                                except: pass
                        break
                    else:
                        await query.edit_message_text(f"⚠️ This task was already {h['status']}.")
                        return
            if not task_found: await query.edit_message_text("⚠️ This task could not be found or was already processed.")
                        
        elif itype == "R":
            reward_found = False
            for r in data.get("redemptions", []):
                if r["reward_id"] == iid and r["date"] == idate:
                    if r["status"] == "pending":
                        reward_found = True
                        if act == "p_app":
                            r["status"] = "approved"
                            await query.edit_message_text(f"✅ Reward given by {parent_name}: {r['reward_name']}")
                            await context.bot.send_message(SON_CHAT_ID, f"🎉 Reward approved: <b>{r['reward_name']}</b>! Enjoy! 🥳", parse_mode="HTML")
                        else:
                            r["status"] = "denied"
                            data["points"] += r["cost"]
                            await query.edit_message_text(f"❌ Denied & Refunded by {parent_name}: {r['reward_name']}")
                            await context.bot.send_message(SON_CHAT_ID, f"❌ Reward denied: <b>{r['reward_name']}</b>. Points refunded.", parse_mode="HTML")
                        
                        # Notify the OTHER parent immediately
                        for pid in PARENT_IDS:
                            if pid != uid:
                                try: await context.bot.send_message(pid, f"ℹ️ Reward request for <b>{r['reward_name']}</b> was {r['status']} by {parent_name}.", parse_mode="HTML")
                                except: pass
                        break
                    else:
                        await query.edit_message_text(f"⚠️ This reward request was already {r['status']}.")
                        return
            if not reward_found: await query.edit_message_text("⚠️ This reward request could not be found or was already processed.")
        save_data(data)

# --- ADMIN CRUD COMMANDS ---
async def edit_points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_parent(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("Usage: `/points +50` or `/points -20`")
    try:
        delta = int(context.args[0])
        data = load_data()
        data["points"] = max(0, data["points"] + delta)
        save_data(data)
        await update.message.reply_text(f"✅ Points updated! New total: {data['points']} pts")
        await context.bot.send_message(SON_CHAT_ID, f"💰 A Parent updated your points by {'+' if delta >= 0 else ''}{delta}! Total: {data['points']} pts")
    except ValueError: await update.message.reply_text("Please use a number like +50 or -20.")

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

# --- BACKGROUND REMINDERS ---
async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    if SON_CHAT_ID: await context.bot.send_message(SON_CHAT_ID, "🏆 <b>Good Morning Champ!</b> Don't forget your morning missions! 🏫", parse_mode="HTML")

async def evening_reminder(context: ContextTypes.DEFAULT_TYPE):
    if SON_CHAT_ID: await context.bot.send_message(SON_CHAT_ID, "🌙 <b>Good Evening!</b> Time to knock out that homework! 📚", parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tutor", ai_tutor_cmd))
    app.add_handler(CommandHandler("write_en", write_en_cmd))
    app.add_handler(CommandHandler("write_fr", write_fr_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("answer", answer_cmd))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("setgoal", set_goal_cmd))
    app.add_handler(CommandHandler("points", edit_points_cmd))
    app.add_handler(CommandHandler("addtask", add_task_cmd))
    app.add_handler(CommandHandler("addreward", add_reward_cmd))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_daily(morning_reminder, time=time(2, 0))
    app.job_queue.run_daily(evening_reminder, time=time(13, 0))
    app.run_polling()

if __name__ == "__main__": main()
