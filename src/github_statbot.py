import requests
import re
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import os
from dotenv import load_dotenv
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Flask app
app = Flask(__name__)

# Environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # E.g. https://yourdomain.com
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # Optional, to increase GitHub API rate limits

if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise ValueError("TELEGRAM_TOKEN and WEBHOOK_URL must be set in environment variables.")

# Validation for GitHub username
def is_valid_github_username(username: str) -> bool:
    pattern = r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$"
    return bool(re.match(pattern, username))

# Telegram handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} started the bot.")
    await update.message.reply_text(
        "👋 Welcome to GitHub StatBot!\n\n"
        "Send me a GitHub username to get profile and repo info.\n"
        "Commands:\n"
        "/help - How to use\n"
        "/repos - List user repositories\n"
        "/quit - Stop interaction"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To use this bot:\n"
        "1. Send a GitHub username (e.g. torvalds).\n"
        "2. Get profile info and repos.\n"
        "Commands:\n"
        "/repos - List repositories\n"
        "/quit - Stop interaction"
    )

async def quit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Thanks for using GitHub StatBot! Bye 👋")

async def get_github_user_info(username: str):
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    url = f"https://api.github.com/users/{username}"
    logger.info(f"Fetching GitHub user info for {username}")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return (
            f"👤 GitHub User: {data.get('login')}\n"
            f"Name: {data.get('name') or 'N/A'}\n"
            f"Bio: {data.get('bio') or 'N/A'}\n"
            f"Location: {data.get('location') or 'N/A'}\n"
            f"Public Repos: {data.get('public_repos')}\n"
            f"Followers: {data.get('followers')}\n"
            f"Following: {data.get('following')}\n"
            f"Profile URL: {data.get('html_url')}\n"
        )
    elif response.status_code == 404:
        return "❌ GitHub user not found."
    else:
        return f"❌ Error fetching data (status {response.status_code})"

async def get_github_repos(username: str):
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    url = f"https://api.github.com/users/{username}/repos?sort=updated"
    logger.info(f"Fetching repos for {username}")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        repos = response.json()
        if not repos:
            return "User has no public repositories."
        # Limit to 10 repos for message length
        repos_list = []
        for repo in repos[:10]:
            repos_list.append(
                f"🔸 [{repo['name']}]({repo['html_url']}) - ⭐ {repo['stargazers_count']}"
            )
        return "User Repositories:\n" + "\n".join(repos_list)
    elif response.status_code == 404:
        return "❌ GitHub user not found."
    else:
        return f"❌ Error fetching repos (status {response.status_code})"

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    logger.info(f"Received username: {username} from user {update.effective_user.id}")
    if not is_valid_github_username(username):
        await update.message.reply_text("❌ Invalid GitHub username format.")
        return

    user_info = await get_github_user_info(username)
    await update.message.reply_text(user_info, disable_web_page_preview=True)

    keyboard = [
        [
            InlineKeyboardButton("View Repos 📦", callback_data=f"repos:{username}"),
            InlineKeyboardButton("Quit ❌", callback_data="quit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("repos:"):
        username = data.split(":", 1)[1]
        repos_text = await get_github_repos(username)
        await query.edit_message_text(repos_text, disable_web_page_preview=True)
    elif data == "quit":
        await query.edit_message_text("Thanks for using GitHub StatBot! Bye 👋")

async def repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        username = context.args[0]
        if not is_valid_github_username(username):
            await update.message.reply_text("❌ Invalid GitHub username format.")
            return
        repos_text = await get_github_repos(username)
        await update.message.reply_text(repos_text, disable_web_page_preview=True)
    else:
        await update.message.reply_text("Usage: /repos <github_username>")

# Create application and add handlers
application = Application.builder().token(TELEGRAM_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("quit", quit_command))
application.add_handler(CommandHandler("repos", repos_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
application.add_handler(CallbackQueryHandler(button_callback))

# Set bot commands on startup
async def set_commands():
    await application.bot.set_my_commands(
        [
            ("start", "Start the bot"),
            ("help", "Show help message"),
            ("repos", "List user repositories"),
            ("quit", "End interaction"),
        ]
    )

asyncio.get_event_loop().run_until_complete(set_commands())

@app.route("/", methods=["GET", "HEAD"])
def health_check():
    return "GitHub StatBot is running", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        if not data:
            logger.warning("Empty webhook payload")
            return "Bad Request", 400

        update = Update.de_json(data, application.bot)

        # Process update asynchronously
        asyncio.get_event_loop().create_task(application.process_update(update))

        return "OK", 200
    except Exception as e:
        logger.exception(f"Error in webhook: {e}")
        return "Error", 500

if __name__ == "__main__":
    logger.info("Starting GitHub StatBot with Flask...")
    # Use PORT environment variable or default 8443
    port = int(os.environ.get("PORT", 8443))
    app.run(host="0.0.0.0", port=port)
