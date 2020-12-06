import ast
import datetime as date
from pytz import timezone
import os
import pickle
import urllib.request
from collections import defaultdict
from random import choice
import telebot
from telebot import types
import requests
import json
import subprocess
import logging
import tokens

#   ВНИМАНИЕ.
# Прошу без разбора не копировать код к себе, ибо так вы ничему не научитесь.
# Данный код не будет полностью работоспособен на repl.it так как использует
# для голосового управления стороннюю программу которую туда не установить
# Потестить самого бота можно тут: @SNTRKbot

HELP = '''
<b>Список доступных команд:</b>

* /<b>add</b>  - <i>Добавить задачу </i>
    <i>Формат:</i> <b>/add 23-11-2020 #Категория Задача</b>
    <i>Или запишите голосовое сообщение, </i>
    <i>Пример:</i> <b>"завтра Категория Задача"</b>
* /<b>print</b> - <i>Показать задачи по дате</i>
* /<b>category</b> - <i>Показать задачи по категории</i>
* /<b>showall</b> - <i>Показать все задачи</i>
* /<b>delete</b> - <i>Удаление задачи из списка</i>
* /<b>export</b> - <i>Записывает задачи в файл picke.dump и отправляет вам</i>
* <i>Пришлите файл picke.dump для импорта.</i> <b>Без команды</b>
* /<b>help</b> - <i>Выводит данное сообщение</i> 
* /<b>cat</b> - <i>Показать рандомного котика</i>
* /<b>test</b> - <i>Загрузить тестовые задачи</i>

Вместо формата даты DD-MM-YYYY, доступно today/сегодня, tomorrow/завтра или later/позже.
'''
# Все токены вынесены в отдельный файл и импортированы как модуль import tokens
token = tokens.bot_token  # Получаем токен бота
API_ENDPOINT = tokens.api_url  # Получаем ссылку сервиса для преобразования голоса в текст
ACCESS_TOKEN = tokens.api_token  # Получаем токен для преобразования голоса в текст
MY_DICT = defaultdict(list)  # Создаём словарь (он более навороченный чем обычный)
RANDOM_LIST = [i for i in range(1, 15)]  # Создаём список для рандомного котика


def time_tz(*args):
    return date.datetime.now(tz).timetuple()


