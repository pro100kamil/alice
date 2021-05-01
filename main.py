import json
import logging
import math
import os
import random

import requests
from flask import Flask, request


def get_distance(p1: tuple, p2: tuple) -> float:
    radius = 6373.0

    lon1 = math.radians(p1[0])
    lat1 = math.radians(p1[1])
    lon2 = math.radians(p2[0])
    lat2 = math.radians(p2[1])

    d_lon = lon2 - lon1
    d_lat = lat2 - lat1

    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        d_lon / 2) ** 2
    c = 2 * math.atan2(a ** 0.5, (1 - a) ** 0.5)

    distance = radius * c
    return distance


def get_geo_info(city_name: str, type_info='coordinates'):
    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": "40d1649f-0493-4b70-98ba-98533de7710b",
            'geocode': city_name,
            'format': 'json'
        }
        data = requests.get(url, params).json()
        if type_info == 'country':
            return data['response']['GeoObjectCollection'][
                'featureMember'][0]['GeoObject']['metaDataProperty'][
                'GeocoderMetaData']['AddressDetails']['Country']['CountryName']

        elif type_info == 'coordinates':
            coordinates_str = data['response']['GeoObjectCollection'][
                'featureMember'][0]['GeoObject']['Point']['pos']

            long, lat = map(float, coordinates_str.split())
            return long, lat

    except Exception as e:
        return e


app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# словарь, в котором ключ — название города, значение — массив,
# где перечислены id картинок

cities = {
    'москва': ['1533899/18559580d4638e41d11e',
               '213044/ea69292c034fb402a07c'],
    'нью-йорк': ['213044/b0f8a34d1319ce6606cc',
                 '1540737/9e8c913a4dc04f1256ea'],
    'париж': ['1652229/e7bbda7139db7f1f1b58',
              '1030494/2e868345245de92042d7']
}

sessionStorage = {}
STANDART_BTNS = [
    {
        'title': 'Да',
        'hide': True
    },
    {
        'title': 'Нет',
        'hide': True
    }, {
        'title': 'Помощь',
        'hide': True
    }
]


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)

    response = {  # В самом начале добавляем кнопку о помощи
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False,
            'buttons': [{
                'title': 'Помощь',
                'hide': True
            }]
        }

    }

    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']

    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        sessionStorage[user_id] = {
            'first_name': None,
            'game_started': False,
            'last_btns': [{
                'title': 'Помощь',
                'hide': True
            }]
        }
        return

    if req['request']['original_utterance'].lower() in ['помощь', 'помоги',
                                                        'help', 'помогите']:
        res['response'][
            'text'] = 'Активировалась помощь! Не знаю, что здесь написать :D\n' \
                      'Продолжайте отвечать на заданный ранее вопрос!!!'
        res['response']['buttons'] = sessionStorage[user_id].get('last_btns',
                                                                 [])[:]
        return

    if sessionStorage[user_id]['first_name'] is None:
        first_name = get_first_name(req)
        if first_name is None:
            res['response']['text'] = 'Не расслышала имя. ' \
                                      'Повтори, пожалуйста!'
        else:
            sessionStorage[user_id]['first_name'] = first_name
            sessionStorage[user_id]['guessed_cities'] = []

            res['response'][
                'text'] = f'Приятно познакомиться, {first_name.title()}. ' \
                          f'Я Алиса. Отгадаешь город по фото?'
            res['response']['buttons'] = STANDART_BTNS
    else:
        name = sessionStorage[user_id]['first_name'].title()
        if not sessionStorage[user_id]['game_started']:
            # игра не начата, значит мы ожидаем ответ на предложение сыграть.
            if 'да' in req['request']['nlu']['tokens']:
                if len(sessionStorage[user_id]['guessed_cities']) == 3:
                    # если все три города отгаданы, то заканчиваем игру
                    res['response']['text'] = f'Ты отгадал все города, {name}!'
                    res['response']['end_session'] = True
                else:
                    # если есть неотгаданные города, то продолжаем игру
                    sessionStorage[user_id]['game_started'] = True
                    # номер попытки, чтобы показывать фото по порядку
                    sessionStorage[user_id]['attempt'] = 1
                    # функция,
                    # которая выбирает город для игры и показывает фото
                    play_game(res, req)

            elif 'нет' in req['request']['nlu']['tokens']:
                res['response']['text'] = f'Ну и ладно, {name}!'
                res['response']['end_session'] = True
            else:
                if req['request'][
                    'original_utterance'] == 'Покажи город на карте':
                    res['response'][
                        'text'] = f'{name}. Ну, показала! Сыграём ещё?'
                else:
                    res['response'][
                        'text'] = f'{name}, я не поняла ответа! ' \
                                  f'Так да или нет?'
                res['response']['buttons'] = STANDART_BTNS

        else:
            play_game(res, req)
    sessionStorage[user_id]['last_btns'] = res['response'].get(
        'buttons', [])[:]


