from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_user_search = State()
    waiting_for_country_name = State()
    waiting_for_country_code = State()
    waiting_for_server_name = State()
    waiting_for_server_country = State()
    waiting_for_server_host = State()
    waiting_for_server_port = State() 