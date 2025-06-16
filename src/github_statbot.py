import requests
import re
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Environment variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Optional: for GitHub API rate limits

# Validate environment variables
if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise ValueError("TELEGRAM_TOKEN and WEBHOOK_URL must be set in environment variables.")

# Validate GitHub username (alphanumeric and hyphens, max 39 chars)
def is_valid_github_username(username: str) -> bool:
    pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$'
    return bool(re.match(pattern, username))

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    logger.info(f"Start command received from user {update.effective_user.id}")
    context.user_data.clear()
    await update.message.reply_text(
        'Hi! I am @github_statbot. Send me a GitHub username to get user info or use /help for commands.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    logger.info(f"Help command received from user {update.effective_user.id}")
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
    """Handle /quit command"""
    logger.info(f"Quit command received from user {update.effective_user.id}")
    context.user_data.clear()
    await update.message.reply_text(
        "Interaction ended. Send another username or use /help for commands."
    )

async def get_github_user_info(username: str) -> tuple[str, bool]:
    """Fetch GitHub user information"""
    logger.info(f"Fetching GitHub user info for @{username}")
    if not is_valid_github_username(username):
        logger.warning(f"Invalid username: @{username}")
        return (
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters.",
            False
        )
    
    url = f'https://api.github.com/users/{username}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 403:
            logger.error("GitHub API rate limit exceeded")
            return "GitHub API rate limit exceeded. Please try again later.", False
        response.raise_for_status()
        user_data = response.json()
        
        if not isinstance(user_data, dict):
            logger.error(f"Unexpected GitHub API response for @{username}: {user_data}")
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
        logger.info(f"Successfully fetched user info for @{username}")
        return reply, True
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error for @{username}: {str(e)}")
        if response.status_code == 404:
            return f"Sorry, the GitHub user '@{username}' does not exist. Please check the username and try again.", False
        return f"Error fetching user data: {str(e)}", False
    except Exception as e:
        logger.exception(f"Unexpected error for @{username}: {str(e)}")
        return f"An unexpected error occurred: {str(e)}. Please try again.", False

async def get_github_repos(username: str) -> tuple[str, bool]:
    """Fetch up to 5 GitHub repositories"""
    logger.info(f"Fetching repositories for @{username}")
    if not is_valid_github_username(username):
        logger.warning(f"Invalid username: @{username}")
        return (
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters.",
            False
        )
    
    url = f'https://api.github.com/users/{username}/repos?per_page=5&sort=updated'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 403:
            logger.error("GitHub API rate limit exceeded")
            return "GitHub API rate limit exceeded. Please try again later.", False
        response.raise_for_status()
        repos_data = response.json()
        
        if not isinstance(repos_data, list):
            logger.error(f"Invalid repos_data type for @{username}: {type(repos_data)}")
            return f"Unexpected response from GitHub API for repositories of '@{username}'. Please try again.", False
        
        if not repos_data:
            logger.info(f"No public repositories found for @{username}")
            return f"No public repositories found for @{username}.", True
        
        reply = f"Top 5 repositories for @{username}:\n\n"
        for repo in repos_data:
            if not isinstance(repo, dict):
                logger.warning(f"Invalid repo entry for @{username}: {repo}")
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
        
        logger.info(f"Successfully fetched repositories for @{username}")
        return reply, True
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error for @{username}: {str(e)}")
        if response.status_code == 404:
            return f"Sorry, the GitHub user '@{username}' does not exist. Please check the username and try again.", False
        return f"Error fetching repos: {str(e)}. Please try again.", False
    except Exception as e:
        logger.exception(f"Unexpected error for @{username}: {str(e)}")
        return f"An unexpected error occurred: {str(e)}. Please try again.", False

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with GitHub usernames"""
    username = update.message.text.strip()
    logger.info(f"Received username: @{username} from user {update.effective_user.id}")
    context.user_data['last_username'] = username
    
    if not is_valid_github_username(username):
        logger.warning(f"Invalid username received: @{username}")
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
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    action, username = query.data.split('_', 1)
    logger.info(f"Button callback: action={action}, username={username} from user {update.effective_user.id}")
    
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
    """Handle /repos command"""
    if not context.args:
        logger.warning(f"Repos command called without username by user {update.effective_user.id}")
        await update.message.reply_text("Please provide a GitHub username, e.g., /repos octocat")
        return
    
    username = context.args[0].strip()
    logger.info(f"Repos command for @{username} by user {update.effective_user.id}")
    if not is_valid_github_username(username):
        logger.warning(f"Invalid username in repos command: @{username}")
        await update.message.reply_text(
            f"Invalid username '@{username}'. GitHub usernames can only contain letters, numbers, and hyphens, up to 39 characters."
        )
        return
    
    reply, _ = await get_github_repos(username)
    await update.message.reply_text(reply)

# Flask Routes
@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    """Handle health check requests"""
    logger.info("Health check requested")
    return 'GitHub StatBot is running', 200

application = Application.builder().token(TELEGRAM_TOKEN).build()

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])

async def webhook():
    """Handle Telegram webhook updates"""
    global application
    logger.info("Received webhook request")
    try:
        data = request.get_json(force=True)
        logger.debug(f"webhook payload: {data}")
        if not data:
            logger.warning("Empty webhook payload")
            return 'Bad Request', 400
        update = Update.de_json(data, application.bot)
        if not update:
            logger.warning("Invalid update received")
            return 'OK', 200
        await application.process_update(update)
        logger.info("Webhook processed successfully")
        return 'OK', 200
    except Exception as e:
        logger.exception(f"Webhook error: {str(e)}")
        return 'Error', 500

# Bot Setup
async def set_commands(application):
    """Set Telegram bot commands"""
    logger.info("Setting bot commands")
    await application.bot.set_my_commands([
        ('start', 'Start the bot'),
        ('help', 'Show help message'),
        ('repos', 'List user repositories'),
        ('quit', 'End interaction')
    ])

def main():
    """Initialize and run the bot"""
    global application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('quit', quit_command))
    application.add_handler(CommandHandler('repos', repos_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Setting up webhook...")
    application.job_queue.run_once(lambda _: set_commands(application), 0)
    application.run_webhook(
        listen='0.0.0.0',
        port=int(os.environ.get('PORT', 8443)),
        url_path=TELEGRAM_TOKEN,
        webhook_url=f'{WEBHOOK_URL}/{TELEGRAM_TOKEN}'
    )

if __name__ == '__main__':
    logger.info("Starting GitHub StatBot")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8443)))