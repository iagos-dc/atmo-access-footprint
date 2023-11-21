import pkg_resources
import dash_auth


auth = dash_auth.DashAuth(
    log_files_dir=pkg_resources.resource_filename('log', ''),
    keycloak_client_id='atmo-access-iagos',
    server_metadata_url='https://sso.aeris-data.fr/auth/realms/aeris/.well-known/openid-configuration',
    secret_key=None,
)
