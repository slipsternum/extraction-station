from telebot.states import State, StatesGroup


class UserStates(StatesGroup):
    """Conversation states."""

    idle = State()


__all__ = ["UserStates"]
