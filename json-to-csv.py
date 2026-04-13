
import json

import pandas as pd


def convert():
    with open('classified-data.json') as f:
        test_data = json.load(f)

    test_data = [i for i in test_data if i['expected_code']
                 != '' and i['description'] != 'success.']

    test_data = [
        {
            'description': i['description'].split('. Product:', 1)[0],
            'expected_code': i['expected_code']
        } for i in test_data
    ]
    df = pd.DataFrame(test_data)

    with open('./classified-data.csv', 'w') as f:
        df.to_csv(f)


convert()
