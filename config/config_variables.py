import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./libros.db")
APP_NAME = os.getenv("APP_NAME", "API VINILOS")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"