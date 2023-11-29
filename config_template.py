# Do not commit production version of such file to git!

import logging


FLASK_CONFIG = {
    'KEYCLOAK_CLIENT_ID': 'my-keycloak-client-id',
    'SECRET_KEY': 'my secret key',
    'SESSION_COOKIE_NAME': 'my-session-cookie-name',
}

APP_PATHNAME_PREFIX = '/atmo-access/footprint/'

AUTH_SERVER_METADATA_URL = 'https://sso.example.com/auth/realms/my-realm/.well-known/openid-configuration'

APP_AUTH_MOUNTING_URL = '/atmo-access-auth/'

APP_LOG_DIR = '/home/user/my-app/log'

APP_LOGS = f'{APP_LOG_DIR}/log.txt'
APP_REQUESTS_LOG = f'{APP_LOG_DIR}/requests.log'

APP_DATA_DIR = '/home/user/my-app/data'

_LOGGING_LEVEL = logging.INFO

logging.basicConfig(format='%(asctime)s - aaft - %(message)s', level=_LOGGING_LEVEL)
