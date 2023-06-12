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
from plotly.subplots import make_subplots


sys.path.append('/home/wolp/PycharmProjects/atmo-access-time-series2')
from utils import charts

from log import log_exception, logger, log_callback
from layout import AIRPORT_SELECT_ID, VERTICAL_LAYER_RADIO_ID, FOOTPRINT_MAP_GRAPH_ID, PREVIOUS_TIME_BUTTON_ID, \
    NEXT_TIME_BUTTON_ID, CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, \
    CO_GRAPH_ID, PROFILE_GRAPH_ID, EMISSION_INVENTORY_CHECKLIST_ID,  EMISSION_REGION_SELECT_ID, TIME_SELECT_ID, \
    airport_name_by_code, airports_df
from footprint_utils import footprint_viz, helper
from footprint_data_access import get_residence_time, get_flight_id_and_profile_by_airport_and_profile_idx, \
    nprofiles_by_airport, get_CO_ts, get_coords_by_airport_and_profile_idx, get_COprofile, get_COprofile_climatology


USE_GL = 500


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
    title = f'10-day backward footprint with origin at {airport_name_by_code[airport_code]} ({airport_code}), ' \
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
    if emission_region != 'TOTAL':
        emission_region = [emission_region, 'TOTAL']
    else:
        emission_region = ['TOTAL']

    CO_ts = get_CO_ts(airport_code)
    CO_ts = CO_ts\
        .sel({'layer': vertical_layer, 'emission_inventory': emission_inventory, 'region': emission_region}, drop=True)\
        .assign_coords(customdata=('profile_idx', np.arange(len(CO_ts['profile_idx'])))) \
        .swap_dims({'profile_idx': 'time'})

    CO_ser = {}
    for lvl in [2, 1]:
        _CO_da = CO_ts['CO_mean'].where(CO_ts['CO_processing_level'] == lvl, drop=True)
        CO_ser[lvl] = (
            helper.insert_nan_into_timeseries_gaps(_CO_da.to_series()),
            helper.insert_nan_into_timeseries_gaps(_CO_da['customdata'].to_series())
        )

    SOFTIO_ser = {}
    for ei in emission_inventory:
        for reg in emission_region:
            _SOFTIO_da = CO_ts['CO_contrib_mean'].sel({'emission_inventory': ei, 'region': reg}, drop=True)
            SOFTIO_ser.setdefault(ei, {})[reg] = (
                helper.insert_nan_into_timeseries_gaps(_SOFTIO_da.to_series()),
                helper.insert_nan_into_timeseries_gaps(_SOFTIO_da['customdata'].to_series())
            )

    nrows = 2 if len(SOFTIO_ser) > 0 else 1
    fig = make_subplots(rows=nrows, cols=1, shared_xaxes=True, vertical_spacing=0.02) #vertical_spacing=0.3)

    # add traces with IAGOS CO
    for lvl, (ser, customdata) in CO_ser.items():
        if lvl == 2:
            color = 'rgba(0, 0, 0, 1)'
        else:
            color = 'rgba(100, 100, 100, 1)'

        if USE_GL and len(ser) > USE_GL:
            go_scatter = go.Scattergl
        else:
            go_scatter = go.Scatter

        trace = go_scatter(
            x=ser.index.values,
            y=ser.values,
            customdata=customdata.values,
            mode='lines+markers',
            name=f'L{lvl}',
            legendgroup='IAGOS',
            legendgrouptitle_text='IAGOS',
            marker={'color': color},
            line={'color': color},
        )

        fig.add_trace(trace, row=1, col=1)

    # add traces with SOFT-IO
    for ei in emission_inventory:
        for reg in emission_region:
            ser, customdata = SOFTIO_ser[ei][reg]

            if USE_GL and len(ser) > USE_GL:
                go_scatter = go.Scattergl
            else:
                go_scatter = go.Scatter

            trace = go_scatter(
                x=ser.index.values,
                y=ser.values,
                customdata=customdata.values,
                mode='lines+markers',
                name=f'{ei} {reg}',
                legendgroup='SOFT-IO',
                legendgrouptitle_text='SOFT-IO',
                #mode='lines',
                #marker={'color': color},
                #line={'color': color},
            )

            fig.add_trace(trace, row=2, col=1)

    if len(emission_inventory) > 1:
        emission_inventory_it = iter(emission_inventory)
        ei = next(emission_inventory_it)
        ser, customdata = SOFTIO_ser[ei]['TOTAL']
        print('customdata', customdata)
        for ei in emission_inventory_it:
            ser2, customdata2 = SOFTIO_ser[ei]['TOTAL']
            ser = ser + ser2
            customdata.update(customdata2)
            print('customdata2', customdata)

        if USE_GL and len(ser) > USE_GL:
            go_scatter = go.Scattergl
        else:
            go_scatter = go.Scatter

        trace = go_scatter(
            x=ser.index.values,
            y=ser.values,
            customdata=customdata.values,
            mode='lines+markers',
            name=f'{"+".join(emission_inventory)} TOTAL',
            legendgroup='SOFT-IO',
            legendgrouptitle_text='SOFT-IO',
            # mode='lines',
            # marker={'color': color},
            # line={'color': color},
        )

        fig.add_trace(trace, row=2, col=1)

    # fig.update_xaxes({'rangeslider': {'visible': True}, 'type': 'date'}, row=1)
    fig.update_xaxes(title='time', row=nrows)
    fig.update_yaxes(
        {
            'title': 'ppb',
        }
    )

    fig.update_layout(
        title={
            'text': f'CO measurements by IAGOS and modeled CO contributions by SOFT-IO (ppb)'
                    f'<br><sup>{airport_name_by_code[airport_code]} ({airport_code}); layer={vertical_layer}; '
                    f'emission regions={emission_region}</sup>',
        },
        uirevision=airport_code,
        legend_groupclick='toggleitem',
    )

    # draw vertical bar indicating a current time
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
                'y1': 1,
                'yref': 'paper',
            }
        ]

    # print(fig)

    return fig


