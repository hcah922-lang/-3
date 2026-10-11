from aiogram.fsm.state import State, StatesGroup


class ProfileFSM(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()
    interests = State()
    extra = State()
    photo = State()
    phone = State()
    preview = State()
    edit_field = State()
    edit_value = State()
