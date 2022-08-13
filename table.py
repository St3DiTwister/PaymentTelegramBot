import gspread

# Берёт данные из таблицы google sheets для изменения текста внутри бота

gc = gspread.service_account(filename='json google sheets')
sh = gc.open_by_key("TOKEN")


def edit_env():
    worksheet = sh.worksheet('Текст')
    list_of_list = worksheet.get_all_values()
    text = ''
    list_of_list = [x.replace('\n', '\\n') for x in list_of_list[1]]
    with open('bot_text.env', 'w', encoding='utf-8') as file:
        text = text + 'START_TEXT=' + '"' + list_of_list[0] + '"' + '\n'
        text = text + 'ABOUT_US=' + '"' + list_of_list[1] + '"' + '\n'
        text = text + 'ABOUT_PROJECT=' + '"' + list_of_list[2] + '"' + '\n'
        text = text + 'NEWS=' + '"' + list_of_list[3] + '"' + '\n'
        text = text + 'HELP=' + '"' + list_of_list[4] + '"' + '\n'
        text = text + 'ACCESS_LINK' +'"' + list_of_list[5] + '"' + '\n'
        file.write(text)


edit_env()