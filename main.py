import os
import json
import requests
from flask import Flask, request


app = Flask(__name__)

sessionStorage = {}


def translate(word, lang='ru-en'):
    url = "https://translated-mymemory---translation-memory.p.rapidapi.com" \
          "/api/get"

    params = {"langpair": lang.replace('-', '|'), "q": word}

    headers = {
        'x-rapidapi-key': "d6b1c4e027msh3cdb97b26f23be3p1ceef0jsn8a4e9faf80b5",
        'x-rapidapi-host': "translated-mymemory---translation-memory.p.rapidapi.com"
    }

    response = requests.request("GET", url, headers=headers, params=params)
    return response.json()["responseData"]["translatedText"].replace('&#39;',
                                                                     '`')


@app.route('/post', methods=['POST'])
def main():
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False,
            'buttons': [{'title': 'Помощь', 'hide': True}]
        }
    }

    handle_dialog(response, request.json)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']

    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        sessionStorage[user_id] = {}
        return

    if sessionStorage[user_id].get('first_name') is None:
        name = get_first_name(req)
        if name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'
            return

        sessionStorage[user_id]['first_name'] = name
        res['response']['text'] = f'Приятно познакомиться, {name.title()}. ' \
                                  'Я Алиса. Я умею переводить слова (фразы)' \
                                  ' с русского языка на английский.'
        return

    if req['request']['original_utterance'].lower() in ['помощь', 'помоги',
                                                        'help', 'помогите']:
        res['response']['text'] = 'Чтобы перевести текст введите ' \
                                  '"Переведи слово <слово>"'
        return

    tokens = req['request']['nlu']['tokens']
    if len(tokens) >= 3 and tokens[:2] == ['переведи', 'слово']:
        res['response']['text'] = translate(' '.join(tokens[2:]))

    else:
        res['response']['text'] = 'Чтобы перевести текст введите ' \
                                  '"Переведи слово <слово>"'


def get_first_name(req):
    for entity in req['request']['nlu']['entities']:
        if entity['type'] == 'YANDEX.FIO':
            return entity['value'].get('first_name', None)


if __name__ == '__main__':
    port = os.environ.get('PORT', 5000)
    app.run(host='0.0.0.0', port=port)
