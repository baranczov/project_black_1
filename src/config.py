import logging
import os
from dotenv import dotenv_values, find_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DOTENV_PATH = find_dotenv()

config = dotenv_values(DOTENV_PATH) if DOTENV_PATH else {}


def get_env_variable(key, default=None):
    """Получает значение переменной окружения по ключу с возможностью указания значения по умолчанию."""
    return config.get(key, default)


DEBUG = get_env_variable("DEBUG", "False") == "True"
BOT_TOKEN = get_env_variable("BOT_TOKEN")
API_KEY = get_env_variable("API_KEY")

LOGGING_LEVEL = logging.DEBUG if DEBUG else logging.INFO

logging.basicConfig(level=LOGGING_LEVEL)