# Настройки логгера и timezone для правильного отображения времени в логах
tz = timezone('Europe/Moscow')
logger = logging.getLogger('ToDoBot')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('todobot.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
formatter.converter = time_tz
fh.setFormatter(formatter)
logger.addHandler(fh)

bot = telebot.TeleBot(token)

# Создаём кнопки для клавиатуры с главными командами
keyboard1 = telebot.types.ReplyKeyboardMarkup()
keyboard1.row('/category', '/print', '/showall')
keyboard1.row('/delete', '/help', '/cat')


# region CREATE TEST DICTIONARY
# Функция которая загрузит тестовые задачи в словарь.
def test():
    test_date = ['2020-12-02', '2020-11-19', '2020-12-09', '2020-11-19', '2020-11-30']
    test_cate = ['#улица', '#дома', '#работа', '#работа', '#дома']
    test_task = ['Утренная пробежка', 'Выучить питон', 'Оттестировать бота', 'Написать бота', 'Повесить люстру']
    for i in range(len(test_date)):
        MY_DICT[test_date[i]].append((test_cate[i], test_task[i]))


# endregion


# region ADD USER TASK IN DICTIONARY -> DATE FUNCTION
def add_task(a_dict, a_date, a_task, a_category):
    # Конвертирование даты и проверка на валидность в day_convert() a_date -> check
    # Проверка на длинну задачи
    # Добавление задачи
    logger.info(f'Add task {a_dict}, {a_date}, {a_task}, {a_category}')
    check = dt_day_convert(a_date.lower())
    logger.info(f'Day converter return {check}')
    if len(a_task) > 3:
        if check != 'error':
            a_dict[check].append((a_category.lower(), a_task.capitalize()))
            msg = f'Задача {a_task.capitalize()} добавлена на {dt_mysql_to_human(check)} !'
            logger.info(msg)
            return msg
        else:
            msg = 'Такой даты не существует.'
            logger.info(msg)
            return msg
    else:
        msg = 'Описание задачи слишком короткое'
        logger.info(msg)
        return msg


# endregion


# region DATE FUNCTION
# Даты в словаре всегда хранятся в формате ГГГГ-ММ-ДД потому что так они верно сортируются
# Пользователь вводит в формате более удобном ДД-ММ-ГГГГ
# Также кое-где в ответах мы пользователю выводим в формате ДД Месяц ГГГГ
# Для этого ниже есть функции конвертации

def dt_day_convert(a_date):
    logger.info(f'Func dt_day_converter: {a_date}')
    # Конвертирование дат в формат ГГГГ-ММ-ДД
    # Проверка даты на валидность check_date()
    if a_date == 'today' or a_date == 'сегодня':
        day = date.datetime.today().strftime('%Y-%m-%d')
        return day
    elif a_date == 'tomorrow' or a_date == 'завтра':
        day = date.datetime.today() + date.timedelta(days=1)
        day = day.strftime('%Y-%m-%d')
        return day
    elif a_date == 'later' or a_date == 'позже':
        day = date.datetime.today() + date.timedelta(days=2)
        day = day.strftime('%Y-%m-%d')
        return day
    else:
        day = dt_check_date(a_date)
        day = dt_date_to_mysql(day)
        return day


def dt_check_date(valid_date):
    # Валидатор даты
    try:
        date.datetime.strptime(valid_date, '%d-%m-%Y')
        return valid_date
    except ValueError:
        x = 'error'
        return x


def dt_mysql_to_human(a_date):
    # Конвертирование даты из ГГГГ-ММ-ДД в ДД Месяц ГГГГ
    day_form = date.datetime.strptime(a_date, '%Y-%m-%d')
    day_form = day_form.strftime('%d %B %Y')
    return day_form


def dt_date_to_mysql(a_date):
    # Конвертирование даты из ДД-ММ-ГГГГ в ГГГГ-ММ-ДД
    day_form = date.datetime.strptime(a_date, '%d-%m-%Y')
    day_form = day_form.strftime('%Y-%m-%d')
    return day_form


def dt_mysql_to_date(a_date):
    # Конвертирование даты из ГГГГ-ММ-ДД в ДД-ММ-ГГГГ
    day_form = date.datetime.strptime(a_date, '%Y-%m-%d')
    day_form = day_form.strftime('%d-%m-%Y')
    return day_form


# endregion


# region SHOW TASKS, CATEGORIES
def find_category(find):
    logger.info(f'Func find_category: {find}')
    # Выборка из словаря указанной пользователяем категории
    line = ''
    for k in MY_DICT.keys():
        for i in MY_DICT[k]:
            if find in i:
                line += f'{dt_mysql_to_date(k)} : {i[0]} - {i[1]}\n'
    return line


def show_all_categories():
    logger.info(f'Func show_all_categories.')
    # Выборка всех существующих категорий
    temp_list = list()
    for k in MY_DICT.keys():
        for i in MY_DICT[k]:
            temp_list.append(i[0])
    s = set(temp_list)  # преобразование в set() удаляет повторы
    return s


def show_task(a_date):
    logger.info(f'Func show_task: {a_date}')
    # Выборка задач по указанной пользователем дате
    tasks = ''
    list_keys = sort_keys(MY_DICT.keys())
    for k in list_keys:
        if a_date == k:
            for i in MY_DICT[k]:
                tasks += f'{dt_mysql_to_date(k)}, {i[0]}, {i[1]}\n'
    return tasks


def show_all_task(a):
    logger.info(f'Func show_all_task: {a}')
    # Возвращает все задачи из словаря
    tasks = ''
    list_keys = sort_keys(a.keys())
    for k in list_keys:
        for i in a[k]:
            tasks += f'{dt_mysql_to_date(k)}, {i[0]}, {i[1]}\n'
    return tasks


# endregion


# region IMPORT / EXPORT
def task_dump(a_dict):
    # Сохранение задач в файл
    with open('./data.pickle', 'wb') as f:
        pickle.dump(a_dict, f)
        logger.info(f'Create tasks dump file')


def save_file(file_id_info):
    # Скачивание файла при получение его от пользователя
    file = bot.download_file(file_id_info.file_path)
    logger.info(f'Download dump file: {file_id_info.file_path}')
    with open('./data.pickle', 'wb') as new_file:
        new_file.write(file)
        logger.info(f'Write dump to file')


def task_load(a_dict):
    # Загрузка скачанного в save_file() дампа в словарь
    with open('./data.pickle', 'rb') as f:
        a_dict = pickle.load(f)
        logger.info(f'Load tasks to dictionary')
    return a_dict


# endregion


def read_audio(filename):
    # Чтение файла для отправки на распознование текста
    with open(filename, 'rb') as f:
        audio = f.read()
        logger.info(f'Read wav audio to sent WIT')
    return audio


def resend_img(url):
    # Сохранение рандомного котика для последующей отправки пользователю
    f = open('out.jpg', 'wb')
    f.write(urllib.request.urlopen(url).read())
    logger.info(f'Save cat file to HDD')
    f.close()


def sort_keys(a_keys):
    # Функция для сортировки задач по дате
    list_keys = list(a_keys)
    list_keys.sort()
    logger.info(f'Sort keys return: {list_keys}')
    return list_keys


def get_task_index(key):
    # Получения индекса в списке задач, для удаления, когда 2 и более задачи на 1 дату.
    li = list()
    x = MY_DICT.get(TEMP)
    for i, k in x:
        li.append(k)
    logger.info(f'list index return: {li.index(key)}')
    return li.index(key)


def del_file(filename):
    # Функция проверяет существует ли такой файл и если да то удаляет его
    if os.path.exists(filename):
        os.remove(filename)
        logger.info(f'Delete file: {filename}')


# region INLINE KEYBOARD
# Генераторы встроенных в сообщение клавиатур (InlineKeyboard)
def Category_Keyboard():
    markup = types.InlineKeyboardMarkup()
    category = show_all_categories()
    for key in category:
        markup.add(types.InlineKeyboardButton(text=key, callback_data="['key', '" + key + "']"))
    return markup


def Delete_Keyboard():
    markup = types.InlineKeyboardMarkup()
    for key, val in MY_DICT.items():
        if len(val) > 1:
            val = 'несколько задач, показать?'
            markup.add(types.InlineKeyboardButton(text=f'{dt_mysql_to_date(key)} {str(val)}',
                                                  callback_data="['del', '" + key + "']"))
        else:
            markup.add(types.InlineKeyboardButton(text=f'{dt_mysql_to_date(key)} {str(val[0][1])}',
                                                  callback_data="['del', '" + key + "']"))
    return markup


def More_Task(a_date):
    markup = types.InlineKeyboardMarkup()
    x = MY_DICT.get(a_date)
    for i in x:
        markup.add(types.InlineKeyboardButton(text=i[1], callback_data="['delete', '" + i[1] + "']"))
    return markup


def Show_Task_Keyboard():
    markup = types.InlineKeyboardMarkup()
    list_keys = sort_keys(MY_DICT.keys())
    for i in list_keys:
        num = len(MY_DICT[i])
        markup.add(types.InlineKeyboardButton(text=f'{dt_mysql_to_date(i)} задач: {num}',
                                              callback_data="['show_task', '" + i + "']"))
    return markup


def Show_More_Task(a_date):
    markup = types.InlineKeyboardMarkup()
    for key, val in MY_DICT.get(a_date):
        markup.add(types.InlineKeyboardButton(text=f'{key} {str(val)}', callback_data="['back', '" + key + "']"))
    return markup


# endregion

# Эта секция CallBack, отвечает за действия при нажатие кнопок на InlineKeyboard
# Из секции выше приходит callback_data="['del', '" + key + "']", по сути это команда 'del'
# и значение переменной 'key' которое мы получили после определенных действий в функциях выше

# Вот так мы получем команду call.data.startswith("['key'") и ставим условие что бы выполнять определенные действия
# А вот так keyFromCallBack = ast.literal_eval(call.data)[1] мы получаем значение той самой переменной
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    global TEMP
    logger.info(f'{call.message.chat.id} - CALLBACK')
    if (call.data.startswith("['key'")):
        logger.info(f'{call.message.chat.id} - CALLBACK - key')
        task = ''
        keyFromCallBack = ast.literal_eval(call.data)[1]
        task += find_category(keyFromCallBack)
        msg = f'{task}'
        bot.send_message(call.message.chat.id, msg)

    if (call.data.startswith("['del'")):
        logger.info(f'{call.message.chat.id} - CALLBACK - del')
        keyCallBack = ast.literal_eval(call.data)[1]
        if len(MY_DICT[keyCallBack]) > 1:
            KEYBOARD = More_Task(keyCallBack)
            TEMP = keyCallBack
            # Используем bot.edit_message_text для редактирования сообщения а не отправки нового
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  text="На этот день несколько задач, какую удалить?",
                                  message_id=call.message.message_id,
                                  reply_markup=KEYBOARD,  # переменная в которую уже сгенерированна inline клавиатура
                                  parse_mode='HTML')  # Используем HTML для корректного отображения.
        else:
            x = MY_DICT.pop(keyCallBack)
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  text=f'Задача {x} удалена.',
                                  message_id=call.message.message_id,
                                  reply_markup=Delete_Keyboard(),  # функция генерации inline клавиатуры
                                  parse_mode='HTML')

    if (call.data.startswith("['delete'")):
        logger.info(f'{call.message.chat.id} - CALLBACK - delete')
        keyFromCallBack = ast.literal_eval(call.data)[1]
        n = get_task_index(keyFromCallBack)
        del MY_DICT[TEMP][n]
        bot.edit_message_text(chat_id=call.message.chat.id,
                              text=f'Задача {keyFromCallBack} удалена.',
                              message_id=call.message.message_id,
                              reply_markup=Delete_Keyboard(),
                              parse_mode='HTML')

    if (call.data.startswith("['show_task'")):
        logger.info(f'{call.message.chat.id} - CALLBACK - showtask')
        keyFromCallBack = ast.literal_eval(call.data)[1]
        KEYBOARD = Show_More_Task(keyFromCallBack)
        TEMP = keyFromCallBack
        bot.edit_message_text(chat_id=call.message.chat.id,
                              text=f'Ваши задачи на {dt_mysql_to_date(keyFromCallBack)} \n'
                                   f'Нажмите на любую задачу для возврата назад.',
                              message_id=call.message.message_id,
                              reply_markup=KEYBOARD,
                              parse_mode='HTML')

    if (call.data.startswith("['back'")):
        logger.info(f'{call.message.chat.id} - CALLBACK back')
        bot.edit_message_text(chat_id=call.message.chat.id,
                              text=f'Выберите дату на которую показать задачи.',
                              message_id=call.message.message_id,
                              reply_markup=Show_Task_Keyboard(),
                              parse_mode='HTML')


