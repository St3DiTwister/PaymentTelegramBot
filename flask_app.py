from flask import Flask, request, render_template
from flask_sslify import SSLify
import requests
from dotenv import load_dotenv
import os
from os.path import join, dirname
import keyboards as kb
import time
import datetime
import traceback
import hashlib
import hmac
from table import edit_env
import re
import db
import telegram

app = Flask(__name__)
ssl = SSLify(app)


def get_from_env(key):
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    return os.environ.get(key)


def get_from_txt(key):
    with open('bot_text.env', 'r', encoding='utf-8') as file:
        text = '0'
        while text != '':
            text = file.readline()
            if text.split('=')[0] == key:
                return text.split('=')[1].replace('\n', '').replace('"', '')


URL = f'https://api.telegram.org/bot{get_from_env("TG_TOKEN")}/'
bot = telegram.Bot(get_from_env("TG_TOKEN"))


def send_message(user_id, message, keyboard=None, line_break=None, user_link=None):  # сверху пост запрос, это гет запрос, с помощью гет запроса можно сделать перенос строк
    global URL
    url = URL + 'sendMessage'
    if user_link is True:
        parent_id = db.check_parent(user_id)
        if parent_id:
            bot.send_message(user_id, f'[Пригласивший тебя человек](tg://user?id={parent_id[0][0]})', parse_mode='MarkdownV2')
        bot.send_message(user_id, f'[Канал техподдержки](https://t.me/joinchat/HDQc4lcv-zplYzNi)', parse_mode='MarkdownV2')
        return "ok"
    elif line_break is None:
        if keyboard is None:
            answer = {'chat_id': user_id, 'text': message}
        else:
            answer = {'chat_id': user_id, 'text': message, 'reply_markup': keyboard}
        r = requests.post(url, json=answer)
    else:
        if keyboard is None:
            r = requests.get(url+'?chat_id=' + str(user_id) + '&text=' + message.replace('+', '%2B'))
        else:
            r = requests.get(url+'?chat_id=' + str(user_id) + '&text=' + message.replace('+', '%2B') + '&reply_markup=' + keyboard)
    print(f'{time.strftime("%H:%M:%S")} --- RESPONSE --- {user_id} --- {message} --- from Bot')
    return r.json()


tasks = {}