@callback(
    Output(PROFILE_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(EMISSION_INVENTORY_CHECKLIST_ID, 'value'),
    Input(EMISSION_REGION_SELECT_ID, 'value'),
    Input(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
)
@log_exception
def update_COprofile_fig(airport_code, emission_inventory, emission_region, current_profile_idx_by_airport):
    emission_inventory = sorted(emission_inventory)
    if emission_region != 'TOTAL':
        emission_region = [emission_region, 'TOTAL']
    else:
        emission_region = ['TOTAL']

    if current_profile_idx_by_airport is None or airport_code not in current_profile_idx_by_airport:
        raise dash.exceptions.PreventUpdate

    profile_idx = current_profile_idx_by_airport[airport_code]

    print(f'get_COprofile({airport_code}, {profile_idx})')
    flight_id, profile = get_flight_id_and_profile_by_airport_and_profile_idx(airport_code, profile_idx)
    CO_profile_ds = get_COprofile(flight_id, profile)

    # prepare data for IAGOS CO profile
    CO_profile_ds = CO_profile_ds.coarsen({'air_press_AC': 3}).mean()
    lvl = CO_profile_ds['CO_processing_level'].item()
    # and build the trace
    color = 'rgba(0, 0, 0, 1)' if lvl == 2 else 'rgba(100, 100, 100, 1)'
    x_vals = CO_profile_ds['COprofile_mean'].values
    y_vals = CO_profile_ds['height'].values
    x_max_1 = np.nanmax(x_vals) if len(x_vals) > 0 else np.nan
    COprofile_trace = go.Scatter(
        x=x_vals,
        y=y_vals,
        mode='lines+markers',
        name=f'L{lvl}',
        legendgroup='IAGOS',
        legendgrouptitle_text='IAGOS',
        marker={'color': color},
        line={'color': color},
    )

    # prepare data for IAGOS CO 5y mean and std
    year = np.datetime64(str(CO_profile_ds['time'].dt.year.item()))
    clim_ds = get_COprofile_climatology().sel({'code': airport_code, 'year': year})
    clim_ds = clim_ds.coarsen({'air_press_AC': 3}).mean()
    # and build the trace
    y_vals = clim_ds['height'].values
    COclimat_trace = go.Scatter(
        x=clim_ds['CO_mean_5y'].values,
        y=y_vals,
        # error_x=go.scatter.ErrorX(array=_ds.CO_std_5y.values, symmetric=True, type='data'),
        mode='lines',
        name=f'5y mean',
        legendgroup='IAGOS',
        legendgrouptitle_text='IAGOS',
        # marker={'color': color},
        line={'color': 'black', 'dash': 'dot'},
    )
    COclimat_trace_1 = go.Scatter(
        x=clim_ds['CO_mean_5y'].values - clim_ds['CO_std_5y'].values,
        y=y_vals,
        mode='lines',
        line=dict(width=0),
        name=f'5y std 1',
        # legendgroup='IAGOS',
        # legendgrouptitle_text='IAGOS',
        showlegend=False,
        # marker={'color': color},
        # line={'color': color},
    )
    x_vals = clim_ds['CO_mean_5y'].values + clim_ds['CO_std_5y'].values
    x_max_2 = np.nanmax(x_vals) if len(x_vals) > 0 else np.nan
    COclimat_trace_2 = go.Scatter(
        x=x_vals,
        y=y_vals,
        mode='lines',
        line=dict(width=0),
        name=f'5y std',
        legendgroup='IAGOS',
        legendgrouptitle_text='IAGOS',
        # showlegend=False,
        fillcolor='rgba(68, 68, 68, 0.3)',
        fill='tonexty',  # marker={'color': color},
        # line={'color': color},
    )

    # prepare data and traces for SOFT-IO
    x_max_softio = []
    softio_traces = []
    for ei in emission_inventory:
        for reg in emission_region:
            x_vals = CO_profile_ds['COprofile_contrib_mean'].sel({'emission_inventory': ei, 'region': reg}).values
            if len(x_vals) > 0:
                x_max_softio.append(np.nanmax(x_vals))
            trace = go.Scatter(
                x=x_vals,
                y=CO_profile_ds['height'].values,
                mode='lines+markers',
                name=f'{ei} {reg}',
                legendgroup='SOFT-IO',
                legendgrouptitle_text='SOFT-IO',
                # mode='lines',
                # marker={'color': color},
                # line={'color': color},
            )
            softio_traces.append(trace)
    if len(emission_inventory) > 1:
        emission_inventory_it = iter(emission_inventory)
        ei = next(emission_inventory_it)
        x_vals = CO_profile_ds['COprofile_contrib_mean'].sel({'emission_inventory': ei, 'region': 'TOTAL'}).values
        for ei in emission_inventory_it:
            x_vals2 = CO_profile_ds['COprofile_contrib_mean'].sel({'emission_inventory': ei, 'region': 'TOTAL'}).values
            x_vals = x_vals + x_vals2
        if len(x_vals) > 0:
            x_max_softio.append(np.nanmax(x_vals))
        trace = go.Scatter(
            x=x_vals,
            y=CO_profile_ds['height'].values,
            mode='lines+markers',
            name=f'{"+".join(emission_inventory)} TOTAL',
            legendgroup='SOFT-IO',
            legendgrouptitle_text='SOFT-IO',
            # mode='lines',
            # marker={'color': color},
            # line={'color': color},
        )
        softio_traces.append(trace)

    x_max = np.nanmax([50, x_max_1, x_max_2] + x_max_softio)

    # build figure
    fig = go.Figure([COprofile_trace, COclimat_trace, COclimat_trace_1, COclimat_trace_2] + softio_traces)
    fig.update_xaxes(title='CO (ppb)', range=[-x_max * 0.02, x_max * 1.02], fixedrange=True)
    fig.update_yaxes(title='altitude (m a.s.l.)', range=[-100, 12e3], fixedrange=True)
    fig.update_layout(
        # width=400,
        height=600,
        legend_groupclick='toggleitem',
        showlegend=True,
    )

    curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
    curr_time = pd.Timestamp(curr_time)
    print(f'time={curr_time}')

    fig.update_layout(
        # xaxis={
            # 'rangeslider': {'visible': True},
            # 'type': 'date',
        # },
        # legend={
        #     'orientation': 'v',
        #     'yanchor': 'top',
        #     'y': 1,
        #     'xanchor': 'left',
        #     'x': 1.05,
        # },
        title={
            'text': f'Profile of CO measurements by IAGOS and modeled CO contributions by SOFT-IO (ppb)'
                    f'<br><sup>{airport_name_by_code[airport_code]} ({airport_code}); time={curr_time}',
                    # f'emission regions={emission_region}</sup>',
        },
        # uirevision=airport_code,
        # legend_groupclick='toggleitem', # enables toogling single items from group legend; see https://github.com/plotly/plotly.py/issues/3488
    )

    return fig