@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f'{message.chat.id} - START - {message.text}')
    bot.send_message(message.chat.id, 'Бот запущен.', reply_markup=keyboard1)


@bot.message_handler(commands=['help'])
def help_msg(message):
    logger.info(f'{message.chat.id} - HELP - {message.text}')
    bot.send_message(message.chat.id, HELP, parse_mode='HTML', reply_markup=keyboard1)


@bot.message_handler(commands=['add'])
def add(message):
    logger.info(f'{message.chat.id} - ADD - {message.text}')
    try:
        _, day, category, task = message.text.split(maxsplit=3)
        task = ' '.join([task])
        if category[0] != '#':
            category = '#' + category
        msg = add_task(MY_DICT, day, task, category)
    except ValueError:
        msg = 'Ошибка в формате добавления\n' \
              'Используйте /add 23-11-2020 #Категория Задача'
        logger.exception('Error ValueError')
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['print'])
def print_(message):
    logger.info(f'{message.chat.id} - PRINT - {message.text}')
    if len(MY_DICT) > 1:
        msg = 'Выберите дату на которую показать задачи.'
    else:
        msg = 'У вас еще нету задач.'
    bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=Show_Task_Keyboard())


@bot.message_handler(commands=['showall'])
def printall_(message):
    logger.info(f'{message.chat.id} - SHOW ALL - {message.text}')
    if len(MY_DICT) > 0:
        msg = show_all_task(MY_DICT)
    else:
        msg = 'Вы ещё не добавили задач.'
    bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=keyboard1)