def balance(user_id, user_message):
    if user_message.lower() == 'назад':
        send_message(user_id, f'Возвращаемся назад...', keyboard=kb.kb_account())
        del tasks[user_id]

    elif user_message.lower() == 'отмена':
        send_message(user_id, f'Отмена...', keyboard=kb.kb_balance())
        tasks[user_id] = {'action': 'баланс'}

    elif user_message.lower() == 'пополнить баланс':
        send_message(user_id, f'На какую сумму хочешь пополнить свой баланс?', keyboard=kb.kb_break())
        tasks[user_id] = {'action': 'баланс пополнение', 'time': time.time()}

    elif user_message.lower() == 'узнать баланс':
        user_info = db.get_user(user_id)
        send_message(user_id, f'Твой баланс - {user_info["balance"]} руб.')

    elif user_message.lower() == 'вывести деньги':
        send_message(user_id, f'Отправь мне свой номер карты (без пробелов), либо номер QIWI кошелька (начиная с 7, без знака +). '
                              f'Должен тебя предупредить, при выводе на карту с твоего баланса спишется дополнительная комиссия в размере 50 руб. Минимальная сумма вывода - 200 руб.', keyboard=kb.kb_break())
        tasks[user_id] = {'action': 'баланс вывод карта', 'time': time.time()}

    elif tasks[user_id]['action'] == 'баланс вывод карта':
        try:
            user_message = int(user_message)
        except ValueError:
            send_message(user_id, f'Укажи номер счета только цифрами.')
            return "ok"
        user_message = str(user_message)
        if user_message[0] in ['2', '4', '5']:
            if len(user_message) != 16:
                send_message(user_id, 'Неправильный номер карты.')
                return "ok"
        elif user_message[0] == '7':
            if len(user_message) != 11:
                send_message(user_id, 'Неправильный номер Qiwi кошелька')
                return "ok"
        else:
            send_message(user_id, 'Странный номер карты...')
            return "ok"
        send_message(user_id, f'Теперь отправь мне сумму вывода.')
        tasks[user_id] = {'action': 'баланс вывод сумма', 'time': time.time(), 'card': str(user_message)}
        return "ok"

    elif tasks[user_id]['action'] == 'баланс вывод сумма':
        try:
            user_message = int(user_message)
        except ValueError:
            send_message(user_id, f'Укажи сумму только числом.')
            return "ok"
        if user_message < 1:
            send_message(user_id, 'Минимальный вывод 1 рубль.')
            return "ok"
        user_balance = db.get_user(user_id)['balance']
        if tasks[user_id]['card'][0] in ['2', '4', '5']:
            amount = user_message + 50
        elif tasks[user_id]['card'][0] == '7':
            amount = user_message
        else:
            send_message(user_id, 'Странный номер карты...')
            return "ok"
        if user_balance >= amount:
            if db.withdraw(user_id, amount):
                result_withdraw = withdraw(amount, tasks[user_id]['card'])
                if result_withdraw.get('transaction') is not None:
                    if user_message + 50 == amount:
                        send_message(user_id, f'Вывод на карту. Дополнительно списываю 50 руб.')
                    send_message(user_id, f'Запрос на вывод успешно создан! Сумма вывода - {user_message} руб.', keyboard=kb.kb_balance())
                    tasks[user_id] = {'action': 'баланс'}
                    return "ok"
                elif result_withdraw.get('code') == 'QWPRC-167':
                    send_message(user_id, 'Статус кошелька не позволяет совершить платеж. Нужно получить статус "основной" в вашем QIWI кошельке.')
                elif result_withdraw.get('code') == 'QWPRC-220':
                    send_message(user_id, 'В данный момент вывод не доступен по нашим причинам, повторите попытку позже...')
                    tasks[user_id] = {'action': 'баланс'}
                    return "ok"
                elif result_withdraw.get('code') == 'QWPRC-4':
                    send_message(user_id, 'Неправильно указан номер счета/телефона')
                    return "ok"
                else:
                    send_message(user_id, 'Произошла неизвестная ошибка...')
                    print(f'НЕИЗВЕСТНАЯ ОШИБКА QIWI P2P -- {result_withdraw.get("code")}')
                    return "ok"
            else:
                send_message(user_id, f'Недостаточно средств на балансе!')
        else:
            send_message(user_id, f'Недостаточно средств на балансе!')
            return "ok"
    elif tasks[user_id]['action'] == 'баланс пополнение':
        try:
            user_message = int(user_message)
        except ValueError:
            send_message(user_id, f'Укажи сумму только числом.')
            return "ok"
        if 1 > user_message > 10000:
            send_message(user_id, 'Минимальная сумма пополнения 1 руб.')
            return "ok"
        send_message(user_id, 'Держи ссылку на оплату. Проверь комментарий к платежу, там должен быть указан твой никнейм.', keyboard=kb.kb_refill_link(link_generator_refill(user_id, user_message)))
        send_message(user_id, 'Буду ждать оплаты.', keyboard=kb.kb_balance())
        tasks[user_id] = {'action': 'баланс'}

    return 1


