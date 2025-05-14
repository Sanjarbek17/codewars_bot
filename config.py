import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Bot token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Codewars API
CODEWARS_API_BASE = "https://www.codewars.com/api/v1/users/"

# Configure logging
# logging.basicConfig(
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     level=logging.DEBUG,
#     handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
# )
# logger = logging.getLogger(__name__)
