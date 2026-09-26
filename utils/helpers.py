from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MOODLE_BASE_URL = os.getenv("MOODLE_BASE_URL", "https://wolfware.ncsu.edu")