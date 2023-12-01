import pandas as pd
from flask import request
import dash_auth
import config


auth = dash_auth.DashAuth(
    log_files_dir=config.APP_LOG_DIR,
    server_metadata_url=config.AUTH_SERVER_METADATA_URL,
    flask_config=config.FLASK_CONFIG,
    auth_mounting_url=config.APP_AUTH_MOUNTING_URL,
)


def get_request_metadata():
    return {
        'user_email': auth.get_user_email(),
        'time': pd.Timestamp.now(tz='UTC'),
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
        # 'ip_address': request.remote_addr,  # with gunicorn/ngnix it always gives 127.0.0.1
        # see: https://stackoverflow.com/questions/3759981/get-ip-address-of-visitors-using-flask-for-python
    }
