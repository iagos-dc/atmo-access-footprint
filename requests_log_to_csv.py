import diskcache
import pandas as pd

from config import APP_REQUESTS_LOG


if __name__ == '__main__':
    req = diskcache.Cache(APP_REQUESTS_LOG)
    req_dict = {k: req[k] for k in req.iterkeys()}
    df = pd.DataFrame.from_dict(req_dict, orient='index')
    print(df.to_csv())
