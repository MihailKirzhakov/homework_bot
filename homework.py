import json
import logging
import os
import time

import requests

from dotenv import load_dotenv
from telebot import TeleBot

import exceptions

load_dotenv()

# Получаем текущую рабочую директорию
current_dir = os.getcwd()

# Формируем полный путь к файлу лога
log_file_path = os.path.join(current_dir, 'C:\\Dev\\homework_bot', 'main.log')

logging.basicConfig(
    level=logging.DEBUG,
    filename=log_file_path,
    filemode='w',
    format="%(asctime)s, %(levelname)s, %(message)s",
)

logger = logging.getLogger(__name__)

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

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

PHRASES = {
    'MISS_PRACTICUM_TOKEN': 'Отсутствует PRACTICUM_TOKEN',
    'MISS_TELEGRAM_TOKEN': 'Отсутствует TELEGRAM_TOKEN',
    'MISS_TELEGRAM_CHAT_ID': 'Отсутствует TELEGRAM_CHAT_ID',
    'API_RESPONSE_ERROR': 'Ошибка запроса к API',
    'NOT_DICT': 'не является словарем.',
    'NO_KEY_HOMEWORKS': 'Ответ API не содержит "homeworks" ключа.',
    'NO_KEY_CURRENT_DATE': 'Ответ API не содержит "current_date" ключа.',
    'NOT_LIST': 'не является списком.',
    'NOT_INT': 'не является целым числом.',
    'SEND_MESSAGE_ERROR': 'Ошибка отправки сообщения',
    'STATUS_RESPONSE': 'Статус ответа на запрос',
    'NO_HW_STATUS': 'Отсутствует информация о домашней работе.',
    'UNKNOWN_HW_STATUS': 'Неизвестный статус домашней работы',
    'FOREIGN_KEY': 'ключ не найден в словаре "homework"',
    'CAN_NOT_DECODE_JSON': 'Ошибка декодирования JSON',
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    if not PRACTICUM_TOKEN:
        logger.critical(PHRASES.get('MISS_PRACTICUM_TOKEN'))
        raise exceptions.TokenMissError(PHRASES.get('MISS_PRACTICUM_TOKEN'))
    if not TELEGRAM_TOKEN:
        logger.critical(PHRASES.get('MISS_TELEGRAM_TOKEN'))
        raise exceptions.TokenMissError(PHRASES.get('MISS_TELEGRAM_TOKEN'))
    if not TELEGRAM_CHAT_ID:
        logger.critical(PHRASES.get('MISS_TELEGRAM_CHAT_ID'))
        raise exceptions.TokenMissError(PHRASES.get('MISS_TELEGRAM_CHAT_ID'))


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'{PHRASES.get("SEND_MESSAGE_ERROR")}: {error}')
    else:
        logger.debug(f'Успешно отправлено сообщение: {message}')


def get_api_answer(timestamp):
    """Делаем запрос к API и возвращаем ответ в формате Python."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != 200:
            raise requests.RequestException(
                f'{PHRASES.get("STATUS_RESPONSE")} {response.status_code}'
            )
        logger.debug('Успешно получен JSON-ответ.')
        response_json = response.json()
    except json.JSONDecodeError as error:
        logger.error(f'{PHRASES.get("CAN_NOT_DECODE_JSON")}: {error}')
        send_message(f'{PHRASES.get("CAN_NOT_DECODE_JSON")} {error}')
        raise
    except requests.RequestException(
        f'{PHRASES.get("STATUS_RESPONSE")} {response.status_code}'
    ) as error:
        logger.error(f'{PHRASES.get("API_RESPONSE_ERROR")}: {error}')
        send_message(f'{PHRASES.get("API_RESPONSE_ERROR")}: {error}')
    return response_json


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error(f'{response} {PHRASES.get("NOT_DICT")}')
        send_message(f'{response} {PHRASES.get("NOT_DICT")}')
        raise TypeError(f'{response} {PHRASES.get("NOT_DICT")}')
    if 'homeworks' not in response:
        logger.error(PHRASES.get('NO_KEY_HOMEWORKS'))
        send_message(PHRASES.get('NO_KEY_HOMEWORKS'))
        raise TypeError(PHRASES.get('NO_KEY_HOMEWORKS'))
    if 'current_date' not in response:
        logger.error(PHRASES.get('NO_KEY_CURRENT_DATE'))
        send_message(PHRASES.get('NO_KEY_CURRENT_DATE'))
        raise TypeError(PHRASES.get('NO_KEY_CURRENT_DATE'))
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        logger.error(f'{current_date} {PHRASES.get("NOT_INT")}')
        send_message(f'{current_date} {PHRASES.get("NOT_INT")}')
        raise TypeError(f'{current_date} {PHRASES.get("NOT_INT")}')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logger.error(f'{homeworks} {PHRASES.get("NOT_LIST")}')
        send_message(f'{homeworks} {PHRASES.get("NOT_LIST")}')
        raise TypeError(f'{homeworks} {PHRASES.get("NOT_LIST")}')
    logger.debug('Ответ API соответствует критериям')


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if not homework_name:
        homework_name_key = 'homework_name'
        logger.error(f'"{homework_name_key}" {PHRASES.get("FOREIGN_KEY")}.')
        send_message(f'"{homework_name_key}" {PHRASES.get("FOREIGN_KEY")}.')
        raise KeyError(f'"{homework_name_key}" {PHRASES.get("FOREIGN_KEY")}.')
    if not status:
        status_name_key = 'status'
        logger.error(f'"{status_name_key}" {PHRASES.get("FOREIGN_KEY")}.')
        send_message(f'"{status_name_key}" {PHRASES.get("FOREIGN_KEY")}.')
        raise KeyError(f'"{status_name_key}" {PHRASES.get("FOREIGN_KEY")}.')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        logger.error(f'{PHRASES.get("UNKNOWN_HW_STATUS")}: {status}')
        send_message(f'{PHRASES.get("UNKNOWN_HW_STATUS")}: {status}')
        raise KeyError(f'{PHRASES.get("UNKNOWN_HW_STATUS")}: {status}')
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
                if last_message != message:
                    send_message(bot, message)
                    last_message = message
            timestamp = response.get('current_date', timestamp)
        except requests.RequestException as error:
            logger.error(f'{PHRASES.get("API_RESPONSE_ERROR")}: {error}')
            send_message(bot, f'{PHRASES.get("API_RESPONSE_ERROR")}: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_message != message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
