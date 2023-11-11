import pkg_resources
import dash_auth

LOG_FILES_DIR = pkg_resources.resource_filename('log', '.')


# TODO: get config from os.environ

auth = dash_auth.DashAuth(
    log_files_dir=LOG_FILES_DIR,
    keycloak_client_id='atmo-access-iagos',
    server_metadata_url='https://sso.aeris-data.fr/auth/realms/aeris/.well-known/openid-configuration',
    secret_key=None,
)

callback_with_auth_decorator = auth.get_callback_with_auth_decorator()