def link_generator_refill(user_id, amount):
    d = (datetime.datetime.now()+datetime.timedelta(hours=3)).replace(tzinfo=datetime.timezone.utc)
    d = d.replace(microsecond=0)
    buildID = os.urandom(16).hex()

    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer ' + get_from_env('SECRET_QIWI_TOKEN'),
        'content-type': 'application/json',
        'Referrer-Policy': 'no-referrer-when-downgrade'
    }
    amount = str(amount) + '.00'
    params = {
        'amount': {'value': amount, 'currency': 'RUB'},
        'comment': db.get_user(user_id)['nickname'],
        'expirationDateTime': d.isoformat(),
        'customer': {'account': str(user_id)}
    }

    print(d.isoformat())
    url = f'https://api.qiwi.com/partner/bill/v1/bills/{buildID}'
    resp = requests.put(url, json=params, headers=headers)
    print(resp.json())
    return resp.json()['payUrl']


def withdraw(amount, card):
    #  перевод на карту priv_id = 1963(visa), 21013(mastercard), 31652(МИР)
    #  перевод на qiwi priv_id = 99
    if card[0] == '4':
        prv_id = '1963'
    elif card[0] == '5':
        prv_id = '21013'
    elif card[0] == '2':
        prv_id = '31652'
    elif card[0] == '7':
        prv_id = '99'
    else:
        return False
    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer ' + get_from_env('QIWI_TOKEN'),
        'content-type': 'application/json'
    }

    params = {
        "id": str(int(time.time() * 1000)),
        "sum": {
            "amount": amount,
            "currency": "643"
        },
        "paymentMethod": {
            "type": "Account",
            "accountId": "643"
        },
        "fields": {
            "account": card
        }
    }
    res = requests.post('https://edge.qiwi.com/sinap/api/v2/terms/' + prv_id + '/payments', json=params, headers=headers)
    return res.json()


