import json


def jsonedit(path):
    with open(path) as f:
        data = json.load(f)
    for item in data['layouts']:
        for keywords in item['words']:
            keywords['text'] = keywords['text'].replace("'", "''")
            # print(keywords['text'])
    # try:
    #     for cellvalues in item['cells']:
    #         for value in cellvalues['words']:
    #             value['text'] = value['text'].replace("'", "''")
    #             print(value['text'])
    # finally:
    with open('aa.json', 'w') as f:
        json.dump(data, f)
