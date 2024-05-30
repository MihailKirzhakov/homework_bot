import logging
import os
import requests
import time

from dotenv import load_dotenv
from telebot import TeleBot

import exceptions

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format="%(asctime)s, %(levelname)s, %(message)s",
)

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
    'miss_env_variables': 'Отсутствуют переменная/ые окружения.',
    'api_response_error': 'Ошибка запроса к API',
    'not_dict': 'не является словарем.',
    'no_key': 'Ответ API не содержит homeworks ключа.',
    'not_list': 'не является списком.',
    'send_message_error': 'Ошибка отправки сообщения',
    'status_response': 'Статус ответа на запрос',
    'no_hw_status': 'Отсутствует информация о домашней работе.',
    'unknown_hw_status': 'Неизвестный статус домашней работы',
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical(PHRASES.get('miss_env_variables'))
        raise exceptions.TokenMissError(PHRASES.get('miss_env_variables'))
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Успешно отправлено сообщение: {message}')
    except Exception as error:
        logging.error(f'{PHRASES.get("send_message_error")}: {error}')


def get_api_answer(timestamp):
    """Делаем запрос к API и возвращаем ответ в формате Python."""
    try:
        logging.debug(f'Запрос к API: {ENDPOINT}')
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != 200:
            logging.error(
                f'{PHRASES.get("status_response")} {response.status_code}'
            )
            send_message(
                f'{PHRASES.get("status_response")} {response.status_code}'
            )
            raise requests.RequestException(
                f'{PHRASES.get("status_response")} {response.status_code}'
            )
        response.raise_for_status()
        logging.debug('Успешно получен JSON-ответ.')
        return response.json()
    except requests.RequestException(
        f'{PHRASES.get("status_response")} {response.status_code}'
    ) as error:
        logging.error(f'{PHRASES.get("api_response_error")}: {error}')
        send_message(f'{PHRASES.get("api_response_error")}: {error}')


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error(f'{response} {PHRASES.get("not_dict")}')
        send_message(f'{response} {PHRASES.get("not_dict")}')
        raise TypeError(f'{response} {PHRASES.get("not_dict")}')
    if 'homeworks' not in response:
        logging.error(PHRASES.get('no_key'))
        send_message(PHRASES.get('no_key'))
        raise TypeError(PHRASES.get('no_key'))
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logging.error(f'{homeworks} {PHRASES.get("not_list")}')
        send_message(f'{homeworks} {PHRASES.get("not_list")}')
        raise TypeError(f'{homeworks} {PHRASES.get("not_list")}')
    logging.debug('Ответ API соответствует критериям')
    return True


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if not homework_name or not status:
        logging.error(PHRASES.get('no_hw_status'))
        send_message(PHRASES.get('no_hw_status'))
        raise ValueError(PHRASES.get('no_hw_status'))
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        logging.error(f'{PHRASES.get("unknown_hw_status")}: {status}')
        send_message(f'{PHRASES.get("unknown_hw_status")}: {status}')
        raise ValueError(f'{PHRASES.get("unknown_hw_status")}: {status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                homeworks = response.get('homeworks')
                if homeworks:
                    for homework in homeworks:
                        message = parse_status(homework)
                        if message:
                            send_message(bot, message)
            timestamp = response.get('current_date', timestamp)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
