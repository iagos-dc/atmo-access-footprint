import functools
import pathlib
import numpy as np
import pandas as pd
import xarray as xr

from footprint_utils import helper
from log import log_exectime, logger
from config import APP_DATA_DIR


DATA_PATH = pathlib.Path(APP_DATA_DIR)

_fp_da = None

CO_data_url = DATA_PATH / 'CO_data.nc'
COprofile_data_url = DATA_PATH / 'COprofile_data.nc'
COprofile_climat_data_url = DATA_PATH / 'COprofile_climat_data.nc'
footprint_data_url = DATA_PATH / 'footprint_by_flight_id.zarr'


_COprofile_ds = xr.open_dataset(COprofile_data_url, engine='h5netcdf')
_COprofile_ds = _COprofile_ds.assign_coords({'height': helper.hasl_by_pressure(_COprofile_ds.air_press_AC)})


def _valid_airport_code(code):
    """
    Checks validity of airport codes.
    :param code: DataArray
    :return: boolean DataArray
    """
    code = code.reset_coords(drop=True)
    code = code.astype(str)  # nan -> 'nan'
    valid_code = (code != 'XXX') & (code != 'nan') & (code.str.len() == 3)
    return valid_code


@functools.lru_cache
@log_exectime
# TODO: _get_CO_data is called twice (first time due to imports, which is useless)
def _get_CO_data():
    _CO_ds = xr.load_dataset(CO_data_url, engine='h5netcdf')
    _CO_ds = _CO_ds.stack({'profile_idx': ('flight_id', 'profile')}, create_index=False)
    CO_filter = (_CO_ds['CO_count'] > 0).any('layer') & _valid_airport_code(_CO_ds['code'])
    _CO_ds = _CO_ds.sel({'profile_idx': CO_filter})
    _CO_ds = _CO_ds.assign_coords({'profile_idx': _CO_ds['profile_idx']})
    logger().info(f'_CO_ds.nbytes = {_CO_ds.nbytes / 1e6}M')
    return _CO_ds


@functools.cache
def _get_airports_data():
    return _get_CO_data().reset_coords()[['code', 'city', 'state', 'lon', 'lat', 'elevation', 'time']]


def apply_time_filter(ds, date_from=None, date_to=None):
    conds = []
    if date_from:
        cond = ds['time'] >= pd.to_datetime(date_from)
        conds.append(cond)
    if date_to:
        cond = ds['time'] <= pd.to_datetime(date_to)
        conds.append(cond)
    if len(conds) == 2:
        cond = conds[0] & conds[1]
    elif len(conds) == 1:
        cond, = conds
    else:
        cond = None
    if cond is not None:
        ds = ds.where(cond, drop=True)
    return ds


@functools.lru_cache(maxsize=32)
def get_iagos_airports(date_from=None, date_to=None, top=None):
    ds = _get_airports_data()
    ds = apply_time_filter(ds, date_from=date_from, date_to=date_to)
    if ds['code'].size == 0:
        airport_ds = ds
        airport_ds['nprofiles'] = pd.Series([], dtype=int)
    else:
        airport_ds = ds.groupby('code').first()
        ds = ds.assign({'nprofiles': ds['profile_idx']})
        airport_ds['nprofiles'] = ds[['nprofiles', 'code']].groupby('code').count()['nprofiles']

    _iagos_airports = airport_ds.to_dataframe().reset_index().rename(columns={
        'code': 'short_name',
        'city': 'long_name',
        'lon': 'longitude',
        'lat': 'latitude',
        'elevation': 'altitude',
    })

    if date_from is not None or date_to is not None:
        mask = airports_df['short_name'].isin(_iagos_airports['short_name'])
    else:
        mask = None

    if top is not None and len(_iagos_airports) > 0:
        return _iagos_airports.nlargest(top, 'nprofiles'), mask
    else:
        return _iagos_airports, mask


@functools.lru_cache(maxsize=8)
def get_residence_time(flight_id, profile, layer):
    global _fp_da
    if _fp_da is None:
        _ds = xr.open_zarr(footprint_data_url)
        _fp_da = _ds['res_time_per_km2']
    try:
        da = _fp_da.sel({'flight_id': flight_id, 'profile': profile, 'layer': layer}, drop=True)
    except KeyError:
        da = None
    return da


@functools.lru_cache(maxsize=256)
def get_COprofile(flight_id, profile):
    try:
        profile_ds = _COprofile_ds.sel({'flight_id': flight_id, 'profile': profile}).load()
    except KeyError:
        profile_ds = None
    return profile_ds


@functools.lru_cache
@log_exectime
def get_COprofile_climatology():
    # print('get_COprofile_climatology()...')
    _COprofile_climat_ds = xr.load_dataset(COprofile_climat_data_url, engine='h5netcdf')
    _clim_5y_mean_ds = _COprofile_climat_ds.rolling({'year': 5}, min_periods=1, center=True).mean()
    _clim_5y_var_ds = _COprofile_climat_ds.rolling({'year': 5}, min_periods=1, center=True).var()
    # print('get_COprofile_climatology()...done')
    return xr.Dataset({
        'CO_mean_5y': _clim_5y_mean_ds['CO_mean'],
        'CO_std_5y': np.sqrt(_clim_5y_mean_ds['CO_var'] + _clim_5y_var_ds['CO_mean'])
    })


def get_coords_by_airport_and_profile_idx(aiport_code, profile_idx):
    return _coords_by_airport[aiport_code][profile_idx]


@functools.lru_cache(maxsize=256)
def get_flight_id_and_profile_by_airport_and_profile_idx(aiport_code, profile_idx):
    coords = get_coords_by_airport_and_profile_idx(aiport_code, profile_idx)
    return coords['flight_id'].item(), coords['profile'].item()


@functools.lru_cache(maxsize=32)
@log_exectime
def get_CO_ts(airport_code, date_from=None, date_to=None):
    coords = _coords_by_airport[airport_code]
    CO_ts = _get_CO_data().sel({'profile_idx': coords['profile_idx']})
    CO_ts = apply_time_filter(CO_ts, date_from=date_from, date_to=date_to)
    logger().info(f'airport_code={airport_code}, CO_ts.nbytes = {CO_ts.nbytes / 1e6}M')
    return CO_ts


_coords_by_airport = {}
nprofiles_by_airport = {}
for airport, coords_for_airport in _get_CO_data()['profile_idx'].groupby('code'):
    _coords_by_airport[airport] = coords_for_airport.sortby('time')
    nprofiles_by_airport[airport] = len(_coords_by_airport[airport]['profile_idx'])

airports_df, _ = get_iagos_airports(top=None)
airports_df = airports_df.sort_values('long_name')
airport_name_by_code = dict(zip(airports_df['short_name'], airports_df['long_name']))
