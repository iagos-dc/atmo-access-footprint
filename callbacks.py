import sys
import pathlib
import toolz
import functools
import numpy as np
import pandas as pd
import xarray as xr
import dash
from dash import Output, Input, State, Patch, callback
import plotly.graph_objects as go

import plotly.express as px

sys.path.append('/home/wolp/PycharmProjects/atmo-access-time-series2')
from utils import charts

from log import log_exception, logger, log_callback
from layout import AIRPORT_SELECT_ID, VERTICAL_LAYER_RADIO_ID, FOOTPRINT_MAP_GRAPH_ID, PREVIOUS_TIME_BUTTON_ID, \
    NEXT_TIME_BUTTON_ID, CURRENT_TIME_BY_AIRPORT_STORE_ID, \
    CO_GRAPH_ID, EMISSION_INVENTORY_CHECKLIST_ID,  EMISSION_REGION_SELECT_ID
from footprint_utils import footprint_viz, helper


footprint_data_dir = pathlib.Path('/home/wolp/data/fp_agg/CO_and_footprint_by_airport')


@functools.lru_cache(maxsize=128)
def get_footprint_img(airport_code, layer, time_idx):
    print(f'get_footprint_img({airport_code}, {layer}, {time_idx})')
    res_time_per_km2, CO_ts, idx_by_i = get_residtime_COts_idx_by_airport(airport_code)
    print(CO_ts['res_time_avail'].isel(i=time_idx).item())
    if CO_ts['res_time_avail'].isel(i=time_idx):
        da = res_time_per_km2.isel({'idx': idx_by_i[time_idx]}, drop=True).sel(layer=layer, drop=True).reset_coords(drop=True).load()
        print(da.sum().item())
        return footprint_viz.get_footprint_viz(da)
    else:
        return None


@functools.lru_cache(maxsize=None)
def get_residtime_COts_idx_by_airport(code):
    code = code.upper()
    url = footprint_data_dir / f'{code}.zarr'
    if not url.exists():
        raise FileNotFoundError(str(url))
    ds = xr.open_zarr(url)
    print(f'{url} opened')

    ds = ds.set_coords(['city', 'code', 'res_time_avail', 'state', 'time'])

    # sort idx so that time is non-decreasing
    perm = np.argsort(ds['time'].load().values)
    ds = ds.assign_coords({'idx_by_i': ('i', perm)})
    idx_by_i = ds['idx_by_i']
    CO_ts = ds.drop_vars('res_time_per_km2').isel({'idx': idx_by_i}).load()
    CO_ts['res_time_avail'] = CO_ts['res_time_avail'].astype('bool')

    # get the heavy variable apart, without sorting
    res_time_per_km2 = ds['res_time_per_km2']

    return res_time_per_km2, CO_ts, idx_by_i


@callback(
    Output(FOOTPRINT_MAP_GRAPH_ID, 'figure'),
    Output(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(PREVIOUS_TIME_BUTTON_ID, 'n_clicks'),
    Input(NEXT_TIME_BUTTON_ID, 'n_clicks'),
    Input(CO_GRAPH_ID, 'clickData'),
    State(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data'),
)
@log_exception
def update_footprint_map(airport_code, vertical_layer, previous_time_click, next_time_click, co_graph_click_data, curent_time_idx_by_airport):
    dash_ctx = list(dash.ctx.triggered_prop_ids.values())

    res_time_per_km2, CO_ts, idx_by_i = get_residtime_COts_idx_by_airport(airport_code)

    if co_graph_click_data is not None and CO_GRAPH_ID in dash_ctx:
        time_idx = co_graph_click_data['points'][0]['customdata']
    else:
        time_idx, _ = curent_time_idx_by_airport.get(airport_code, (0, np.datetime64('nat')))

    if PREVIOUS_TIME_BUTTON_ID in dash_ctx and time_idx > 0:
        time_idx -= 1
    if NEXT_TIME_BUTTON_ID in dash_ctx and time_idx < len(idx_by_i) - 1:
        time_idx += 1
    curr_time = pd.Timestamp(CO_ts['time'].isel({'i': time_idx}).item())
    curent_time_idx_by_airport[airport_code] = time_idx, curr_time

    mapbox_layer = get_footprint_img(airport_code, vertical_layer, time_idx)

    fig = Patch()
    fig['layout']['title'] = f'{airport_code} : {vertical_layer} : {curr_time.strftime("%Y-%m-%d %H:%M")} : [{time_idx}]'
    fig['layout']['mapbox']['layers'] = [mapbox_layer]
    return fig, curent_time_idx_by_airport


@callback(
    Output(CO_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(EMISSION_INVENTORY_CHECKLIST_ID, 'value'),
    Input(EMISSION_REGION_SELECT_ID, 'value'),
)
@log_exception
def update_CO_fig(airport_code, vertical_layer, emission_inventory, emission_region):
    emission_inventory = sorted(emission_inventory)

    _, CO_ts, _ = get_residtime_COts_idx_by_airport(airport_code)
    CO_ts = CO_ts.sel({'layer': vertical_layer, 'emission_inventory': emission_inventory, 'region': emission_region}, drop=True)

    # add NaN's between time epochs spaced > 4 days
    dtime_threshold = np.timedelta64(4, 'D')
    time = CO_ts['time'].reset_coords(drop=True)
    dtime = time.diff('i').values
    nan_idx, = np.nonzero(dtime > dtime_threshold)

    CO_ts2 = CO_ts.swap_dims({'i': 'time'})

    stats = ['mean', 'min', 'max']
    df = {
        'CO': {stat: helper.insert_nan(CO_ts2[f'CO_{stat}'].to_series(), nan_idx) for stat in stats}
    }
    for ei in emission_inventory:
        df[ei] = {stat: helper.insert_nan(CO_ts2[f'CO_contrib_{stat}'].sel({'emission_inventory': ei}).to_series(), nan_idx) for stat in stats}

    fig = charts.multi_line(df, line_dash_style_by_sublabel={'mean': 'solid', 'min': 'dot', 'max': 'dash'})
    fig.update_traces(
        line={'width': 1},
        customdata=helper.insert_nan(np.arange(len(df['CO']['mean'])), nan_idx)
    )
    # print(fig['data'])
    return fig


@callback(
    Output(CO_GRAPH_ID, 'figure', allow_duplicate=True),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data'),
    prevent_initial_call=True,
)
@log_exception
def patch_CO_graph(airport_code, curent_time_idx_by_airport):
    fig = Patch()
    print(curent_time_idx_by_airport)
    _, curr_time = curent_time_idx_by_airport[airport_code]

    fig['layout']['shapes'] = [
        {
            'line': {'color': 'yellow', 'width': 2, 'dash': 'dot'},
            'type': 'line',
            'x0': curr_time,
            'x1': curr_time,
            'xref': 'x',
            'y0': 0,
            'y1': 1,
            'yref': 'y domain',
        }
    ]
    return fig
