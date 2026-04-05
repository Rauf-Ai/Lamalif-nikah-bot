"""
states.py — состояния FSM для aiogram 3
"""
from aiogram.fsm.state import State, StatesGroup


class RegStates(StatesGroup):
    waiting_rules     = State()
    waiting_gender    = State()
    waiting_name      = State()
    waiting_age       = State()
    waiting_city      = State()
    waiting_about     = State()
    waiting_photos    = State()
    confirm_profile   = State()


class EditStates(StatesGroup):
    choose_field  = State()
    edit_name     = State()
    edit_age      = State()
    edit_city     = State()
    edit_about    = State()
    edit_photos   = State()


class BrowseStates(StatesGroup):
    browsing      = State()
    like_message  = State()   # ввод сообщения к лайку (премиум)
