import json
import logging
import os
import sys
import time

import requests
import telebot
from dotenv import load_dotenv
from telebot import TeleBot

import exceptions

load_dotenv()

log_file_path = os.path.join(os.getcwd(), 'main.log')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_file_handler = logging.FileHandler(
    filename=log_file_path, mode='w', encoding='utf-8'
)
stream_handler = logging.StreamHandler(sys.stdout)

formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
log_file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

logger.addHandler(log_file_handler)
logger.addHandler(stream_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class Phrases:
    """Фразы для логирования."""

    MISS_PRACTICUM_TOKEN = 'Отсутствует PRACTICUM_TOKEN'
    MISS_TELEGRAM_TOKEN = 'Отсутствует TELEGRAM_TOKEN'
    MISS_TELEGRAM_CHAT_ID = 'Отсутствует TELEGRAM_CHAT_ID'
    NOT_DICT = 'не является словарем.'
    NO_KEY_HOMEWORKS = 'Ответ API не содержит "homeworks" ключа.'
    NO_KEY_CURRENT_DATE = 'Ответ API не содержит "current_date" ключа.'
    NOT_LIST = 'не является списком.'
    NOT_INT = 'не является целым числом.'
    STATUS_RESPONSE = 'Статус ответа на запрос'
    UNKNOWN_HW_STATUS = 'Неизвестный статус домашней работы'
    FOREIGN_KEY = 'ключ не найден в словаре "homework"'
    CAN_NOT_DECODE_JSON = 'Ошибка декодирования JSON'
    NO_NEW_HOMEWORKS = 'Новых результатов не обнаружено'
    KEY_ERROR = 'Ошибка с ключом'
    PROGRAMM_FAILURE = 'Сбой в работе программы'
    SEND_MESSAGE_ERROR = 'Ошибка отправки сообщения'
    SEND_MESSAGE_SUCCESS = 'Сообщение успешно отправлено'


def check_tokens():
    """Проверка доступности переменных окружения."""
    missing_tokens = []
    tokens_to_check = {
        PRACTICUM_TOKEN: Phrases.MISS_PRACTICUM_TOKEN,
        TELEGRAM_TOKEN: Phrases.MISS_TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID: Phrases.MISS_TELEGRAM_CHAT_ID,
    }
    for token, phrase in tokens_to_check.items():
        if not token:
            missing_tokens.append(phrase)
    if missing_tokens:
        logger.critical(', '.join(missing_tokens))
        raise exceptions.TokenMissError(', '.join(missing_tokens))


def send_message(bot, message):
    """Отправка сообщения в чат телеги."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telebot.apihelper.ApiException as error:
        message = f'{Phrases.SEND_MESSAGE_ERROR}: {error}'
        logger.error(message)
    else:
        logger.debug(f'{Phrases.SEND_MESSAGE_SUCCESS}.')
    return message


def check_repeat_message(bot, message, last_message):
    """Проверка на повтор сообщения."""
    if last_message != message:
        send_message(bot, message)
        return message
    return last_message


def get_api_answer(timestamp):
    """Делаем запрос к API и возвращаем ответ в формате Python."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != 200:
            raise exceptions.RequestError(
                f'{Phrases.STATUS_RESPONSE} {response.status_code}'
            )
        return response.json()
    except json.JSONDecodeError as error:
        raise exceptions.JsonDecodeError(
            f'{Phrases.CAN_NOT_DECODE_JSON} "{error}"'
        )
    except requests.RequestException as error:
        raise exceptions.RequestError(
            f'{Phrases.STATUS_RESPONSE} {response.status_code} "{error}"'
        )


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(f'{response} {Phrases.NOT_DICT}')
    if 'homeworks' not in response:
        raise KeyError(Phrases.NO_KEY_HOMEWORKS)
    if 'current_date' not in response:
        raise exceptions.CurrentDateKeyError(Phrases.NO_KEY_CURRENT_DATE)
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        raise exceptions.CurrentDateKeyTypeError(
            f'{current_date} {Phrases.NOT_INT}'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(f'{homeworks} {Phrases.NOT_LIST}')


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if not homework_name:
        homework_name_key = 'homework_name'
        raise KeyError(f'"{homework_name_key}" {Phrases.FOREIGN_KEY}.')
    if not status:
        status_name_key = 'status'
        raise KeyError(f'"{status_name_key}" {Phrases.FOREIGN_KEY}.')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise ValueError(f'{Phrases.UNKNOWN_HW_STATUS}: {status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            if homeworks:
                message = parse_status(homeworks[-1])
                last_message = check_repeat_message(
                    bot, message, last_message
                )
            else:
                logger.debug(Phrases.NO_NEW_HOMEWORKS)
            timestamp = response.get('current_date', timestamp)
        except exceptions.CurrentDateError as error:
            logger.error(f'{Phrases.KEY_ERROR}: {error}')
        except Exception as error:
            message = f'{Phrases.PROGRAMM_FAILURE}: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
