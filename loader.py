from database.crud import Database
from utils.browser import BrowserManager
import os
from dotenv import load_dotenv

load_dotenv()

browser_manager = BrowserManager()
data_base = Database(str(os.getenv("DB_PATH")))