@app.route('/', methods=['POST'])
def process():
    global tasks
    # print(request.json)

    # ----- БЛОК ОБРАБОТКИ СООБЩЕНИЙ О ГРУППЕ (игнорировать) -----
    if list(request.json.keys())[1] == 'my_chat_member':
        return "ok"

    # ----- БЛОК ОБРАБОТКИ ЛИЧНЫХ СООБЩЕНИЙ -----
    if list(request.json.keys())[1] == 'message':
        try:
            user_id = request.json["message"]["from"]["id"]
            user_message = request.json["message"]["text"]
        except KeyError:
            return "ok"
        print(f'{time.strftime("%H:%M:%S")} --- {user_id} --- {user_message}')

        # ----- ПРОВЕРКА НА АКТИВНЫЕ ЗАДАЧИ -----
        if user_id in tasks.keys():
            if tasks[user_id]['action'] in ['баланс']:
                balance(user_id, user_message)
                return "ok"
            if round(time.time() - tasks[user_id]['time']) > 120:  # если разница во времени начала задачи и текущего больше 2 минут, возврат в главное меню
                send_message(user_id, 'Время ожидания истекло, возврат в главное меню...', keyboard=kb.kb_main(user_id))
                del tasks[user_id]
                return "ok"
            if tasks[user_id]['action'] in ['баланс', 'баланс пополнение', 'баланс вывод', 'баланс вывод карта', 'баланс вывод сумма']:
                balance(user_id, user_message)
                return "ok"
            if user_message.lower() == 'отмена':
                del tasks[user_id]
                send_message(user_id, 'Возврат в главное меню...', keyboard=kb.kb_main(user_id))
                return "ok"
            if tasks[user_id]['action'] == 'регистрация':
                if db.check_nickname(user_message) is True:
                    if 6 <= len(user_message) <= 20:
                        if bool(re.match(r'^[A-Za-z0-9]*$', user_message)):
                            send_message(user_id, f'Твой логин - "{user_message}". Уверен в своём выборе?', keyboard=kb.kb_choice())
                            tasks[user_id] = {'action': 'подтверждение регистрации', 'time': time.time(), 'nickname': user_message}
                        else:
                            send_message(user_id, 'Логин должен состоять из английских букв и цифр!')
                            return "ok"
                    else:
                        send_message(user_id, 'Логин должен состоять как минимум из 6 и как максимум из 20 символов!')
                else:
                    send_message(user_id, 'Логин занят.')
                    return "ok"
            elif tasks[user_id]['action'] == 'подтверждение регистрации':
                if user_message.lower() == 'да':
                    if db.add_user(user_id, tasks[user_id]['nickname']):
                        send_message(user_id, f'Ты успешно зарегистрировался! Возврат в главное меню...', keyboard=kb.kb_main(user_id))
                        del tasks[user_id]
                    else:
                        send_message(user_id, 'Что-то пошло не так... Возврат в главное меню...', keyboard=kb.kb_main(user_id))
                elif user_message.lower() == 'нет':
                    send_message(user_id, f'Хорошо, подумай ещё и напиши мне новый логин!', keyboard=kb.kb_break())
                    tasks[user_id] = {'action': 'регистрация', 'time': time.time()}
            elif tasks[user_id]['action'] == 'покупка доступа':
                if db.get_user(user_id)['balance'] >= 1000:  # проверка баланса на нужную сумму
                    if user_message != '.':
                        parent_nickname = db.check_nickname(user_message)
                        if parent_nickname != 1:  # проверяет наличие введенного пользователя в базе
                            if parent_nickname != tasks[user_id]['nickname']:
                                if db.withdraw(user_id, 1000):  # снимает деньги со счета пользователя
                                    db.get_access(user_id)
                                    send_message(user_id, f'Доступ успешно приобретён!')
                                    send_message(user_id, 'Держи ссылку на вступление!', keyboard=kb.kb_access_link(get_from_txt('ACCESS_LINK')))
                                    send_message(user_id, 'Добро пожаловать!', keyboard=kb.kb_main(user_id))
                                    db.new_referral(parent_nickname, tasks[user_id]['nickname'])  # добавляет связь родителя-ребенка в реферальную систему
                                    db.referrals(tasks[user_id]['nickname'])  # функция проверки статусов
                                    send_bonus = db.referral_bonus(tasks[user_id]['nickname'])
                                    for x in send_bonus.keys():
                                        send_message(x, f'Тебе начислен бонус за реферальную систему в размере {send_bonus[x].get("amount")} руб.')
                                    # send_message(db.referral_bonus(tasks[user_id]['nickname']), f'Новый реферал - {tasks[user_id]["nickname"]}!')
                                    del tasks[user_id]
                                    return "ok"
                                else:
                                    send_message(user_id, 'На твоём счету недостаточно средств', keyboard=kb.kb_main(user_id))
                                    return "ok"
                            else:
                                send_message(user_id, 'Хочешь стать рефералом самого себя? Умно... но нет.')
                                return "ok"
                        else:
                            send_message(user_id, 'Такой никнейм не зарегистрирован в нашей системе.')
                            return "ok"
                    else:
                        if db.withdraw(user_id, 1000):
                            db.get_access(user_id)
                            send_message(user_id, 'Доступ успешно приобретён!')
                            send_message(user_id, 'Держи ссылку на вступление!', keyboard=kb.kb_access_link(get_from_txt('ACCESS_LINK')))
                            send_message(user_id, 'Добро пожаловать!', keyboard=kb.kb_main(user_id))
                            del tasks[user_id]
                            return "ok"
                        else:
                            send_message(user_id, 'На твоём счету недостаточно средств', keyboard=kb.kb_main(user_id))
                            del tasks[user_id]
                            return "ok"
                else:
                    send_message(user_id, 'На твоём счету недостаточно средств', keyboard=kb.kb_main(user_id))
                    del tasks[user_id]
            elif tasks[user_id]['action'] == 'изменить баланс человека':
                if len(user_message.split('+')) == 2:
                    info_about_action = user_message.replace(' ', '').split('+')
                    if db.get_user(info_about_action[0]) is not None:
                        db.refill(info_about_action[0], info_about_action[1])
                        send_message(info_about_action[0], f'Тебе выдана премия в размере {info_about_action[1]} руб.')
                        send_message(user_id, 'Успешно!')
                    else:
                        send_message(user_id, 'Пользователь с этим chat_id отсутствует')
                elif len(user_message.split('-')) == 2:
                    info_about_action = user_message.replace(' ', '').split('-')
                    user_info = db.get_user(info_about_action[0])
                    if user_info is not None:
                        if user_info['balance'] >= int(info_about_action[1]):
                            db.withdraw(info_about_action[0], info_about_action[1])
                            send_message(info_about_action[0], f'С тебя списали {info_about_action[1]} руб.')
                            send_message(user_id, 'Успешно!')
                        else:
                            send_message(user_id, 'Нельзя списать больше, чем есть.')
                    else:
                        send_message(user_id, 'Пользователь с этим chat_id отсутствует')
                else:
                    send_message(user_id, f'Неправильный ввод. Нужно ввести chat_id действие сумма. Например: {user_id}+100. Это пополнение на 100 рублей.')

        # ----- ОСНОВНОЙ БЛОК СООБЩЕНИЙ -----
        if user_message.lower() in ['мой аккаунт', 'приобрести доступ', 'баланс', 'мой статус', 'мои рефералы', 'узнать баланс', 'пополнить баланс', 'вывести деньги']:
            user_info = db.get_user(user_id)
            if user_info is None:
                send_message(user_id, 'Ты не зарегистрирован в системе!')
                return "ok"
        if user_message.lower() == 'назад' or user_message.lower() == 'отмена':
            send_message(user_id, f'Возврат в главное меню...', keyboard=kb.kb_main(user_id))
        elif user_message.lower() == '/start':
            send_message(user_id, get_from_txt('START_TEXT').replace('\\n', '%0A'), line_break=True, keyboard=kb.kb_main(user_id))
        elif user_message.lower() == 'регистрация':
            if not db.get_user(user_id):
                send_message(user_id, f'Если хочешь зарегистрироваться в системе, отправь мне свой логин. \nЛогин может содержать латиницу (английские буквы) и цифры, он должен быть уникальным '
                                      f'и состоять как минимум из 6 символов, но не превышать 20 символов. Буду ждать 2 минуты.', keyboard=kb.kb_break())
                tasks[user_id] = {'action': 'регистрация', 'time': time.time()}
            else:
                send_message(user_id, 'Ты уже зарегистрирован!')
        elif user_message.lower() == 'мой аккаунт':
            send_message(user_id, f'Что тебя интересует?', keyboard=kb.kb_account())
        elif user_message.lower() == 'баланс':
            send_message(user_id, f'Что хочешь сделать?', keyboard=kb.kb_balance())
            tasks[user_id] = {'action': 'баланс'}
        elif user_message.lower() in ['узнать баланс', 'пополнить баланс', 'вывести деньги']:
            tasks[user_id] = {'action': 'баланс'}
            balance(user_id, user_message)
        elif user_message.lower() == 'о нас':
            send_message(user_id, get_from_txt('ABOUT_US').replace('\\n', '%0A'), line_break=True)
        elif user_message.lower() == 'о проекте':
            send_message(user_id, get_from_txt('ABOUT_PROJECT').replace('\\n', '%0A'), line_break=True)
        elif user_message.lower() == 'новости':
            send_message(user_id, get_from_txt('NEWS').replace('\\n', '%0A'), line_break=True)
        elif user_message.lower() == 'помощь':
            send_message(user_id, get_from_txt('HELP').replace('\\n', '%0A'), line_break=True, keyboard=kb.kb_help())
        elif user_message.lower() == 'техподдержка':
            send_message(user_id, 'Сообщение', user_link=True)
        elif user_message.lower() == 'админ панель':
            if user_id == 404587021 or user_id == 511872773:
                send_message(user_id, 'Командуй', keyboard=kb.kb_admin_panel())
            else:
                send_message(user_id, 'Нет доступа')
        elif user_message.lower() == 'обновить текст':
            if user_id == 404587021 or user_id == 511872773:
                edit_env()
                send_message(user_id, 'Обновлено')
            else:
                send_message(user_id, 'Нет доступа')
        elif user_message.lower() == 'изменить баланс человека':
            if user_id == 404587021 or user_id == 511872773:
                send_message(user_id, f'Отправь мне chat_id пользователя, которому нужно изменить баланс, '
                                      f'а затем укажи действие(минус или плюс) и сумму.%0aНапример: {user_id}+100 или {user_id}-100. '
                                      f'Первый вариант - пополнение, второй - списание.', keyboard=kb.kb_break(), line_break=True)
                tasks[user_id] = {'action': 'изменить баланс человека', 'time': time.time()}
            else:
                send_message(user_id, 'Нет доступа')
        elif user_message.lower() == 'мой статус':
            user_info = db.get_user(user_id)
            if user_info['access'] == 1:
                access = 'Доступ приобретён'
            else:
                access = 'Доступ не приобретён'
            send_message(user_id, f'Твой статус - {user_info["status"]}.%0AТвой никнейм - {user_info["nickname"]}.%0A{access}', line_break=True)
        elif user_message.lower() == 'мои рефералы':
            user_referrals = db.check_referrals(user_id)
            if not user_referrals:
                send_message(user_id, 'У тебя нет рефералов.')
            else:
                stroke = 'Твои рефералы:%0A'
                for x in user_referrals:
                    stroke = stroke + x + '%0A'
                send_message(user_id, stroke, line_break=True)
        elif user_message.lower() == 'приобрести доступ':
            user_info = db.get_user(user_id)
            if user_info['access'] == 1:
                send_message(user_id, 'Доступ уже приобретён')
                return "ok"
            if user_info['balance'] < 1000:
                send_message(user_id, 'Стоимость доступа - 1000 рублей. На твоём счету недостаточно средств.')
                return "ok"
            send_message(user_id, 'Стоимость доступа - 1000 рублей. Если готов купить, то отправь мне никнейм человека, который тебя пригласил. Если такого человека нет, просто отправь мне символ точки.', keyboard=kb.kb_break())
            tasks[user_id] = {'action': 'покупка доступа', 'time': time.time(), 'nickname': user_info['nickname']}
            return "ok"

    return "ok"


