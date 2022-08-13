import json
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
import db


def kb_main(user_id):
    user_info = db.get_user(user_id)
    if user_info is not None:
        keyboard = {'keyboard': [
            ['Мой аккаунт'],
            ['О нас', 'О проекте'],
            ['Новости'],
            ['Помощь']],
            'one_time_keyboard': False, 'resize_keyboard': True}
        if user_info['access'] != 1:
            keyboard['keyboard'].insert(0, ['Приобрести доступ'])
        if user_id == 404587021 or user_id == 511872773:
            keyboard['keyboard'].insert(0, ['Админ панель'])
    else:
        keyboard = {'keyboard': [
            ['Регистрация'],
            ['О нас', 'О проекте'],
            ['Новости'],
            ['Помощь']],
            'one_time_keyboard': False, 'resize_keyboard': True}
        if user_id == 404587021 or user_id == 511872773:
            keyboard['keyboard'].insert(0, ['Обновить текст'])

    return json.dumps(keyboard)


def kb_admin_panel():
    keyboard = json.dumps({'keyboard': [['Обновить текст'], ['Изменить баланс человека'], ['Отмена']], 'one_time_keyboard': False, 'resize_keyboard': True})

    return keyboard


def kb_choice():
    keyboard = json.dumps({'keyboard': [['Да'], ['Нет'], ['Отмена']], 'one_time_keyboard': False, 'resize_keyboard': True})

    return keyboard


def kb_break():
    keyboard = json.dumps({'keyboard': [['Отмена']], 'one_time_keyboard': False, 'resize_keyboard': True})

    return keyboard


def kb_account():
    keyboard = json.dumps({'keyboard': [['Баланс'], ['Мой статус'], ['Мои рефералы'], ['Назад']], 'one_time_keyboard': False, 'resize_keyboard': True})

    return keyboard


def kb_balance():
    keyboard = json.dumps({'keyboard': [['Узнать баланс'], ['Пополнить баланс'], ['Вывести деньги'], ['Назад']], 'one_time_keyboard': False, 'resize_keyboard': True})

    return keyboard


def kb_refill_link(link):
    keyboard = json.dumps(
        {
            'inline_keyboard': [[
                {'text': 'Оплатить!', 'url': link}
            ]]
        }
    )

    return keyboard


def kb_access_link(link):
    keyboard = json.dumps(
        {
            'inline_keyboard': [[
                {'text': 'Вступить!', 'url': link}
            ]]
        }
    )

    return keyboard


def kb_help():
    keyboard = json.dumps({'keyboard': [['Техподдержка'], ['Назад']], 'one_time_keyboard': False, 'resize_keyboard': True})

    return keyboard

