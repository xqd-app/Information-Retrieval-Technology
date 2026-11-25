# 🌅 Daily News Briefing Telegram Bot

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![Telegram](https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/solid_news_briefing_bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Deployed on Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com)

An autonomous, zero-hardware AI agent pipeline that aggregates, deduplicates, and synthesizes multi-source RSS news feeds across **AI, Web3/Blockchain, Macro Economics, and Global Politics** — then delivers a dense, Markdown-formatted briefing directly to a Telegram channel every day at **8:00 PM EST**.

---

## 🏗️ System Architecture

The pipeline runs fully serverless via a decoupled micro-automation loop:

```
[ cron-job.org ]          ← Daily 8:00 PM EST trigger ping
       │
       ▼  Secure HTTP POST
[ Render Cloud Instance ] ← Reads encrypted env vars → Pulls multi-source RSS feeds
       │
       ▼  Unified JSON payload
[ Gemini 2.5 Flash API ]  ← Cleans, deduplicates, and contextualizes into Markdown
       │
       ▼  HTTPS POST
[ Telegram Bot API ]      ← Delivers curated briefing to @solid_news_briefing_bot
```

### Key Technical Decisions

- **Code-first abstraction** — Built in pure Python instead of node-based platforms (e.g. n8n) for ultra-fast cold starts and a zero-dollar operating footprint.
- **Intelligent deduplication** — Uses `gemini-2.5-flash` to consolidate multi-outlet coverage of the same story into single definitive summaries, stripping clickbait in the process.
- **Hardened secret management (DevSecOps)** — All credentials are isolated out of version control into native container environment variables. Nothing sensitive ever touches the repo.

---

## 📁 Repository Structure

```
├── app.py              # Flask server + automated pipeline controller
├── requirements.txt    # Pinned environment dependencies
├── .gitignore          # Ensures .env is never committed
└── README.md           # This file
```

---

## 🛠️ Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Solidx74/Daily-News-Briefing-Telegram-Bot.git
cd Daily-News-Briefing-Telegram-Bot
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure your secrets

Create a `.env` file in the project root:

```env
TELEGRAM_TOKEN="your_bot_api_token"
TELEGRAM_CHAT_ID="your_chat_id"
GEMINI_API_KEY="your_google_ai_studio_key"
```

> ⚠️ **Security note:** `.gitignore` is pre-configured to exclude `.env`. Never commit this file.

### 4. Run locally

```bash
python app.py
```

Then trigger the pipeline manually by sending a request to:

```
http://127.0.0.1:5000/trigger
```

You can use your browser, cURL, or any HTTP client.

---

## 🚀 Cloud Deployment (Render + cron-job.org)

### Step 1 — Deploy to Render

1. Create a free account at [render.com](https://render.com).
2. Create a **New Web Service** and connect your GitHub repository.
3. Set the following build configuration:

   | Field | Value |
   |---|---|
   | Language | Python |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn app:app` |
   | Instance Type | Free |

### Step 2 — Add environment variables

In the Render dashboard, go to **Environment** and add:

```
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID
GEMINI_API_KEY
```

### Step 3 — Schedule the daily trigger

1. Create a free account at [cron-job.org](https://cron-job.org).
2. Create a new cron job pointing to your Render URL:
   ```
   https://your-render-app-url.onrender.com/trigger
   ```
3. Set the schedule to **06:00 AM (Asia/Dhaka)** — this maps exactly to 8:00 PM EST.

---

## 📜 License

Distributed under the [MIT License](LICENSE).

---

<p align="center">Built and maintained by <a href="https://github.com/Solidx74">Solidx74</a></p>
