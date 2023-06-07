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
    NEXT_TIME_BUTTON_ID, CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, \
    CO_GRAPH_ID, EMISSION_INVENTORY_CHECKLIST_ID,  EMISSION_REGION_SELECT_ID, TIME_SELECT_ID, \
    airport_name_by_code, airports_df
from footprint_utils import footprint_viz, helper
from footprint_data_access import get_residence_time, get_flight_id_and_profile_by_airport_and_profile_idx, \
    nprofiles_by_airport, get_CO_ts, get_coords_by_airport_and_profile_idx


@functools.lru_cache(maxsize=128)
def get_footprint_img(airport_code, layer, profile_idx):
    print(f'get_footprint_img({airport_code}, {layer}, {profile_idx})')
    flight_id, profile = get_flight_id_and_profile_by_airport_and_profile_idx(airport_code, profile_idx)
    res_time_per_km2 = get_residence_time(flight_id, profile, layer)
    if res_time_per_km2 is not None:
        da = res_time_per_km2.load()
        # print(da.sum().item())
        return footprint_viz.get_footprint_viz(da)
    else:
        return None


@callback(
    Output(AIRPORT_SELECT_ID, 'value'),
    Input(FOOTPRINT_MAP_GRAPH_ID, 'clickData'),
)
def update_airport_on_map_click(map_click_data):
    if map_click_data is not None and 'points' in map_click_data and len(map_click_data['points']) > 0:
        clicked_airport, = map_click_data['points']
        airport_code = airports_df.iloc[clicked_airport['pointIndex']]['short_name']
        return airport_code
    else:
        return dash.no_update


