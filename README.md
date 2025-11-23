# 🔫 GunsArizona Bot

Automatically monitors GunsArizona.com for specific firearms and sends Telegram notifications.

## Features
- Scans every 15 minutes for new listings
- Filters by keywords (Daniel Defense, Glock 19, Glock 43x, Sig P365 variants)
- Sends formatted Telegram alerts with price, location, description
- Remembers sent ads to avoid duplicates

## Running on GitHub Actions (24/7, Free)

This bot runs automatically on GitHub Actions. No server needed!

### Setup Instructions

#### 1. Create GitHub Repository
1. Go to [GitHub.com](https://github.com) and create a new repository
2. Name it `gun-bot` (or whatever you prefer)
3. Make it **Private** (important!)

#### 2. Push Code to GitHub
Open terminal in this folder and run:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/gun-bot.git
git push -u origin main
```

#### 3. Set Up Secrets
1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add these 3 secrets:

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token (from config.json) |
| `TELEGRAM_CHAT_ID` | Your chat ID (from config.json) |
| `PAT_TOKEN` | Create a Personal Access Token (see below) |

**Creating PAT_TOKEN:**
1. Go to GitHub Settings (your profile, not repo) → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name like "Gun Bot"
4. Check the `repo` scope
5. Click Generate and copy the token
6. Paste it as the `PAT_TOKEN` secret

#### 4. Enable Actions
1. Go to the **Actions** tab in your repo
2. Click "I understand my workflows, go ahead and enable them"
3. The bot will now run every 15 minutes!

#### 5. Manual Test
Click **Actions** → **Gun Bot Scanner** → **Run workflow** to test immediately.

## Local Testing
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install requests beautifulsoup4 schedule
python main.py
```

## How It Works
- GitHub Actions runs `run_once.py` every 15 minutes
- The script checks for new listings matching your keywords
- Any new matches trigger a Telegram notification
- The `seen_ads.json` file is automatically committed back to the repo
