import functools
import secrets
import pathlib
import logging
import pandas as pd
from flask import Flask, redirect, url_for, session, abort
from authlib.integrations.flask_client import OAuth
import diskcache
from dash import Input, Output, html, dcc, no_update


DASH_AUTH_EXPIRE = 1200
AUTH_INTERVAL_ID = 'auth-interval-id'
AUTH_INTERVAL_IN_SEC = 900
_SESSION_ID = 'atmo-access-session_id'
_USER_EMAIL = 'atmo-access-user-email'
LOCATION_ID = 'location-component'


interval = dcc.Interval(
    id=AUTH_INTERVAL_ID,
    interval=AUTH_INTERVAL_IN_SEC * 1e3,
    # persistence=True,
    # persistence_type='session',
)


def with_auth(callback_decorator, auth):
    def callback_with_auth_decorator(*args, **kwargs):
        location_id = f'{LOCATION_ID}-{len(auth.locations) + 1}'
        auth.locations.append(dcc.Location(id=location_id))

        no_outputs = len([arg for arg in args if isinstance(arg, Output)])

        # set the extra error popup output as the last output;
        # this is important if a callback relies on the indices of the outputs,
        # cf. utils/graph_with_horizontal_selection_AIO.py/update_from_and_to_input_values (line ca. 107)
        new_args = args[:no_outputs] + (Output(location_id, 'href'), ) + args[no_outputs:]

        def callback_func_transform(callback_func):
            @functools.wraps(callback_func)
            def callback_func_with_auth(*callback_args):
                if auth.is_user_authentified():
                    callback_result = callback_func(*callback_args)
                    if no_outputs == 1:
                        callback_result = (callback_result, )
                    elif no_outputs == 0:
                        callback_result = ()
                    callback_with_auth_func_result = callback_result + (no_update, )
                else:
                    outputs = (no_update, ) * no_outputs
                    callback_with_auth_func_result = outputs + (auth.get_login_url(), )
                if no_outputs == 0:
                    callback_with_auth_func_result, = callback_with_auth_func_result
                return callback_with_auth_func_result

            return callback_decorator(*new_args, **kwargs)(callback_func_with_auth)

        return callback_func_transform
    return callback_with_auth_decorator


class DashAuth:
    def __init__(
            self,
            log_files_dir,
            keycloak_client_id='atmo-access-iagos',
            server_metadata_url='https://sso.aeris-data.fr/auth/realms/aeris/.well-known/openid-configuration',
            secret_key=None,
    ):
        self.locations = []
        self.flask_app = Flask(__name__)
        self.flask_app.config['SECRET_KEY'] = secret_key if secret_key is not None else secrets.token_urlsafe(32)
        self.flask_app.config['KEYCLOAK_CLIENT_ID'] = keycloak_client_id

        self.oauth = OAuth(app=self.flask_app)
        self.keycloak = self.oauth.register(
            name='keycloak',
            server_metadata_url=server_metadata_url,
            client_kwargs={
                'scope': 'openid email profile',
                'token_endpoint_auth_method': 'client_secret_basic',
                'token_placement': 'header',
                'code_challenge_method': 'S256'  # enable PKCE
            },
        )

        active_sessions_filename = pathlib.PurePath(log_files_dir) / 'active_sessions'
        self.active_sessions = diskcache.Cache(active_sessions_filename)

        user_login_time_filename = pathlib.PurePath(log_files_dir) / 'user_login_time'
        self.user_login_time = diskcache.Cache(user_login_time_filename)

        self.auth_callbacks_installed = False
        self.install_auth_callbacks()

    def _authorize(self):
        token = self.oauth.keycloak.authorize_access_token()
        user_info = token.get('userinfo')
        if user_info is not None:
            user_email = user_info.get('email')
        else:
            user_email = None
        session_id = secrets.token_urlsafe(32)
        timenow = pd.Timestamp.now()

        self.active_sessions.set(session_id, None, expire=DASH_AUTH_EXPIRE, retry=True)
        self.user_login_time.set(session_id, (timenow, user_email), retry=True)

        session[_SESSION_ID] = session_id
        print(list(token))
        print('!!!token =', token)
        print('!!!session =', dict(session))

    def install_auth_callbacks(self):
        if self.auth_callbacks_installed:
            return

        @self.flask_app.route('/login')
        def login():
            print('login...')
            try:
                session.clear()
                res = self.oauth.keycloak.authorize_redirect(redirect_uri=url_for('authorize', _external=True))
                print('login...done')
                return res
            except Exception as e:
                logging.exception('login failed', exc_info=e)
                print('login...failed')
                abort(403, description='Authentication failed')

        @self.flask_app.route('/authorize')
        def authorize():
            print('authorize...')
            try:
                self._authorize()
                # Save the token or user information if needed
                # return redirect(url_for('index'))
                res = redirect(url_for('/'))
                print('authorize...done')
                return res
            except Exception as e:
                print('ko !!!')
                logging.exception('authorize failed', exc_info=e)
                abort(403, description='Authentication failed')

        print('install_auth_callbacks done', flush=True)

    def get_login_url(self):
        return url_for('login')

    def is_user_authentified(self):
        try:
            session_id = session.get(_SESSION_ID)
            # print(f'session_id={session_id}', flush=True)
            return session_id is not None and self.active_sessions.touch(session_id, expire=DASH_AUTH_EXPIRE)
        except Exception as e:
            logging.exception('checking user authentication failed', exc_info=e)
            return False

    def get_callback_with_auth_decorator(self):
        return lambda callback_decorator: with_auth(callback_decorator, self)

    def finalize_dash_app(self, dash_app):
        callback_with_auth = self.get_callback_with_auth_decorator()(dash_app.callback)
        @callback_with_auth(
            Input(AUTH_INTERVAL_ID, 'n_intervals')
        )
        def refresh_auth(_):
            print(f'refresh_auth callback: {_}', flush=True)

        dash_app_layout = dash_app.layout
        if not isinstance(dash_app_layout, (list, tuple)):
            dash_app_layout = [dash_app_layout]
        dash_app_layout = list(dash_app_layout)
        dash_app_layout.extend(self.locations)
        dash_app_layout.append(interval)
        dash_app.layout = html.Div(
            id='_dash_auth_app_container',
            children=dash_app_layout
        )
