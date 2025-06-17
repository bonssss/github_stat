# GitHub Stat Bot

A Telegram bot (@github_statbot) that retrieves GitHub user information and their top 5 public repositories. Built with Python and the `python-telegram-bot` library, it uses webhooks for real-time interaction and the GitHub API for data retrieval. Deployed on Render’s free tier, it supports interactive menus and commands.

## Features
- **User Info**: Fetch details like name, bio, public repos, followers, following, join date, and profile URL for any GitHub user.
- **Repositories**: List up to 5 recently updated public repositories with names, descriptions, star counts, and URLs.
- **Commands**:
  - `/start`: Initialize the bot.
  - `/help`: Display available commands.
  - `/repos <username>`: List top 5 repositories for a user.
  - `/quit`: End the current interaction.
  - Send a GitHub username directly to access an interactive menu with "User Info", "Repositories", or "Quit" options.

## Prerequisites
- Python 3.11.9
- Telegram account and a bot token from [@BotFather](https://t.me/BotFather)
- GitHub Personal Access Token (PAT) with `public_repo` scope
- Render account (free tier) for deployment
- Git installed for repository management

## Setup

### 1. Clone the Repository
```bash
git clone https://github.com/bonssss/github_stat.git
cd github_stat
```
### 2. Install Dependencies
Ensure requirements.txt contains:
```bash
python-telegram-bot[webhooks]>=20.7
requests==2.32.3
python-dotenv==1.0.1
```
### 3. Configure Environment Variables
Create a .env file in the root directory:
```bash
TELEGRAM_TOKEN=your_telegram_bot_token
RENDER_EXTERNAL_HOSTNAME=github-stat.onrender.com
GITHUB_TOKEN=your_github_personal_access_token
```
