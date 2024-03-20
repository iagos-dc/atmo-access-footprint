import warnings
from pathlib import Path
import pandas as pd
import diskcache
import config


if __name__ == '__main__':
    requests_deque_path = Path(config.APP_LOG_DIR) / 'requests_archive'
    if requests_deque_path.exists():
        req = diskcache.Deque(directory=requests_deque_path)
        _req = []
        for r in req:
            _r = {'id': r['id']}
            _r.update(r['json'])
            _r.update(r['request'])
            _req.append(_r)
        df = pd.DataFrame.from_records(_req)
        print(df)
        print()
        print(df.iloc[-1])
        print()
        print(df['user_email'].value_counts())
        print()
        df2 = df[df['id'].notna()]
        print(df2.groupby(df2.startDate.str.slice(0, 7))['id'].count())
    else:
        warnings.warn(f'{str(requests_deque_path)} does not exist')
