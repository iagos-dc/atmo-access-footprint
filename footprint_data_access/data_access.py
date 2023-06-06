import functools
import importlib.resources
import pathlib
import pandas as pd
import xarray as xr


_iagos_airports = None
_fp_ds = None
_CO_ds = None

CO_data_url = pathlib.Path('/home/wolp/data/fp_agg/CO_data.nc')
COprofile_data_url = pathlib.Path('/home/wolp/data/fp_agg/COprofile_data.nc')
footprint_data_url = pathlib.Path('/home/wolp/data/fp_agg/footprint_by_flight_id_2018.zarr/')


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


def _get_CO_data():
    global _CO_ds
    if _CO_ds is None:
        # _CO_ds = xr.load_dataset(CO_data_url, engine='h5netcdf')  # TODO: uncomment
        _CO_ds = xr.open_dataset(CO_data_url, engine='h5netcdf')  # TODO: to be removed
        _CO_ds = _CO_ds.sel({'flight_id': slice('2018', '2019')}).load()  # TODO: to be removed
        _CO_ds = _CO_ds.stack({'profile_idx': ('flight_id', 'profile')}, create_index=False)
        CO_filter = (_CO_ds['CO_count'] > 0).any('layer') & _valid_airport_code(_CO_ds['code'])
        _CO_ds = _CO_ds.sel({'profile_idx': CO_filter})
        _CO_ds = _CO_ds.assign_coords({'profile_idx': _CO_ds['profile_idx']})
    return _CO_ds


def get_iagos_airports_old(top=None):
    global _iagos_airports
    if _iagos_airports is None:
        ref = importlib.resources.files('footprint_data_access') / 'resources/iagos_airports.json'
        with importlib.resources.as_file(ref) as url:
            _iagos_airports = pd.read_json(url, orient='records')
    if top is not None:
        return _iagos_airports.nlargest(top, 'nprofiles')
    else:
        return _iagos_airports


def get_iagos_airports(top=None):
    global _iagos_airports
    if _iagos_airports is None:
        ds = _get_CO_data().reset_coords()[['code', 'city', 'state', 'lon', 'lat', 'elevation']]
        airport_ds = ds.groupby('code').first()
        ds = ds.assign({'nprofiles': ds['profile_idx']})
        airport_ds['nprofiles'] = ds[['nprofiles', 'code']].groupby('code').count()['nprofiles']
        _iagos_airports = airport_ds.to_pandas().reset_index().rename(columns={
            'code': 'short_name',
            'city': 'long_name',
            'lon': 'longitude',
            'lat': 'latitude',
            'elevation': 'altitude',
        })
    if top is not None:
        return _iagos_airports.nlargest(top, 'nprofiles')
    else:
        return _iagos_airports


@functools.lru_cache(maxsize=128)
def get_residence_time(flight_id, profile):
    global _fp_ds
    if _fp_ds is None:
        _fp_ds = xr.open_zarr(footprint_data_url)
    try:
        da = _fp_ds.sel({'flight_id': flight_id, 'profile': profile})['res_time_per_km2']
    except KeyError:
        da = None
    return da


@functools.lru_cache(maxsize=128)
def get_flight_id_and_profile_by_airport_and_profile_idx(aiport_code, profile_idx):
    coords = _coords_by_airport[aiport_code][profile_idx]
    return coords['flight_id'].item(), coords['profile'].item()
    # pd.Timestamp(coords['time'].item())


# @functools.lru_cache(maxsize=32)
def get_CO_ts(airport_code):
    coords = _coords_by_airport[airport_code]
    return _get_CO_data().sel({'profile_idx': coords['profile_idx']})


_coords_by_airport = {}
nprofiles_by_airport = {}
for airport, coords_for_airport in _get_CO_data()['profile_idx'].groupby('code'):
    _coords_by_airport[airport] = coords_for_airport.sortby('time')
    nprofiles_by_airport[airport] = len(_coords_by_airport[airport]['profile_idx'])
