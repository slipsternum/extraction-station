from telebot.states import State, StatesGroup


class UserStates(StatesGroup):
    """Conversation states."""

    idle = State()


class SetupStates(StatesGroup):
    """/setup: naming a new piece of equipment."""

    add_name = State()


class BeanStates(StatesGroup):
    """/newbean: capture a bag, review the extracted details, edit a field."""

    capture = State()
    review = State()
    edit_field = State()


class BrewStates(StatesGroup):
    """/brew: one state per step; the draft lives in state data until it is saved."""

    bean = State()
    method = State()
    grind = State()
    param = State()
    photo = State()
    extraction = State()
    clarity = State()
    notes = State()
    rating = State()
    comment = State()
    review = State()


__all__ = ["BeanStates", "BrewStates", "SetupStates", "UserStates"]
