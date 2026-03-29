# ChampBot — Complete Setup Guide

A Telegram bot that turns your son's daily routine into a game — complete tasks, earn points, unlock real rewards. 🏆

---

## What the Bot Does

| Feature | Details |
|---|---|
| Daily task list | 5 activities with point values |
| Morning reminder | Bot messages son at 7 AM every day |
| Mark tasks done | Simple keyboard buttons |
| Points & balance | Tracks total points earned |
| Streak counter | Rewards consistent daily completion |
| Reward redemption | Son requests rewards, parent approves |
| Parent dashboard | Full control via Telegram |

---

## Daily Tasks (pre-configured)

| Task | Points |
|---|---|
| 📚 Homework / Studies | 20 pts |
| 🏃 Physical Exercise | 15 pts |
| 📖 Reading / Learning | 15 pts |
| 🧹 Chores / Household Tasks | 10 pts |
| 🦷 Brushing Teeth | 5 pts |
| **Daily maximum** | **65 pts** |

## Rewards (pre-configured)

| Reward | Cost |
|---|---|
| 📱 30 min extra screen time | 30 pts |
| 📱 1 hour extra screen time | 55 pts |
| 🍕 Favourite meal / treat | 80 pts |
| 🎬 Movie night pick | 100 pts |
| 💵 50 cents cash | 40 pts |
| 💵 $1.00 cash | 75 pts |
| 🎮 Full game day (weekend) | 200 pts |

---

## Step-by-Step Setup

### Step 1 — Create the Bot (5 minutes)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Give it a name, e.g. **HabitBot**
4. Give it a username ending in `bot`, e.g. **YourNameHabitBot**
5. BotFather will give you a **token** like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   **Save this — you'll need it shortly.**

---

### Step 2 — Get Your Chat IDs (5 minutes)

You and your son each need to send `/start` to the bot to find your Chat IDs.

1. Search for your bot in Telegram (the username you just created)
2. Press **Start** or send `/start`
3. The bot will reply with your Chat ID, e.g. `Your Chat ID is: 987654321`
4. **Have your son do the same** from his phone — note his Chat ID too

---

### Step 3 — Add the Code to Railway (10 minutes)

**Option A: Upload via GitHub (recommended)**

1. Create a free account at [github.com](https://github.com)
2. Create a new repository called `habitbot`
3. Upload all 5 files from this folder:
   - `bot.py`
   - `requirements.txt`
   - `railway.toml`
   - `Procfile`
   - `.env.example`
4. Go to [railway.app](https://railway.app) and sign in with GitHub
5. Click **New Project → Deploy from GitHub repo**
6. Select your `habitbot` repository

**Option B: Upload directly to Render**

1. Create a free account at [render.com](https://render.com)
2. Click **New → Background Worker**
3. Connect your GitHub repository (same steps as above)

---

### Step 4 — Set Environment Variables

In Railway (or Render), go to your project's **Variables** tab and add:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | The token from BotFather |
| `PARENT_CHAT_ID` | Your Chat ID (from Step 2) |
| `SON_CHAT_ID` | Your son's Chat ID (from Step 2) |

Railway will automatically restart the bot after you save.

---

### Step 5 — Test the Bot

**As parent:**
1. Open Telegram, find your bot
2. Send `/start` — you should see the parent control panel

**As son (from his phone):**
1. Find the same bot
2. Send `/start` — he should see his task panel with buttons

**Test the flow:**
1. Son taps **✅ Mark task done**
2. Selects a task from the list
3. Bot awards points and notifies you
4. Check **📊 My points** to see the balance

---

## Commands Reference

### Son's Commands
| Command / Button | What it does |
|---|---|
| `✅ Mark task done` | Opens task selection |
| `📊 My points` | Shows current balance |
| `📅 Today's tasks` | Lists all tasks + completion status |
| `🏆 My streak` | Shows consecutive full days |
| `🎁 Rewards` | Lists all rewards |
| `/redeem screen30` | Requests a reward (pending parent approval) |
| `📜 History` | Shows recent task completions |

### Parent's Commands
| Command / Button | What it does |
|---|---|
| `📊 Son's progress` | Full overview of points, streak, today's tasks |
| `/approve` | Approve the next pending reward request |
| `/deny` | Deny the next pending reward request (points refunded) |
| `/points +50` | Add 50 bonus points |
| `/points -20` | Deduct 20 points |
| `/addtask piano\|🎹 Piano\|15` | Add a new task |
| `/removetask piano` | Remove a task |
| `/reset` | Clear today's completed tasks |
| `📋 View all tasks` | List all tasks with point values |

---

## Customising Tasks & Rewards

### Change point values
Edit `bot.py`, find the `DEFAULT_TASKS` list near the top, and change the `"points"` values.

### Add a new task at runtime (no code edit needed)
Send this as parent in Telegram:
```
/addtask soccer|⚽ Soccer Practice|20
```

### Change the morning reminder time
In `bot.py`, find this line:
```python
job_queue.run_daily(morning_reminder, time=time(7, 0, 0))
```
Change `7, 0, 0` to your preferred time (24-hour, UTC). Railway servers run in UTC — if you're in UTC+4 (Seychelles), use `3, 0, 0` for 7 AM local time.

---

## Tips for Success

- **Start with a points review conversation** — sit with your son, explain the system, let him pick 1–2 rewards he really wants. This creates instant buy-in.
- **Approve rewards promptly** — delayed approval kills motivation. Try to approve same day.
- **Add bonus points** (`/points +10`) for exceptional effort, not just completion.
- **Celebrate streaks** — acknowledge a 7-day streak out loud, not just in the app.
- **Review and adjust** after 2 weeks — if tasks feel too easy or too hard, change the points.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot not responding | Check Railway logs; ensure `BOT_TOKEN` is set correctly |
| Wrong person getting messages | Swap `PARENT_CHAT_ID` and `SON_CHAT_ID` values |
| Points not saving | Check Railway has a persistent disk attached (free tier includes it) |
| Morning reminder not arriving | Remember Railway runs in UTC — adjust the time accordingly |

---

*ChampBot — Built with python-telegram-bot v21 · Hosted free on Railway.app* 🏆