@callback(
    Output(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(PREVIOUS_TIME_BUTTON_ID, 'n_clicks'),
    Input(NEXT_TIME_BUTTON_ID, 'n_clicks'),
    Input(CO_GRAPH_ID, 'clickData'),
    State(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
)
@log_exception
def update_current_time_by_airport(airport_code, previous_time_click, next_time_click, co_graph_click_data, current_profile_idx_by_airport):
    dash_ctx = list(dash.ctx.triggered_prop_ids.values())

    if co_graph_click_data is not None and CO_GRAPH_ID in dash_ctx:
        # TODO: get profile_idx from customdata
        profile_idx = co_graph_click_data['points'][0]['customdata']
    elif airport_code is not None:
        profile_idx = current_profile_idx_by_airport.get(airport_code, 0)
    else:
        raise dash.exceptions.PreventUpdate

    if PREVIOUS_TIME_BUTTON_ID in dash_ctx and profile_idx > 0:
        profile_idx -= 1
    if NEXT_TIME_BUTTON_ID in dash_ctx and profile_idx < nprofiles_by_airport[airport_code] - 1:
        profile_idx += 1

    # curr_time = pd.Timestamp(CO_ts['time'].isel({'i': profile_idx}).item())
    current_profile_idx_by_airport[airport_code] = profile_idx
    return current_profile_idx_by_airport



# @callback(
#     Output(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data'),
#     Output(TIME_SELECT_ID, 'value'),
#     Output(TIME_SELECT_ID, 'options'),
#     Input(AIRPORT_SELECT_ID, 'value'),
#     Input(TIME_SELECT_ID, 'value'),
#     Input(PREVIOUS_TIME_BUTTON_ID, 'n_clicks'),
#     Input(NEXT_TIME_BUTTON_ID, 'n_clicks'),
#     Input(CO_GRAPH_ID, 'clickData'),
#     State(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data'),
# )
# @log_exception
# def update_current_time_by_airport(airport_code, time_idx, previous_time_click, next_time_click, co_graph_click_data, current_time_idx_by_airport):
#     dash_ctx = list(dash.ctx.triggered_prop_ids.values())
#
#     time_by_time_idx = dash.no_update
#     _, CO_ts, idx_by_i = get_residtime_COts_idx_by_airport(airport_code)
#     if co_graph_click_data is not None and CO_GRAPH_ID in dash_ctx:
#         time_idx = co_graph_click_data['points'][0]['customdata']
#     elif time_idx is not None and TIME_SELECT_ID in dash_ctx:
#         try:
#             time_idx = int(time_idx)
#         except ValueError:
#             time_idx = 0
#     elif airport_code is not None and AIRPORT_SELECT_ID in dash_ctx:
#         time_idx, _ = current_time_idx_by_airport.get(airport_code, (0, np.datetime64('nat')))
#         time_by_time_idx = dict(CO_ts['time'].to_series())
#     elif time_idx is not None and PREVIOUS_TIME_BUTTON_ID in dash_ctx and time_idx > 0:
#         time_idx -= 1
#     elif time_idx is not None and NEXT_TIME_BUTTON_ID in dash_ctx and time_idx < len(idx_by_i) - 1:
#         time_idx += 1
#     else:
#         raise dash.exceptions.PreventUpdate
#
#     print(time_idx, type(time_idx), CO_ts['time'])
#     curr_time = pd.Timestamp(CO_ts['time'].isel({'i': time_idx}).item())
#     current_time_idx_by_airport[airport_code] = time_idx, curr_time
#     return current_time_idx_by_airport, time_idx, time_by_time_idx


@callback(
    Output(FOOTPRINT_MAP_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
    prevent_initial_call=True,
)
@log_exception
def update_footprint_map(airport_code, vertical_layer, current_profile_idx_by_airport):
    if current_profile_idx_by_airport is None:
        raise dash.exceptions.PreventUpdate
    try:
        profile_idx = current_profile_idx_by_airport[airport_code]
    except KeyError:
        raise dash.exceptions.PreventUpdate

    mapbox_layer = get_footprint_img(airport_code, vertical_layer, profile_idx)

    fig = Patch()

    curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
    title = f'Footprint with origin at {airport_name_by_code[airport_code]} ({airport_code}), ' \
            f'layer={vertical_layer}; time={pd.Timestamp(curr_time).strftime("%Y-%m-%d %H:%M")}'
    fig['layout']['title'] = title
    fig['layout']['mapbox']['layers'] = [mapbox_layer]
    return fig


@callback(
    Output(CO_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(EMISSION_INVENTORY_CHECKLIST_ID, 'value'),
    Input(EMISSION_REGION_SELECT_ID, 'value'),
    Input(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
)
@log_exception
def update_CO_fig(airport_code, vertical_layer, emission_inventory, emission_region, current_profile_idx_by_airport):
    emission_inventory = sorted(emission_inventory)

    CO_ts = get_CO_ts(airport_code)
    CO_ts = CO_ts.sel({'layer': vertical_layer, 'emission_inventory': emission_inventory, 'region': emission_region}, drop=True)

    # add NaN's between time epochs spaced > 4 days
    dtime_threshold = np.timedelta64(4, 'D')
    time = CO_ts['time'].reset_coords(drop=True)
    dtime = time.diff('profile_idx').values
    nan_idx, = np.nonzero(dtime > dtime_threshold)

    # print(nan_idx, type(nan_idx))

    CO_ts2 = CO_ts.swap_dims({'profile_idx': 'time'})
    stat = 'mean'
    df = {
        'IAGOS': helper.insert_nan(CO_ts2[f'CO_{stat}'].to_series(), nan_idx)
    }
    for ei in emission_inventory:
        df[ei] = helper.insert_nan(CO_ts2[f'CO_contrib_{stat}'].sel({'emission_inventory': ei}).to_series(), nan_idx)

    fig = charts.multi_line(
        df,
        # use_GL=False,
        # line_dash_style_by_sublabel={'mean': 'solid', 'min': 'dot', 'max': 'dash'}
    )
    fig.update_traces(
        # line={'width': 1},
        line={'width': 2},
        customdata=helper.insert_nan(np.arange(len(CO_ts2['time'])), nan_idx),
    )
    fig.update_layout(
        # xaxis={
            # 'rangeslider': {'visible': True},
            # 'type': 'date',
        # },
        legend={
            'orientation': 'v',
            'yanchor': 'top',
            'y': 1,
            'xanchor': 'left',
            'x': 1.05,
        },
        title={
            'text': f'CO measurements by IAGOS and CO contributions by SOFT-IO (ppb)'
                    f'<br><sup>{airport_name_by_code[airport_code]} ({airport_code}); layer={vertical_layer}; '
                    f'emission regions={emission_region}</sup>',
        },
        uirevision=airport_code,
    )

    fig.update_layout(
        {
            'xaxis': {'domain': [0, 1]},
            'yaxis': {'domain': [0, 0.48]},
            'yaxis2': {'domain': [0.52, 1], 'overlaying': 'free'},
            'yaxis3': {'domain': [0.52, 1], 'overlaying': 'y2'},
        }
    )

    if current_profile_idx_by_airport is not None and airport_code in current_profile_idx_by_airport:
        profile_idx = current_profile_idx_by_airport[airport_code]
        curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
        curr_time = pd.Timestamp(curr_time)
        print(f'time={curr_time}')
        fig['layout']['shapes'] = [
            {
                'line': {'color': 'grey', 'width': 1, 'dash': 'dot'},
                'type': 'line',
                'x0': curr_time,
                'x1': curr_time,
                'xref': 'x',
                'y0': 0,
                'y1': 1 / 0.48,
                'yref': 'y domain',
            }
        ]

    return fig
