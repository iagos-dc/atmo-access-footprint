import os

os.environ['DASH_REQUESTS_PATHNAME_PREFIX'] = '/atmo-access/footprint/'

from app import server

if __name__ == "__main__":
    server.run()
