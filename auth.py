import dash_auth
import config


auth = dash_auth.DashAuth(
    log_files_dir=config.APP_LOG_DIR,
    server_metadata_url=config.AUTH_SERVER_METADATA_URL,
    flask_config=config.FLASK_CONFIG,
    auth_mounting_url=config.APP_AUTH_MOUNTING_URL,
)
