# Free 24/7 Discord Bot Hosting Guide

## Option 1: Render.com (EASIEST - Recommended)

### Step 1: Prepare Your Files

1. **Create a `requirements.txt` file:**
```txt
discord.py>=2.0.0
python-dotenv
```

2. **Create a `.gitignore` file:**
```
.env
__pycache__/
*.pyc
```

3. **Make sure your bot code uses environment variables** (already done in improved_discord_bot.py)

### Step 2: Upload to GitHub

1. Create a GitHub account if you don't have one
2. Create a new repository (can be private)
3. Upload these files:
   - `improved_discord_bot.py` (rename to `bot.py` for simplicity)
   - `requirements.txt`
   - `.gitignore`
   - DO NOT upload `.env` file!

### Step 3: Deploy on Render

1. Go to https://render.com and sign up (free)
2. Click "New +" → "Background Worker"
3. Connect your GitHub repository
4. Configure:
   - **Name:** discord-bot (or any name)
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. Click "Advanced" → Add Environment Variable:
   - **Key:** `DISCORD_BOT_TOKEN`
   - **Value:** Your bot token
6. Click "Create Background Worker"

✅ Your bot will now run 24/7 for free!

---

## Option 2: Railway.app (Good Alternative)

### Setup:
1. Go to https://railway.app
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your bot repository
5. Add environment variable: `DISCORD_BOT_TOKEN`
6. Railway auto-detects Python and runs it!

**Note:** Railway gives $5/month free credit. Should be enough for a simple bot.

---

## Option 3: Replit (For Beginners)

### Setup:
1. Go to https://replit.com
2. Create a new Python Repl
3. Upload your bot code
4. Add `DISCORD_BOT_TOKEN` in "Secrets" (lock icon)
5. Click Run

**Important:** Free Replit repls sleep after inactivity. To keep it awake:
- Use UptimeRobot (https://uptimerobot.com) to ping your repl every 5 minutes
- Or upgrade to Replit's paid plan

---

## Option 4: Oracle Cloud (FREE FOREVER - Advanced)

This is truly free forever but requires more setup:

### Requirements:
- Oracle Cloud account
- Basic Linux knowledge
- SSH client

### Setup Steps:
1. Create Oracle Cloud account (requires credit card for verification, but won't charge)
2. Create an "Always Free" ARM-based compute instance (Ubuntu)
3. SSH into the server
4. Install Python and dependencies:
```bash
sudo apt update
sudo apt install python3 python3-pip git -y
```
5. Clone your GitHub repo or upload files
6. Install requirements:
```bash
pip3 install -r requirements.txt
```
7. Create a systemd service to run bot on startup:
```bash
sudo nano /etc/systemd/system/discord-bot.service
```

Add this:
```ini
[Unit]
Description=Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/discord-bot
Environment="DISCORD_BOT_TOKEN=your_token_here"
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

8. Enable and start:
```bash
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
```

✅ Bot runs 24/7 forever for free!

---

## Quick Comparison

| Platform | Free? | Easy? | 24/7? | Best For |
|----------|-------|-------|-------|----------|
| **Render.com** | Yes | ⭐⭐⭐⭐⭐ | Yes | Beginners |
| **Railway.app** | $5/mo credit | ⭐⭐⭐⭐⭐ | Yes | Quick setup |
| **Replit** | Yes* | ⭐⭐⭐⭐ | With tricks | Learning |
| **Oracle Cloud** | Yes (forever) | ⭐⭐ | Yes | Advanced users |

---

## My Recommendation

**For you:** Start with **Render.com**
- Completely free
- Super easy setup
- Runs 24/7 reliably
- Takes 5-10 minutes to set up

If you need help with any of these, let me know which one you want to use!
