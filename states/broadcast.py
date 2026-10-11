from aiogram.fsm.state import State, StatesGroup


class BroadcastFSM(StatesGroup):
    text = State()
    photo = State()
    audience = State()
    confirm = State()
