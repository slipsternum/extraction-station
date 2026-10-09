from __future__ import annotations


class WelcomeText:
    @staticmethod
    def greeting(user: object | None) -> str:
        first_name = getattr(user, "first_name", None) or "there"
        return (
            f"Hey {first_name}! Welcome to your Telegram bot.\n\n"
            "Use /help to see available commands."
        )

    @staticmethod
    def cancelled() -> str:
        return "Cancelled."


class HelpText:
    @staticmethod
    def help_message() -> str:
        return (
            "Available commands:\n"
            "- /start: show the welcome message\n"
            "- /ping: check bot health\n"
            "- /help: show this help message\n"
            "- /cancel: cancel the current operation"
        )
