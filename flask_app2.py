import sys
import functools
import secrets
import pkg_resources
from flask import Flask, redirect, url_for, session, abort, jsonify, request
from authlib.integrations.flask_client import OAuth
import pandas as pd
import diskcache
from log import logger


_SESSION_ID = 'atmo-access-session_id'

active_sessions_filename = pkg_resources.resource_filename('log', 'time_by_session')
active_sessions = diskcache.Cache(active_sessions_filename)

user_last_login_filename = pkg_resources.resource_filename('log', 'user_last_login')
#user_last_login = diskcache.Cache(user_last_login_filename)

user_activity_filename = pkg_resources.resource_filename('log', 'user_activity')
#user_activity = diskcache.Cache(user_activity_filename)



flask_app = Flask(__name__)
flask_app.config['SECRET_KEY'] = 'this is my secret' #secrets.token_urlsafe(32)
flask_app.config['KEYCLOAK_CLIENT_ID'] = 'atmo-access-iagos'


oauth = OAuth(app=flask_app)
# keycloak = oauth.register('keycloak', overwrite=True)

oauth.register(
    name='keycloak',
    server_metadata_url='https://sso.aeris-data.fr/auth/realms/aeris/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'token_endpoint_auth_method': 'client_secret_basic',
        'token_placement': 'header',
        'code_challenge_method': 'S256'  # enable PKCE
    },
)


@flask_app.errorhandler(403)
def accesss_forbiden(e):
    return jsonify(error=str(e)), 403


# Routes
@flask_app.route('/')
def index():
    return redirect(url_for('login'))
    # session_id = session.get(_SESSION_ID)
    # print('session_id =', session_id)
    # if session_id:
    #     return redirect(url_for('/dashboard/'))
    # else:
    #     return redirect(url_for('login'))


@flask_app.route('/login')
def login():
    print('login...')
    try:
        session.clear()
        res = oauth.keycloak.authorize_redirect(redirect_uri=url_for('authorize', _external=True))
        print('login...done')
        return res
    except Exception as e:
        logger().exception('login failed', exc_info=e)
        print('login...failed')
        abort(403, description='Authentification failed')


def _inspect_authorize_request():
    if request.method == 'GET':
        error = request.args.get('error')
        if error:
            description = request.args.get('error_description')
            raise Exception(f'Oauth problem !!!: error={error}, description={description}')

        params = {
            'code': request.args['code'],
            'state': request.args.get('state'),
        }
    else:
        params = {
            'code': request.form['code'],
            'state': request.form.get('state'),
        }
    print('params =', params)


def _authorize():
    # _inspect_authorize_request()
    token = oauth.keycloak.authorize_access_token()
    session_id = secrets.token_urlsafe(32)
    timenow = pd.Timestamp.now()

    active_sessions.set(session_id, timenow, expire=15, retry=True)

    # store userinfo by timenow ?
    # while str(timenow) in userinfo_by_time:
    #     timenow += pd.Timedelta(1, 'us')
    # userinfo_by_time[str(timenow)] = token['userinfo']

    print(list(token))
    session[_SESSION_ID] = session_id
    print('!!!token =', token)
    print('!!!session =', dict(session))


@flask_app.route('/authorize')
def authorize():
    print('authorize...')
    try:
        _authorize()
        # Save the token or user information if needed
        # return redirect(url_for('index'))
        res = redirect(url_for('/dashboard/'))
        print('authorize...done')
        return res
    except Exception as e:
        print('ko !!!')
        logger().exception('authorize failed', exc_info=e)
        abort(403, description='Authentification failed')


def _protect_route(f):
    @functools.wraps(f)
    def new_f(*args, **kwargs):
        session_id = session.get(_SESSION_ID)
        # print(f'_protect_route::got session_id={session_id}')
        if session_id is not None:
            is_session_active = active_sessions.get(session_id, default=False, retry=True)
        else:
            is_session_active = False
        if is_session_active:
            return f(*args, **kwargs)
        else:
            #return redirect(url_for('login'))
            #print('_protect_route::not OK for session_id =', session_id)
            # abort(403, description='Access forbidden')
            try:
                print('try authorize...')
                oauth.keycloak.authorize_redirect(redirect_uri=url_for('authorize', _external=True))
                _authorize()
                print('try authorize...ok')
                return f(*args, **kwargs)
                # return redirect(url_for('authorize'))
            except Exception as e:
                try:
                    print('authorize failed; fallback to login...')
                    logger().exception('authorize failed; fallback to login', exc_info=e)
                    return redirect(url_for('login'))
                except Exception as e2:
                    print('login failed; panic')
                    logger().exception('login failed; panic', exc_info=e)
                    raise
    return new_f


def protect_dash_app(dash_app):
    for key, view_func in list(dash_app.server.view_functions.items()):
        if key.startswith('/dashboard/'):
            print(key)
            dash_app.server.view_functions[key] = _protect_route(view_func)
