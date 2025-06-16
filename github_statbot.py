import requests
import re
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()  # Load environment variables from .env file

# Flask app
app = Flask(__name__)

# Load environment variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')  # e.g. https://yourdomain.com

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set.")

# Initialize Telegram application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Utility Functions ---

def is_valid_github_username(username: str) -> bool:
    pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$'
    return bool(re.match(pattern, username))

async def get_github_user_info(username: str) -> tuple[str, bool]:
    if not is_valid_github_username(username):
        return (
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters.",
            False
        )
    url = f'https://api.github.com/users/{username}'
    try:
        response = requests.get(url)
        if response.status_code == 403:
            return "GitHub API rate limit exceeded. Please try again later.", False
        response.raise_for_status()
        user_data = response.json()

        name = user_data.get('name', 'N/A')
        bio = user_data.get('bio', 'N/A')
        public_repos = user_data.get('public_repos', 0)
        followers = user_data.get('followers', 0)
        following = user_data.get('following', 0)
        created_at = user_data.get('created_at', 'N/A').split('T')[0]
        profile_url = user_data.get('html_url', f'https://github.com/{username}')

        reply = f"GitHub User: @{username}\n"
        reply += f"Name: {name}\nBio: {bio}\nPublic Repos: {public_repos}\n"
        reply += f"Followers: {followers}\nFollowing: {following}\n"
        reply += f"Joined: {created_at}\nProfile: {profile_url}"

        return reply, True
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return f"Sorry, the GitHub user '@{username}' does not exist.", False
        return f"HTTP error: {str(e)}", False
    except Exception as e:
        return f"Unexpected error: {str(e)}", False

async def get_github_repos(username: str) -> tuple[str, bool]:
    if not is_valid_github_username(username):
        return (
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters.",
            False
        )
    url = f'https://api.github.com/users/{username}/repos?per_page=5&sort=updated'
    try:
        response = requests.get(url)
        if response.status_code == 403:
            return "GitHub API rate limit exceeded. Please try again later.", False
        response.raise_for_status()
        repos_data = response.json()

        if not repos_data:
            return f"No public repositories found for @{username}.", True

        reply = f"Top 5 repositories for @{username}:\n\n"
        for repo in repos_data:
            name = repo.get('name', 'N/A')
            description = repo.get('description') or 'No description'
            if len(description) > 100:
                description = description[:100] + '...'
            stars = repo.get('stargazers_count', 0)
            url = repo.get('html_url', '#')
            reply += f"📂 {name}\nDescription: {description}\n⭐ Stars: {stars}\nURL: {url}\n\n"

        return reply, True
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return f"GitHub user '@{username}' not found.", False
        return f"HTTP error: {str(e)}", False
    except Exception as e:
        return f"Unexpected error: {str(e)}", False

# --- Telegram Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        'Hi! I am @github_statbot. Send me a GitHub username to get user info or use /help for commands.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show help\n"
        "/repos <username> - List public repos\n"
        "/quit - End the interaction"
    )

async def quit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Interaction ended. Send a new GitHub username to start over.")

async def repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a GitHub username, e.g., /repos octocat")
        return
    username = context.args[0].strip()
    reply, _ = await get_github_repos(username)
    await update.message.reply_text(reply)

# --- Telegram Message + Callback Handlers ---

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    context.user_data['last_username'] = username

    if not is_valid_github_username(username):
        await update.message.reply_text(f"Invalid username '@{username}'.")
        return

    keyboard = [
        [
            InlineKeyboardButton("User Info", callback_data=f'user_{username}'),
            InlineKeyboardButton("Repositories", callback_data=f'repos_{username}')
        ],
        [InlineKeyboardButton("Quit", callback_data=f'quit_{username}')]
    ]
    await update.message.reply_text(
        f"What would you like to know about @{username}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, username = query.data.split('_', 1)

    if action == 'quit':
        context.user_data.clear()
        await query.message.reply_text("Interaction ended.")
        return

    if action == 'user':
        reply, success = await get_github_user_info(username)
    elif action == 'repos':
        reply, success = await get_github_repos(username)

    await query.message.reply_text(reply)
    if success:
        keyboard = [
            [
                InlineKeyboardButton("User Info", callback_data=f'user_{username}'),
                InlineKeyboardButton("Repositories", callback_data=f'repos_{username}')
            ],
            [InlineKeyboardButton("Quit", callback_data=f'quit_{username}')]
        ]
        await query.message.reply_text(
            f"Anything else about @{username}?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- Register handlers ---

application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('help', help_command))
application.add_handler(CommandHandler('quit', quit_command))
application.add_handler(CommandHandler('repos', repos_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
application.add_handler(CallbackQueryHandler(button_callback))

# --- Flask webhook route ---

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return 'OK', 200

# --- Main ---

def main():
    print("Starting bot and setting webhook...")
    application.run_webhook(
        listen='0.0.0.0',
        port=int(os.environ.get('PORT', 8443)),
        url_path=TELEGRAM_TOKEN,
        webhook_url=f'{WEBHOOK_URL}/{TELEGRAM_TOKEN}'
    )

if __name__ == '__main__':
    main()