def play_game(res, req):
    user_id = req['session']['user_id']
    attempt = sessionStorage[user_id]['attempt']
    name = sessionStorage[user_id]["first_name"].title()

    if attempt == 1:
        # если попытка первая, то случайным образом выбираем город для гадания
        city = random.choice(list(cities))
        while city in sessionStorage[user_id]['guessed_cities']:
            city = random.choice(list(cities))
        # записываем город в информацию о пользователе
        sessionStorage[user_id]['city'] = city
        sessionStorage[user_id]['country'] = get_geo_info(city,
                                                          type_info='country').lower()
        # добавляем в ответ картинку
        res['response']['card'] = {}
        res['response']['card']['type'] = 'BigImage'
        res['response']['card']['title'] = f'Что это за город, {name}?'
        res['response']['card']['image_id'] = cities[city][attempt - 1]
        res['response']['text'] = f'{name}, Тогда сыграем!'
    else:
        # сюда попадаем, если попытка отгадать не первая
        city = sessionStorage[user_id]['city']

        if city in sessionStorage[user_id]['guessed_cities']:
            if req['request']['original_utterance'].lower() == \
                    sessionStorage[user_id]['country']:
                res['response']['buttons'] = [*STANDART_BTNS,
                                              {
                                                  'title': 'Покажи город на карте',
                                                  'hide': True,
                                                  "url": f"https://yandex.ru/maps/"
                                                         f"?mode=search&text={city}"}]
                res['response']['text'] = f'Правильно! Сыграем ещё, {name}?'

                sessionStorage[user_id]['game_started'] = False
                return
            res['response'][
                'text'] = f'{name}, Вы не угадали страну города! ' \
                          f'Попробуйте ещё раз.'
            return

        # проверяем есть ли правильный ответ в сообщение
        if get_city(req) == city:
            res['response']['text'] = f'Верно, {name}! А теперь угадайте в ' \
                                      f'какой стране этот город?'
            sessionStorage[user_id]['guessed_cities'].append(city)
            return
        else:
            # если нет
            if attempt == 3:
                res['response'][
                    'text'] = f'{name}, Вы пытались. Это {city.title()}. Сыграем ещё?'
                sessionStorage[user_id]['game_started'] = False
                sessionStorage[user_id]['guessed_cities'].append(city)
                return
            else:
                # иначе показываем следующую картинку
                res['response']['card'] = {}
                res['response']['card']['type'] = 'BigImage'
                res['response']['card']['title'] = f'{name}, Неправильно. ' \
                                                   f'Вот тебе дополнительное фото'
                res['response']['card']['image_id'] = cities[city][attempt - 1]
                res['response']['text'] = f'{name}, Вы не угадали!'
    # увеличиваем номер попытки доля следующего шага
    sessionStorage[user_id]['attempt'] += 1


def get_city(req):
    # перебираем именованные сущности
    for entity in req['request']['nlu']['entities']:
        # если тип YANDEX.GEO,
        # то пытаемся получить город(city), иначе возвращаем None
        if entity['type'] == 'YANDEX.GEO':
            # возвращаем None, если не нашли сущности с типом YANDEX.GEO
            return entity['value'].get('city', None)


def get_first_name(req):
    # перебираем сущности
    for entity in req['request']['nlu']['entities']:
        # находим сущность с типом 'YANDEX.FIO'
        if entity['type'] == 'YANDEX.FIO':
            # Если есть сущность с ключом 'first_name',
            # иначе возвращаем None.
            return entity['value'].get('first_name', None)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
