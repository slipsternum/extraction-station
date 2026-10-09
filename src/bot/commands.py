from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from telebot.types import BotCommand, BotCommandScope


@dataclass(frozen=True)
class CommandSet:
    commands: Iterable[BotCommand]
    scope: BotCommandScope


user_commands: CommandSet = CommandSet(
    commands=[
        BotCommand("start", "show the welcome message"),
        BotCommand("help", "show available commands"),
        BotCommand("ping", "check if the bot is alive"),
        BotCommand("cancel", "cancel the current operation"),
    ],
    scope=BotCommandScope(type="all_private_chats"),
)

admin_commands: CommandSet = CommandSet(
    commands=[
        BotCommand("admin", "admin-only example command"),
        *user_commands.commands,
    ],
    scope=BotCommandScope(type="all_private_chats"),
)


__all__ = ["CommandSet", "user_commands", "admin_commands"]
