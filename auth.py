import os
import dash_auth


auth = dash_auth.DashAuth(
    log_files_dir='/home/iagos/atmo-access/atmo-access-footprint/log',
    keycloak_client_id='atmo-access-iagos',
    server_metadata_url='https://sso.aeris-data.fr/auth/realms/aeris/.well-known/openid-configuration',
    secret_key=os.environ['ATMO_ACCESS_SECRET_KEY'],
    auth_mounting_url='/atmo-access-auth/',
)
