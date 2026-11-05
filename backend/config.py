from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment():
    load_dotenv(PROJECT_ROOT / ".env")
