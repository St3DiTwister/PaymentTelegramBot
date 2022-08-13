import sqlite3
sql = sqlite3.connect('PaymentTgBot.db', check_same_thread=False)
c = sql.cursor()


def new_referral(parent_nickname, child_nickname):
    try:
        c.execute("INSERT INTO referrals (parent_nickname, child_nickname) VALUES (?, ?);", (parent_nickname, child_nickname))
        sql.commit()
        return True
    except sql.IntegrityError:
        return False


def get_access(chat_id):
    c.execute("UPDATE users set access = 1 WHERE chat_id=(?)", (chat_id,))
    sql.commit()
    return True


def referrals(new_user):
    while True:
        status = 'Стандарт'
        check_user = c.execute(f"SELECT parent_nickname FROM referrals where child_nickname=(?);", (new_user,)).fetchall()  # выбор пользователя, статус которого проверяем
        if not check_user:  # если список пустой, значит родителя нет, значит проверять нечего
            break
        if check_user == new_user:
            break
        check_user = check_user[0][0]  # выводит никнейм проверяемого юзера
        children = c.execute(f"SELECT child_nickname FROM referrals WHERE parent_nickname=(?);", (check_user,)).fetchall()  # список приглашенных людей
        quantity = 0  # количество людей, которых пригласили приглашенные проверяемого юзера
        for x in children:
            quantity += c.execute(f"SELECT COUNT(child_nickname) FROM referrals where parent_nickname=(?);", (x[0],)).fetchall()[0][0]
        if 3 <= len(children) < 5:
            if quantity >= 2:
                status = 'X Pack'
            else:
                status = 'Стандарт+'
        elif 5 <= len(children) < 10:
            if quantity >= 3:
                status = 'XXL Pack'
            else:
                status = 'XL Pack'
        elif len(children) >= 10:
            if quantity >= 10:
                status = 'Gold+ Pack'
            else:
                status = 'Gold Pack'
        else:
            status = 'Стандарт'
        c.execute("UPDATE users set status=(?) WHERE nickname=(?);", (status, check_user))
        sql.commit()
        new_user = check_user

    return True


def check_registration(chat_id):
    result_from_base = c.execute(f"SELECT * FROM users WHERE chat_id=(?);", (chat_id,)).fetchall()
    if not result_from_base:
        return False
    else:
        return True


def get_user(chat_id):
    user_info = {'chat_id': '', 'balance': '', 'status': '', 'access': '', 'nickname': ''}
    result_from_base = c.execute(f"SELECT * FROM users WHERE chat_id=(?);", (chat_id,)).fetchall()
    if not result_from_base:
        return
    else:
        q = 0
        for x in user_info:
            user_info[x] = result_from_base[0][q]
            q += 1
        return user_info


def add_user(chat_id, nickname):
    try:
        c.execute("INSERT INTO users (chat_id, nickname) VALUES (?, ?);", (chat_id, nickname))
        sql.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def check_nickname(nickname):
    result = c.execute("SELECT nickname from users WHERE nickname LIKE (?);", (nickname,)).fetchall()
    if not result:
        return True
    else:
        return result[0][0]


def refill(chat_id, amount):
    c.execute("UPDATE users set balance = (SELECT users.balance) + (?) WHERE chat_id=(?);", (amount, chat_id))
    sql.commit()
    return True


def withdraw(chat_id, amount):
    balance = c.execute("SELECT balance FROM users WHERE chat_id=(?)", (chat_id,)).fetchall()
    if not balance:
        return False
    if balance[0][0] >= amount:
        c.execute("UPDATE users set balance = (SELECT users.balance) - (?) WHERE chat_id=(?);", (amount, chat_id))
        sql.commit()
    else:
        return False
    return True


def check_referrals(chat_id):
    result = c.execute("SELECT child_nickname FROM referrals WHERE parent_nickname=(SELECT nickname FROM users WHERE chat_id=(?));", (chat_id,)).fetchall()
    list_referrals = [x[0] for x in result]
    return list_referrals


def referral_bonus(new_user):
    amount_bonus = {
        0: 400,
        1: 50,
        2: 25,
        3: 10
    }
    send_bonus = {}
    for x in range(0, 4):
        parent_user = c.execute(f"SELECT parent_nickname, access, chat_id FROM referrals LEFT JOIN users u on u.nickname = referrals.parent_nickname WHERE child_nickname=(?);", (new_user,)).fetchall()
        if not parent_user:
            break
        parent_user = parent_user[0]
        if parent_user[1] == 1:
            c.execute("UPDATE users set balance = (SELECT users.balance) + (?) WHERE nickname=(?);", (amount_bonus.get(x), parent_user[0]))
            sql.commit()
            send_bonus[parent_user[2]] = {'amount': amount_bonus.get(x)}
            print(f'Бонус в размере {amount_bonus.get(x)} начислен: {parent_user[0]}')
        new_user = parent_user[0]
    return send_bonus


def check_parent(user):
    parent_id = c.execute("SELECT chat_id FROM users WHERE nickname=(SELECT parent_nickname FROM referrals WHERE child_nickname=(SELECT nickname FROM users WHERE chat_id=(?)));", (user,)).fetchall()
    return parent_id


def datalist_users():
    users_info = c.execute("SELECT * FROM users").fetchall()
    return users_info


def datalist_referrals():
    referrals_info = c.execute("SELECT * FROM referrals").fetchall()
    return referrals_info