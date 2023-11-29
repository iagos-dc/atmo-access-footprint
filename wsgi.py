import os
import config

# see: https://community.plotly.com/t/deploy-dash-on-apache-server-solved/4855/18
os.environ['DASH_REQUESTS_PATHNAME_PREFIX'] = config.APP_PATHNAME_PREFIX
# os.environ['DASH_URL_BASE_PATHNAME'] = config.APP_PATHNAME_PREFIX

from app import server

if __name__ == "__main__":
    server.run()