@bot.message_handler(commands=['category'])
def cat_list_(message):
    logger.info(f'{message.chat.id} - CATEGORY - {message.text}')
    if len(MY_DICT) > 0:
        msg = 'Выберите категорю для отображения задач в ней.'
    else:
        msg = 'У вас ещё нет категорий.'
    bot.send_message(message.chat.id, msg, reply_markup=Category_Keyboard())


@bot.message_handler(commands=['delete'])
def delete_(message):
    logger.info(f'{message.chat.id} - DELETE - {message.text}')
    msg = 'Удалите задачу нажатием на кнопку.'
    bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=Delete_Keyboard())


@bot.message_handler(commands=['export'])
def download(message):
    logger.info(f'{message.chat.id} - EXPORT - {message.text}')
    task_dump(MY_DICT)
    doc = open('./data.pickle', 'rb')
    bot.send_document(message.chat.id, doc)


@bot.message_handler(content_types=['document'])
def handle_docs(message):
    logger.info(f'{message.chat.id} - IMPORT')
    file_id_info = bot.get_file(message.document.file_id)
    save_file(file_id_info)
    MY_DICT.update(task_load(MY_DICT))
    del_file('data.pickle')
    bot.send_message(message.chat.id, f'Задачи импортированы')


# Этот хендлер отвечает за обработку голосовых команд

