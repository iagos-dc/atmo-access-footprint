import pandas as pd
import xarray as xr

from footprint_utils import helper
from footprint_data_access.data_access import _COprofile_ds, DATA_PATH


if __name__ == '__main__':
    _COprofile_ds = _COprofile_ds.assign_coords({'height': helper.hasl_by_pressure(_COprofile_ds.air_press_AC)})
    _CO_da = _COprofile_ds.COprofile_mean.load()
    CO_da = _CO_da.stack({'profile_idx': ('flight_id', 'profile')}, create_index=False)
    CO_da = CO_da.where(CO_da['time'].notnull(), drop=True)

    CO_da = CO_da.assign_coords({'month': CO_da['time'].dt.month, 'year': CO_da['time'].dt.year})
    code_ym = CO_da['code'] + '_' + \
              CO_da['year'].astype(str) + '-' + \
              CO_da['month'].astype(str).str.pad(2, side='left', fillchar='0')
    CO_da = CO_da.assign_coords({'code_ym': code_ym})

    CO_by_code_ym = CO_da.groupby('code_ym')
    _CO_stat_by_code_ym = xr.Dataset({'CO_mean': CO_by_code_ym.mean(), 'CO_var': CO_by_code_ym.var(ddof=1)})

    CO_stat_by_code_ym = _CO_stat_by_code_ym.assign_coords({
        'code': _CO_stat_by_code_ym.code_ym.str.slice(0, -8),
        'ym': _CO_stat_by_code_ym.code_ym.str.slice(-7, None).astype('M8[s]')
    })
    CO_stat_by_code_ym = CO_stat_by_code_ym.assign_coords({'year': CO_stat_by_code_ym['ym'].dt.year})
    code_year = CO_stat_by_code_ym['code'] + '_' + CO_stat_by_code_ym['year'].astype(str)
    CO_stat_by_code_ym = CO_stat_by_code_ym.assign_coords({'code_year': code_year})

    CO_by_code_year = CO_stat_by_code_ym.groupby('code_year')
    _mean = CO_by_code_year.mean()
    _var = CO_by_code_year.var(ddof=1)
    _CO_stat_by_code_year = xr.Dataset({'CO_mean': _mean['CO_mean'], 'CO_var': _mean['CO_var'] + _var['CO_mean']})
    CO_stat_by_code_year = _CO_stat_by_code_year.assign_coords({
        'code': _CO_stat_by_code_year['code_year'].str.slice(0, -5),
        'year': _CO_stat_by_code_year['code_year'].str.slice(-4, None).astype('M8[s]')
    })

    code_year_idx = pd.MultiIndex.from_arrays(
        [CO_stat_by_code_year['code'].values, CO_stat_by_code_year['year'].values],
        names=['code', 'year']
    )
    CO_stat_by_code_and_year = CO_stat_by_code_year\
        .assign_coords({'code_year': code_year_idx})\
        .unstack('code_year')\
        .sortby('year')\
        .transpose('code', 'year', 'air_press_AC')

    CO_stat_by_code_and_year.to_netcdf(DATA_PATH / 'COprofile_climat_data.nc', engine='h5netcdf')
    print('Done!')
