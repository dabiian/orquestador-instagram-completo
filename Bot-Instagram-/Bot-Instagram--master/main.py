"""Módulo principal - Instagram Bot"""
import socket
from app.api.task_api import TaskAPI
from app.api.ai_api import AIAPI
from app.api.account_api import AccountAPI
from app.orchestrator.bot_runner import EjecutaBot
from app.utils.logger import configure_process_stdio_utf8

NAME_BOT = f"Bot_Instagram_{socket.gethostname()}"
PROCESS = "V1"

if __name__ == "__main__":
    configure_process_stdio_utf8()
    task_api = TaskAPI()
    ai_api = AIAPI()
    account_api = AccountAPI()

    bot = EjecutaBot(NAME_BOT, task_api=task_api, ai_api=ai_api, account_api=account_api)
    bot.run_bot("V1")
