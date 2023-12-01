import warnings
from pathlib import Path
import pandas as pd
import diskcache
import config


if __name__ == '__main__':
    requests_deque_path = Path(config.APP_REQUESTS_LOG)
    if requests_deque_path.exists():
        req = diskcache.Deque(directory=config.APP_REQUESTS_LOG)

        req = list(filter(lambda x: isinstance(x, dict), req))
        df = pd.DataFrame.from_records(req)

        print(df)
        print(df.iloc[-1])
        print(df['user_email'].value_counts())
    else:
        warnings.warn(f'{str(requests_deque_path)} does not exist')