@app.route('/qiwi_bill', methods=['POST'])
def qiwi_process():
    if list(request.json.keys())[0] == 'bill':
        print(request.json)
        try:
            amount = request.json['bill']['amount']['value']  # Сумма платежа
            status = request.json['bill']['status']['value']  # Проверка успеха платежа
            # comment = request.json['bill']['comment']  # Логин в реферальной системе
            user_id = request.json['bill']['customer']['account']  # chat_id
            invoice_parameters = f"{request.json['bill']['amount']['currency']}|{amount}|{request.json['bill']['billId']}|{request.json['bill']['siteId']}|{status}"
            hash = hmac.new((get_from_env('SECRET_QIWI_TOKEN')).encode('UTF-8'), invoice_parameters.encode('UTF-8'), hashlib.sha256)
            if hash.hexdigest() == request.headers['X-Api-Signature-SHA256']:
                if status == 'PAID':
                    if db.refill(user_id, amount.split(".")[0]):
                        send_message(user_id, f'Твой баланс успешно пополнен на {amount.split(".")[0]} руб. !')
                    else:
                        send_message(user_id, 'Произошла ошибка в пополнении, обратись за помощью.')
            else:
                print('Странный платёж...!')
        except Exception as e:
            print(e)
            print('Что то пошло не так!\n', traceback.format_exc())

    return "ok"


@app.route('/list', methods=['GET'])
def session_list():
    return render_template('list.html', users=db.datalist_users(), referrals=db.datalist_referrals())


if __name__ == '__main__':
    app.run()
