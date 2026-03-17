import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./martial_arts.db")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "martial-arts-ai-super-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Model
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(os.path.dirname(__file__), "ml"))