@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    logger.info(f'{message.chat.id} - VOICE')
    # Сохраняем голосовое сообщение на компьютер
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open('new_file.ogg', 'wb') as new_file:
        new_file.write(downloaded_file)
    # Конвертируем из OGG в WAV сторонним линуксовским приложением FFMPEG
    process = subprocess.run(['ffmpeg', '-y', '-i', 'new_file.ogg', 'output.wav'])
    if process.returncode != 0:
        raise Exception("Something went wrong")
    # Удаляем скачанный файл после конвертации
    del_file('new_file.ogg')
    # Отправляем файл для получения текста из голоса на сторонний сервис wit.ai.
    # Есть подобные сервисы от Google и Yandex,
    # но там даже для пробного периода надо карту привязать а я не хочу!
    audio = read_audio('output.wav')
    headers = {'authorization': 'Bearer ' + ACCESS_TOKEN,
               'Content-Type': 'audio/wav'}
    resp = requests.post(API_ENDPOINT, headers=headers, data=audio)
    # Получаем ответ в json виде и забираем из него только нужное нам
    data = json.loads(resp.content)
    temp_msg = data['text']
    # Удаляем файл который конвертировали ffmpeg
    del_file('output.wav')
    try:
        # Полученный от wit.ai текст разбиваем на переменные и передаём обычной функции добавления задачи
        day, category, task = temp_msg.split(maxsplit=2)
        task = ' '.join([task])
        msg = add_task(MY_DICT, day, task, '#' + category)
    except ValueError:
        msg = 'Ошибка в формате добавления\n' \
              'сегодня/завтра/позже Категория Задача'
        logger.exception('Error ValueError')
    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['test'])
def random(message):
    logger.info(f'{message.chat.id} - TEST DATA - {message.text}')
    test()
    bot.send_message(message.chat.id, f'Тестовые данные загружены')


@bot.message_handler(commands=['cat'])
def cat(message):
    logger.info(f'{message.chat.id} - CAT - {message.text}')
    le = choice(RANDOM_LIST)
    resend_img('https://sntrk.ru/img/cats/' + str(le) + '.jpg')
    with open('out.jpg', 'rb') as im_f:
        bot.send_photo(message.chat.id, im_f)
    if os.path.exists('out.jpg'):
        os.remove('out.jpg')


# Сервисные команды без слеша CHAT.ID, PRINT.DICT, CLEAR.DICT, BOT.SOURCE.CODE
@bot.message_handler(content_types=['text'])
def send_text(message):
    if message.text == 'service_id':
        logger.info(f'{message.chat.id} - SERVICE - {message.text}')
        bot.send_message(message.chat.id, message.chat.id)
    elif message.text == 'service_dict':
        logger.info(f'{message.chat.id} - SERVICE - {message.text}')
        logger.info(f'{message.chat.id} - DICTIONARY - {str(MY_DICT)}')
    elif message.text == 'service_clear':
        logger.info(f'{message.chat.id} - SERVICE - {message.text}')
        MY_DICT.clear()
    elif message.text == 'service_code':
        logger.info(f'{message.chat.id} - SERVICE - {message.text}')
        doc = open('./main.py', 'rb')
        bot.send_document(message.chat.id, doc)
    else:
        logger.info(f'{message.chat.id} - ERROR COMMANDS - {message.text}')
        bot.send_message(message.chat.id, 'Ошибка, данной команды не существует, используйте /help')


bot.polling(none_stop=True)
