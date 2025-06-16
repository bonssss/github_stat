import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
# load_dotenv is not used here, but can be used to load environment variables from a .env file
from dotenv import load_dotenv
# Load environment variables from .env file if needed
load_dotenv()
# Telegram bot token from BotFather
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hi! I am @github_statbot. Send me a GitHub username, and I’ll fetch info about that user.')

async def get_github_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    url = f'https://api.github.com/users/{username}'
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        user_data = response.json()
        
        # Extract relevant information
        name = user_data.get('name', 'N/A')
        bio = user_data.get('bio', 'N/A')
        public_repos = user_data.get('public_repos', 0)
        followers = user_data.get('followers', 0)
        following = user_data.get('following', 0)
        created_at = user_data.get('created_at', 'N/A').split('T')[0]
        
        # Format the response
        reply = f"GitHub User: @{username}\n"
        reply += f"Name: {name}\n"
        reply += f"Bio: {bio}\n"
        reply += f"Public Repos: {public_repos}\n"
        reply += f"Followers: {followers}\n"
        reply += f"Following: {following}\n"
        reply += f"Joined: {created_at}"
        
        await update.message.reply_text(reply)
        
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            await update.message.reply_text(f"User @{username} not found on GitHub.")
        else:
            await update.message.reply_text(f"Error fetching data: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

def main():
    # Initialize the bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_github_user_info))
    
    # Start the bot
    print("Bot @github_statbot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()