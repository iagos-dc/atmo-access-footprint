import sys
import logging
import pathlib
import functools
import diskcache
import argparse
import requests
import pandas as pd
from authlib.integrations.requests_client import OAuth2Session

import config
import footprint_data_access


USERS_TO_IGNORE = [
    'pawel.wolff@aero.obs-mip.fr',
]


def timestamp_to_str(t):
    return t.strftime('%Y-%m-%dT%H:%M:%S%z')


# TODO: remove code duplication with callbacks.py
def _update_footprint_map_comment(
        airport_code, vertical_layer, current_profile_idx_by_airport,
        *args, **kwargs
):
    airport_name = footprint_data_access.airport_name_by_code[airport_code]
    profile_idx = current_profile_idx_by_airport.get(airport_code, 0)
    curr_time = footprint_data_access.get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
    return f'Footprint from {vertical_layer} layer over {airport_name} ({airport_code}) on {pd.Timestamp(curr_time).strftime("%Y-%m-%d %H:%M")}'


def get_request_json(req):
    user_email = req.get('user_email')
    req_time = req['time']
    comment = req.get('comment')
    if not comment:
        if req['name'] == 'update_footprint_map':
            comment = _update_footprint_map_comment(*req.get('args', []), **req.get('kwargs', {}))

    ignore = user_email in USERS_TO_IGNORE

    if not user_email:
        # user being None / 'null' is not accepted by the DB
        user_email = 'anonymous@unknown'

    req_json = {
        'user': user_email,
        'startDate': timestamp_to_str(req_time),
        'endDate': timestamp_to_str(req_time),
        'service': 'FOOTPRINT',
        'comment': f'[IAGOS] {comment}',
    }

    return req_json, ignore


@functools.cache
def get_auth_client():
    logging.debug('get_auth_client')
    return OAuth2Session(
        client_id=config.CLIENT_ID,
        client_secret=config.API_SECRET_KEY,
        scope='openid'
    )


_TOKEN_REDO_REQUEST = pd.Timedelta(180, 's')
_token = None
_token_time = None

def get_auth_token():
    global _token, _token_time
    time_now = pd.Timestamp.now(tz='UTC')
    if _token is None or time_now > _token_time + _TOKEN_REDO_REQUEST:
        client = get_auth_client()
        logging.debug('get_auth_token')
        _token = client.fetch_token(
            url=config.AUTH_TOKEN_ENDPOINT,
            username=config.USER_LOGIN,
            password=config.USER_PASSWORD
        )
        _token_time = time_now

    return _token


def do_post(url, body, token):
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    response = requests.post(url, headers=headers, json=body)
    return response


def push_request_to_db(req_json):
    logging.debug(f'push_request_to_db: {req_json}')
    token = get_auth_token()
    response = do_post(config.ADMIN_APPLICATION_URL, req_json, token)
    response.raise_for_status()
    app_id = response.text
    logging.debug(f'push_request_to_db got app_id={app_id}')
    return app_id


if __name__ == '__main__':
    logdir = pathlib.PurePath(config.APP_LOG_DIR)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--requests_deque',
        help=f'pathname of a deque with requests to process',
    )
    args = parser.parse_args()

    logging.basicConfig(
        filename=logdir / 'push_requests_to_db.log',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
        # level=logging.DEBUG
    )

    requests_archive_deque = diskcache.Deque(directory=logdir / 'requests_archive')
    requests_staging_deque = diskcache.Deque(directory=logdir / 'requests_staging')
    requests_staging_deque_directory = requests_staging_deque.directory
    lock_file = diskcache.Cache(directory=logdir / '.lock')

    if args.requests_deque is None:
        reqs = diskcache.Deque(directory=config.APP_REQUESTS_LOG)
    else:
        if not pathlib.Path(args.requests_deque).is_dir():
            raise NotADirectoryError(f'{args.requests_deque} does not exist')
        reqs = diskcache.Deque(directory=args.requests_deque)

    if len(reqs) == 0:
        logging.debug(f'No requests in {reqs.directory}, so nothing to do!')
        sys.exit(0)
    logging.info(f'Processing {len(reqs)} request(s) from {reqs.directory}')

    inserted_count, ignored_count, failed_count = 0, 0, 0
    while len(reqs) > 0:
        with lock_file.transact():
            # This is a slightly cumbersome way to ensure no other process is appending and popping items
            # from the Deque requests_staging_deque, which could cause problems.

            with requests_staging_deque.transact():
                req = reqs.peekleft()
                staging_index = len(requests_staging_deque)
                requests_staging_deque.append(req)
                reqs.popleft()
            try:
                req_json, ignore = get_request_json(req)
                if not ignore:
                    # push req_json to DB via API
                    req_id = push_request_to_db(req_json)
                    if not req_id:
                        raise RuntimeError(f'Inserting to the database failed silently with req_id={req_id}')
                else:
                    req_id = None

                req_to_archive = {
                    'id': req_id,
                    'json': req_json,
                    'request': req,
                }

                requests_archive_deque.append(req_to_archive)
                requests_staging_deque.pop()

                if req_id:
                    logging.debug(f'The request with id={req_id} successfully inserted into the database and stored in the local archive.')
                    inserted_count += 1
                else:
                    # logging.debug(f'The request {req_json} stored in the local archive only.')
                    ignored_count += 1
            except Exception as e:
                failed_count += 1
                logging.exception(f'Failed to post a request to the database; the request is saved into Deque {requests_staging_deque_directory} at index={staging_index}', exc_info=e)

    logging.info(f'{inserted_count} request(s) inserted into the database')
    if ignored_count > 0:
        logging.info(f'{ignored_count} request(s) ignored and stored in the local archive only')
    if failed_count > 0:
        logging.info(f'{failed_count} request(s) failed to be processed and only copied into Deque {requests_staging_deque.directory}')

    if len(requests_staging_deque) > 0:
        logging.warning(f'{len(requests_staging_deque)} request(s) are waiting in the staging Deque {requests_staging_deque_directory} for insertion into the database!')
        logging.warning(
            f'In order to try to insert them, please rename the directory {requests_staging_deque_directory} '
            f'to <new_dir_name> and re-run this script with the option "-d <new_dir_name>"'
        )
