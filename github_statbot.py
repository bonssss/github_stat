import requests
import re
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Initialize Flask app
app = Flask(__name__)

# Telegram bot token
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set.")
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')  # Set in Render environment variables

# Validate GitHub username (alphanumeric and hyphens, max 39 chars)
def is_valid_github_username(username: str) -> bool:
    pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$'
    return bool(re.match(pattern, username))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # Clear any existing context
    await update.message.reply_text(
        'Hi! I am @github_statbot. Send me a GitHub username to get user info or use /help for commands.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/repos <username> - List up to 5 public repositories of a user\n"
        "/quit - End the current interaction\n"
        "Or just send a GitHub username to get user info.\n"
        "Note: GitHub usernames can only contain letters, numbers, and hyphens (-), up to 39 characters."
    )
    await update.message.reply_text(help_text)

async def quit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # Clear stored context
    await update.message.reply_text(
        "Interaction ended. Send another username or use /help for commands."
    )

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
        
        if not isinstance(user_data, dict):
            return f"Unexpected response from GitHub API for user '@{username}'. Please try again.", False
        
        name = user_data.get('name', 'N/A')
        bio = user_data.get('bio', 'N/A')
        public_repos = user_data.get('public_repos', 0)
        followers = user_data.get('followers', 0)
        following = user_data.get('following', 0)
        created_at = user_data.get('created_at', 'N/A').split('T')[0]
        profile_url = user_data.get('html_url', f'https://github.com/{username}')
        
        reply = f"GitHub User: @{username}\n"
        reply += f"Name: {name}\n"
        reply += f"Bio: {bio}\n"
        reply += f"Public Repos: {public_repos}\n"
        reply += f"Followers: {followers}\n"
        reply += f"Following: {following}\n"
        reply += f"Joined: {created_at}\n"
        reply += f"Profile: {profile_url}"
        
        return reply, True
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return f"Sorry, the GitHub user '@{username}' does not exist. Please check the username and try again.", False
        return f"Error fetching user data: {str(e)}", False
    except Exception as e:
        print(f"Error in get_github_user_info for @{username}: {str(e)}")
        return f"An unexpected error occurred: {str(e)}. Please try again.", False

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
        
        print(f"GitHub API response for repos of @{username}: type={type(repos_data)}, content={repos_data}")
        
        if not isinstance(repos_data, list):
            print(f"Invalid repos_data type for @{username}: {type(repos_data)}")
            return f"Unexpected response from GitHub API for repositories of '@{username}'. Please try again.", False
        
        if not repos_data:
            return f"No public repositories found for @{username}.", True
        
        reply = f"Top 5 repositories for @{username}:\n\n"
        for repo in repos_data:
            if not isinstance(repo, dict):
                print(f"Invalid repo entry for @{username}: {repo}")
                continue
            name = repo.get('name', 'N/A')
            description = repo.get('description') or 'No description'
            if len(description) > 100:
                description = description[:100] + '...'
            stars = repo.get('stargazers_count', 0)
            url = repo.get('html_url', '#')
            
            reply += f"📂 {name}\n"
            reply += f"Description: {description}\n"
            reply += f"⭐ Stars: {stars}\n"
            reply += f"URL: {url}\n\n"
        
        return reply, True
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return f"Sorry, the GitHub user '@{username}' does not exist. Please check the username and try again.", False
        print(f"HTTP error in get_github_repos for @{username}: {str(e)}")
        return f"Error fetching repos: {str(e)}. Please try again.", False
    except Exception as e:
        print(f"Error in get_github_repos for @{username}: {str(e)}")
        return f"An unexpected error occurred: {str(e)}. Please try again.", False

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    context.user_data['last_username'] = username
    
    if not is_valid_github_username(username):
        await update.message.reply_text(
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters."
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("User Info", callback_data=f'user_{username}'),
            InlineKeyboardButton("Repositories", callback_data=f'repos_{username}')
        ],
        [InlineKeyboardButton("Quit", callback_data=f'quit_{username}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"What would you like to know about @{username}?",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, username = query.data.split('_', 1)
    
    if action == 'quit':
        context.user_data.clear()
        await query.message.reply_text(
            "Interaction ended. Send another username or use /help for commands.",
            reply_markup=None
        )
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Anything else about @{username}?",
            reply_markup=reply_markup
        )

async def repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a GitHub username, e.g., /repos octocat")
        return
    
    username = context.args[0].strip()
    if not is_valid_github_username(username):
        await update.message.reply_text(
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters."
        )
        return
    
    reply, _ = await get_github_repos(username)
    await update.message.reply_text(reply)

# Flask route for webhook
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return 'OK', 200

def main():
    global application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('quit', quit_command))
    application.add_handler(CommandHandler('repos', repos_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("Bot @github_statbot is setting up webhook...")
    application.run_webhook(
        listen='0.0.0.0',
        port=int(os.environ.get('PORT', 8443)),
        url_path=TELEGRAM_TOKEN,
        webhook_url=f'{WEBHOOK_URL}/{TELEGRAM_TOKEN}'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8443)))