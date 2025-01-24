from telethon.sync import TelegramClient
from dotenv import load_dotenv
import os   
from bot import Bot


load_dotenv()


token = os.getenv("TOKEN")
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

bot = Bot(token=token, api_id=api_id, api_hash=api_hash)

