# Codewars Bot

A Telegram bot that integrates with Codewars to help users track their progress, receive coding challenges, and stay engaged with programming practice.

## Features

- Telegram bot interface for easy interaction
- Integration with Codewars API
- Local data storage using TinyDB
- Track user progress and statistics
- Receive daily coding challenges

## Commands

/start - Welcome message and list of available commands
/register [codewars_username] - Register your Codewars account
/creategroup [group_name] - Create a new group
/joingroup - See available groups to join
/mystats - See your Codewars statistics
/groupstats - See your group's statistics
/daily - View today's and yesterday's kata completions
/weekly - View last 7 days of kata completions
/help - Show list of commands and get assistance

## Prerequisites

- Python 3.13+
- Telegram Bot Token
- Codewars API access

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd codewars_bot
```

2. Create and activate a virtual environment:
```bash
python -m venv env
source env/bin/activate  # On macOS/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
CODEWARS_API_KEY=your_codewars_api_key
```

## Usage

Run the bot:
```bash
python main.py
```

## Database

The project uses TinyDB (db.json) for storing:
- User information
- Challenge history
- Progress tracking

## Contributing

Feel free to open issues and submit pull requests.

## License

[Add your chosen license]