import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

AUTH_PARAMS = {
    "app_ver": os.getenv("APP_VER", "97"),
    "os": os.getenv("OS", "ios"),
    "os_ver": os.getenv("OS_VER", "18.1"),
    "secret": os.getenv("SECRET"),
}