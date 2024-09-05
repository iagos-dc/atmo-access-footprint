import warnings
import sys
import pathlib
import toolz
import functools
import numpy as np
import pandas as pd
import xarray as xr
import dash
from dash import Output, Input, State, Patch
import dash_bootstrap_components as dbc

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from footprint_utils.exception_handler import callback_with_exc_handling, AppException, AppWarning


from log import log_exception, logger, log_callback, log_exectime
from layout import AIRPORT_SELECT_ID, VERTICAL_LAYER_RADIO_ID, FOOTPRINT_MAP_GRAPH_ID, PREVIOUS_TIME_BUTTON_ID, \
    DATE_FROM_ID, DATE_TO_ID, \
    NEXT_TIME_BUTTON_ID, REWIND_TIME_BUTTON_ID, FASTFORWARD_TIME_BUTTON_ID, CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, \
    CO_GRAPH_ID, PROFILE_GRAPH_ID, EMISSION_INVENTORY_CHECKLIST_ID,  EMISSION_REGION_SELECT_ID, TIME_INPUT_ID, \
    COLOR_HEX_BY_GFED4_REGION, COLOR_HEX_BY_EMISSION_INVENTORY, GEO_REGIONS_WITHOUT_TOTAL, FILLPATTERN_SHAPE_BY_EMISSION_INVENTORY, DATA_DOWNLOAD_BUTTON_ID, \
    DATA_DOWNLOAD_POPUP_ID, add_watermark, ONLY_SIGNIFICANT_REGIONS_CHECKBOX_ID, ONLY_SIGNIFICANT_REGIONS_PERCENTAGE_ID, \
    RESIDENCE_TIME_SCALE_RADIO_ID, RESIDENCE_TIME_CUTOFF_RADIO_ID, \
    IAGOS_COLOR_HEX, IAGOS_COLOR_BRIGHT_HEX, IAGOS_AIRPORT_SIZE
from footprint_utils import footprint_viz, helper
from footprint_data_access import get_residence_time, get_flight_id_and_profile_by_airport_and_profile_idx, \
    airports_df, airport_name_by_code, get_iagos_airports, \
    get_CO_ts, get_coords_by_airport_and_profile_idx, get_COprofile, get_COprofile_climatology


USE_GL = 500


# TODO: improve test for not available footprint data: see e.g. FRA in FT layer on 2013-02-23 06:38
@functools.lru_cache(maxsize=8)
def get_footprint_img(
        airport_code,
        layer,
        profile_idx,
        color_scale_transform=(np.log, np.exp),
        residence_time_cutoff=1e-3,
        update_center_and_zoom=True,
):
    def _calc_zoom(min_lat, max_lat, min_lon, max_lon):
        # source: https://stackoverflow.com/questions/46891914/control-mapbox-extent-in-plotly-python-api
        width_y = max_lat - min_lat
        width_x = max_lon - min_lon
        zoom_y = -1.446 * np.log(width_y) + 7.2753
        zoom_x = -1.415 * np.log(width_x) + 8.7068
        return min(np.around(zoom_y, decimals=2), np.around(zoom_x, decimals=2))

    # print(f'get_footprint_img({airport_code}, {layer}, {profile_idx})')
    fig = Patch()

    flight_id, profile = get_flight_id_and_profile_by_airport_and_profile_idx(airport_code, profile_idx)
    res_time_per_km2 = get_residence_time(flight_id, profile, layer)
    if res_time_per_km2 is not None:
        da = res_time_per_km2.load()
        img, coordinates, colorscale_trace = footprint_viz.get_footprint_viz(
            da,
            color_scale_transform=color_scale_transform,
            residence_time_cutoff=residence_time_cutoff,
        )
        fig['layout']['mapbox']['layers'] = [{
            'sourcetype': 'image',
            'source': img,
            'coordinates': coordinates,
        }]
        fig['data'][1] = colorscale_trace
        del fig['layout']['annotations'][1]

        if update_center_and_zoom:
            # get spatial extent
            try:
                lons, lats = zip(*coordinates)
                min_lat, max_lat, min_lon, max_lon = min(lats), max(lats), min(lons), max(lons)
                center_lon, center_lat = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
                fig['layout']['mapbox']['center'] = {'lon': center_lon, 'lat': center_lat}
                zoom = _calc_zoom(min_lat, max_lat, min_lon, max_lon)
                fig['layout']['mapbox']['zoom'] = zoom
            except Exception as e:
                logger().exception('_calc_zoom exception', exc_info=e)
    else:
        annotation = dict(
            name="n/a",
            text="Footprint not available",
            # textangle=textangle,
            # opacity=0.05,
            font=dict(color="black", size=75),
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        fig['layout']['annotations'][1] = annotation
        del fig['layout']['mapbox']['layers']
        del fig['data'][1]
    return fig


# Begin of callback definitions and their helper routines.
# See: https://dash.plotly.com/basic-callbacks
# for a basic tutorial and
# https://dash.plotly.com/  -->  Dash Callback in left menu
# for more detailed documentation


@callback_with_exc_handling(
    Output(AIRPORT_SELECT_ID, 'options'),
    Output(AIRPORT_SELECT_ID, 'value'),
    Output(DATE_FROM_ID, 'value'),
    Output(DATE_TO_ID, 'value'),
    Input(DATE_FROM_ID, 'value'),
    Input(DATE_TO_ID, 'value'),
    State(AIRPORT_SELECT_ID, 'value')
)
@log_exception
def filter_airports_by_dates(date_from, date_to, previous_airport_code):
    airports_df, _ = get_iagos_airports(date_from=date_from, date_to=date_to)
    options = [
        {
            'label': f'{long_name} ({short_name}) - {nprofiles} profiles',
            'value': short_name
        }
        for short_name, long_name, nprofiles in zip(airports_df['short_name'], airports_df['long_name'], airports_df['nprofiles'])
    ]
    if options:
        if previous_airport_code and previous_airport_code in list(airports_df['short_name']):
            value = previous_airport_code
        else:
            nprofiles_max = airports_df['nprofiles'].max()
            value = airports_df[airports_df['nprofiles'] == nprofiles_max]['short_name'].iloc[0]
    else:
        warnings.warn('No airports found for the chosen dates', category=AppWarning)
        return dash.no_update, dash.no_update, None, None
    return options, value, dash.no_update, dash.no_update


@callback_with_exc_handling(
    Output(AIRPORT_SELECT_ID, 'value', allow_duplicate=True),
    Input(FOOTPRINT_MAP_GRAPH_ID, 'clickData'),
    Input(DATE_FROM_ID, 'value'),
    Input(DATE_TO_ID, 'value'),
    prevent_initial_call=True,
)
@log_exception
def update_airport_on_map_click(map_click_data, date_from, date_to):
    if map_click_data is not None and 'points' in map_click_data and len(map_click_data['points']) > 0:
        clicked_airport, = map_click_data['points']
        airport_code = airports_df.iloc[clicked_airport['pointIndex']]['short_name']
        # check if airport is 'active'
        time_filtered_airports_df, _ = get_iagos_airports(date_from=date_from, date_to=date_to)
        if airport_code in list(time_filtered_airports_df['short_name']):
            return airport_code
    return dash.no_update


@callback_with_exc_handling(
    Output(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
    Output(TIME_INPUT_ID, 'value'),
    Output(TIME_INPUT_ID, 'invalid'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(PREVIOUS_TIME_BUTTON_ID, 'n_clicks'),
    Input(NEXT_TIME_BUTTON_ID, 'n_clicks'),
    Input(REWIND_TIME_BUTTON_ID, 'n_clicks'),
    Input(FASTFORWARD_TIME_BUTTON_ID, 'n_clicks'),
    Input(CO_GRAPH_ID, 'clickData'),
    Input(TIME_INPUT_ID, 'value'),
    Input(DATE_FROM_ID, 'value'),
    Input(DATE_TO_ID, 'value'),
    State(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
)
@log_exception
def update_current_time_by_airport(
        airport_code,
        previous_time_click, next_time_click, rew_time_click, ff_time_click,
        co_graph_click_data,
        time_input,
        date_from, date_to,
        current_profile_idx_by_airport
):
    dash_ctx = list(dash.ctx.triggered_prop_ids.values())

    CO_ts = get_CO_ts(airport_code, date_from=date_from, date_to=date_to)
    profile_indexes = CO_ts['profile_idx_for_airport'].values
    min_profile_idx, max_profile_idx = profile_indexes[[0, -1]]

    if co_graph_click_data is not None and CO_GRAPH_ID in dash_ctx:
        # TODO: get profile_idx from customdata
        profile_idx = co_graph_click_data['points'][0]['customdata']
    elif airport_code is not None:
        profile_idx = current_profile_idx_by_airport.get(airport_code, -1)
    else:
        raise dash.exceptions.PreventUpdate

    big_time_step = max(int((max_profile_idx - min_profile_idx + 1) * 0.05), 5)
    if PREVIOUS_TIME_BUTTON_ID in dash_ctx:
        profile_idx -= 1
    if NEXT_TIME_BUTTON_ID in dash_ctx:
        profile_idx += 1
    if REWIND_TIME_BUTTON_ID in dash_ctx:
        profile_idx -= big_time_step
    if FASTFORWARD_TIME_BUTTON_ID in dash_ctx:
        profile_idx += big_time_step
    profile_idx = min(max(profile_idx, min_profile_idx), max_profile_idx)

    current_profile_idx_by_airport[airport_code] = profile_idx

    curr_time = CO_ts['time'][profile_idx - min_profile_idx].item()
    curr_time = pd.Timestamp(curr_time).strftime("%Y-%m-%d %H:%M")

    return current_profile_idx_by_airport, curr_time, False


def _update_footprint_map_comment(
        airport_code, vertical_layer, current_profile_idx_by_airport,
        *args, **kwargs
):
    airport_name = airport_name_by_code[airport_code]
    profile_idx = current_profile_idx_by_airport.get(airport_code, 0)
    curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
    return f'Footprint from {vertical_layer} layer over {airport_name} ({airport_code}) on {pd.Timestamp(curr_time).strftime("%Y-%m-%d %H:%M")}'


@callback_with_exc_handling(
    Output(FOOTPRINT_MAP_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
    Input(DATE_FROM_ID, 'value'),
    Input(DATE_TO_ID, 'value'),
    Input(RESIDENCE_TIME_SCALE_RADIO_ID, 'value'),
    Input(RESIDENCE_TIME_CUTOFF_RADIO_ID, 'value'),
    prevent_initial_call=True,
)
@log_exception
@log_callback(log_callback_context=False, comment_func=_update_footprint_map_comment)
def update_footprint_map(
        airport_code, vertical_layer, current_profile_idx_by_airport,
        date_from, date_to, residence_time_scale, residence_time_cutoff,
):
    if current_profile_idx_by_airport is None:
        raise dash.exceptions.PreventUpdate
    try:
        profile_idx = current_profile_idx_by_airport[airport_code]
    except KeyError:
        raise dash.exceptions.PreventUpdate

    dash_ctx = list(dash.ctx.triggered_prop_ids.values())

    if residence_time_scale == 'lin':
        color_scale_transform = (lambda x: x, lambda x: x)
    elif residence_time_scale == 'sqrt':
        color_scale_transform = (np.sqrt, lambda x: x ** 2)
    elif residence_time_scale == 'log':
        color_scale_transform = (np.log, np.exp)
    else:
        raise ValueError(f'unknown residence_time_scale={residence_time_scale}')

    # change center and zoom only when airport has changed
    update_center_and_zoom = AIRPORT_SELECT_ID in dash_ctx

    fig = get_footprint_img(
        airport_code,
        vertical_layer,
        profile_idx,
        color_scale_transform=color_scale_transform,
        residence_time_cutoff=residence_time_cutoff,
        update_center_and_zoom=update_center_and_zoom,
    )

    # apply station color to fig (cyan for chosen station)
    _color_series = pd.Series(IAGOS_COLOR_HEX, index=airports_df.index)
    _size_series = pd.Series(IAGOS_AIRPORT_SIZE, index=airports_df.index)
    _color_series.loc[airports_df['short_name'] == airport_code] = 'green' #IAGOS_COLOR_BRIGHT_HEX
    _size_series.loc[airports_df['short_name'] == airport_code] = 1.5 * IAGOS_AIRPORT_SIZE
    fig['data'][0]['marker']['color'] = _color_series.values
    fig['data'][0]['marker']['size'] = _size_series.values

    # apply station opacity to fig
    _, airport_mask = get_iagos_airports(date_from=date_from, date_to=date_to)
    if airport_mask is not None:
        _opacity_series = pd.Series(0.2, index=airports_df.index)
        _opacity_series[airport_mask] = 1
        _opacity_series = _opacity_series.values
    else:
        _opacity_series = 1
    fig['data'][0]['marker']['opacity'] = _opacity_series

    curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
    title = f'IAGOS airports and 10-day backward footprint (residence time in a total air column during 10-day period)' \
            f'<br>with the <b>{vertical_layer}</b> layer over {airport_name_by_code[airport_code]} (<b>{airport_code}</b>) ' \
            f'on <b>{pd.Timestamp(curr_time).strftime("%Y-%m-%d %H:%M")}</b> as a receptor'
    fig['layout']['title'] = title

    return fig


@callback_with_exc_handling(
    Output(CO_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(EMISSION_INVENTORY_CHECKLIST_ID, 'value'),
    Input(EMISSION_REGION_SELECT_ID, 'value'),
    Input(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
    Input(DATE_FROM_ID, 'value'),
    Input(DATE_TO_ID, 'value'),
)
@log_exception
def update_CO_fig(
        airport_code, vertical_layer, emission_inventory, emission_region, current_profile_idx_by_airport,
        date_from, date_to
):
    if not airport_code:
        raise dash.exceptions.PreventUpdate

    emission_inventory = sorted(emission_inventory)

    CO_ts = get_CO_ts(airport_code, date_from=date_from, date_to=date_to)
    CO_ts = CO_ts\
        .sel({'layer': vertical_layer, 'emission_inventory': emission_inventory, 'region': emission_region}, drop=True)\
        .assign_coords({'customdata': CO_ts['profile_idx_for_airport']})\
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
        _SOFTIO_da = CO_ts['CO_contrib_mean'].sel({'emission_inventory': ei}, drop=True)
        SOFTIO_ser[ei] = (
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
            marker={'color': color, 'size': 5},
            line={'color': color, 'width': 1},
        )

        fig.add_trace(trace, row=1, col=1)

    # add traces with SOFT-IO
    for ei in emission_inventory:
        ser, customdata = SOFTIO_ser[ei]

        if USE_GL and len(ser) > USE_GL:
            go_scatter = go.Scattergl
        else:
            go_scatter = go.Scatter

        color = COLOR_HEX_BY_EMISSION_INVENTORY.get(ei)
        if color is not None:
            trace_kwargs = {
                'marker_color': color,
                'line_color': color
            }
        else:
            trace_kwargs = {}

        trace = go_scatter(
            x=ser.index.values,
            y=ser.values,
            customdata=customdata.values,
            mode='lines+markers',
            name=f'{ei} {emission_region}',
            legendgroup='SOFT-IO',
            legendgrouptitle_text='SOFT-IO',
            marker={'size': 3},
            **trace_kwargs
        )

        fig.add_trace(trace, row=2, col=1)

    # SOFT-IO total
    if len(emission_inventory) > 1:
        emission_inventory_it = iter(emission_inventory)
        ei = next(emission_inventory_it)
        ser, customdata = SOFTIO_ser[ei]
        for ei in emission_inventory_it:
            ser2, customdata2 = SOFTIO_ser[ei]
            ser = ser + ser2
            customdata.update(customdata2)

        if USE_GL and len(ser) > USE_GL:
            go_scatter = go.Scattergl
        else:
            go_scatter = go.Scatter

        color = COLOR_HEX_BY_EMISSION_INVENTORY['ALL']
        trace = go_scatter(
            x=ser.index.values,
            y=ser.values,
            customdata=customdata.values,
            mode='lines+markers',
            name='<br>+'.join([f'{ei} {emission_region}' for ei in emission_inventory]),
            legendgroup='SOFT-IO',
            legendgrouptitle_text='SOFT-IO',
            line={'color': color},
            marker={'size': 3, 'color': color},
        )

        fig.add_trace(trace, row=2, col=1)

    # fig.update_xaxes({'rangeslider': {'visible': True}, 'type': 'date'}, row=1)
    fig.update_xaxes(title='', row=nrows)
    # fig.update_xaxes(title='time', row=nrows)
    # fig.update_xaxes(visible=False, showticklabels=True)
    fig.update_yaxes(
        {
            'title': 'ppb',
        }
    )

    fig.update_layout(
        title={
            'text': f'CO measurements by IAGOS and modelled CO contributions by SOFT-IO (ppb)'
                    f'<br>over {airport_name_by_code[airport_code]} (<b>{airport_code}</b>), '
                    f'averaged in the <b>{vertical_layer}</b> layer',
                    #f'emission regions={", ".join(emission_region)}</sup>',
        },
        uirevision=airport_code,
        autosize=False,
        margin={'autoexpand': True, 'r': 0, 't': 60, 'l': 0, 'b': 0},
        legend={
            'groupclick': 'toggleitem',
            'tracegroupgap': 120,
        },
        # modebar={'orientation': 'v'}
    )

    # draw vertical bar indicating a current time
    if current_profile_idx_by_airport is not None and airport_code in current_profile_idx_by_airport:
        profile_idx = current_profile_idx_by_airport[airport_code]
        curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
        curr_time = pd.Timestamp(curr_time)
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

    return add_watermark(fig)


@callback_with_exc_handling(
    Output(PROFILE_GRAPH_ID, 'figure'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(EMISSION_INVENTORY_CHECKLIST_ID, 'value'),
    Input(CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, 'data'),
    Input(ONLY_SIGNIFICANT_REGIONS_CHECKBOX_ID, 'value'),
    Input(ONLY_SIGNIFICANT_REGIONS_PERCENTAGE_ID, 'value'),
)
@log_exception
def update_COprofile_fig(
        airport_code,
        emission_inventory,
        current_profile_idx_by_airport,
        only_significant_regions,
        only_significat_regions_percentage,
):
    emission_inventory = sorted(emission_inventory)

    if current_profile_idx_by_airport is None or airport_code not in current_profile_idx_by_airport:
        raise dash.exceptions.PreventUpdate

    profile_idx = current_profile_idx_by_airport[airport_code]

    # print(f'get_COprofile({airport_code}, {profile_idx})')
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
        mode='lines',
        name=f'5y mean',
        legendgroup='IAGOS',
        legendgrouptitle_text='IAGOS',
        line={'color': 'black', 'dash': 'dot'},
    )
    COclimat_trace_1 = go.Scatter(
        x=clim_ds['CO_mean_5y'].values - clim_ds['CO_std_5y'].values,
        y=y_vals,
        mode='lines',
        line=dict(width=0),
        name=f'5y std 1',
        showlegend=False,
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
        fillcolor='rgba(68, 68, 68, 0.3)',
        fill='tonexty',
    )

    # prepare data and traces for SOFT-IO
    COprofile_contrib = CO_profile_ds['COprofile_contrib_mean']\
        .sel({'emission_inventory': emission_inventory})\
        .dropna('emission_inventory', how='all')
    emission_inventory_without_all_nans = list(COprofile_contrib['emission_inventory'].values)
    # print('emission_inventory_without_all_nans', emission_inventory_without_all_nans)

    x_max_softio = []
    softio_traces = []

    # SOFT-IO TOTAL
    if len(emission_inventory_without_all_nans) > 0:
        softio_total = COprofile_contrib.sel({'region': 'TOTAL'}).sum('emission_inventory')
        if len(softio_total.values) > 0:
            x_max_softio.append(np.nanmax(softio_total.values))

        color = COLOR_HEX_BY_EMISSION_INVENTORY['ALL']
        if color is not None:
            trace_kwargs = {
                'marker_color': color,
                'line_color': color
            }
        else:
            trace_kwargs = {}

        trace = go.Scatter(
            x=softio_total.values,
            y=CO_profile_ds['height'].values,
            mode='lines+markers',
            marker={'size': 3},
            name='<br>+'.join([f'{ei} TOTAL' for ei in emission_inventory_without_all_nans]),
            legendgroup='SOFT-IO TOTAL',
            legendgrouptitle_text='SOFT-IO TOTAL',
            **trace_kwargs
        )
        softio_traces.append(trace)

    # SOFT-IO by regions
    for ei in emission_inventory_without_all_nans:
        COprofile_contrib_for_ei = COprofile_contrib\
            .sel({'emission_inventory': ei})\
            .drop_sel({'region': 'TOTAL'})
        if only_significant_regions and only_significat_regions_percentage is not None:
            # ignore regions which contributes < 1% than SOFT-IO total contribution from all emission inventories
            COprofile_contrib_for_ei = COprofile_contrib_for_ei\
                .where(COprofile_contrib_for_ei > softio_total * (only_significat_regions_percentage / 100))\
                .dropna('region', how='all')

        for reg in COprofile_contrib_for_ei['region'].values:
            x_vals = COprofile_contrib_for_ei.sel({'region': reg}).values

            # TODO: do sth to see hover better, e.g. ignore values < 0.1 in the hover:
            x_vals = np.nan_to_num(x_vals)  # to prevent the peculair behavoir of plotly fill area plots ???

            if len(x_vals) > 0:
                x_max_softio.append(np.nanmax(x_vals))

            color = COLOR_HEX_BY_GFED4_REGION[reg]
            trace = go.Scatter(
                x=x_vals,
                y=CO_profile_ds['height'].values,
                mode='lines',
                name=f'{reg}',
                legendgroup=f'SOFT-IO {ei}',
                legendgrouptitle_text=f'SOFT-IO {ei}',
                stackgroup='one',
                orientation='h',
                line={'color': color, 'width': 0},
                fillpattern={
                    'shape': FILLPATTERN_SHAPE_BY_EMISSION_INVENTORY.get(ei, 'x'),
                    'fgopacity': 0.3
                }
            )
            softio_traces.append(trace)

    x_max = np.nanmax([50, x_max_1, x_max_2] + x_max_softio)

    curr_time = get_coords_by_airport_and_profile_idx(airport_code, profile_idx)['time'].item()
    curr_time = pd.Timestamp(curr_time).strftime("%Y-%m-%d %H:%M")

    # build figure
    fig = go.Figure([COprofile_trace, COclimat_trace, COclimat_trace_1, COclimat_trace_2] + softio_traces)
    fig.update_xaxes(title='CO (ppb)', range=[0, x_max * 1.05], fixedrange=False)  # min_range: -x_max * 0.05
    fig.update_yaxes(title='altitude (m a.s.l.)', range=[-100, 12e3], fixedrange=False)
    fig.update_layout(
        # width=400,
        height=650,
        title={
            'text': f'Profile of CO measurements by IAGOS and<br>modelled CO contributions by SOFT-IO (ppb)'
                    f'<br>over {airport_name_by_code[airport_code]} (<b>{airport_code}</b>) on <b>{curr_time}</b>',
        },
        legend={
            'groupclick': 'toggleitem',
            'traceorder': 'grouped',
            'orientation': 'v',
        },
        showlegend=True,
        autosize=False,
        margin={'autoexpand': True, 'r': 180, 't': 105, 'l': 0, 'b': 0},
        uirevision=f'{flight_id} {profile} {emission_inventory}',
    )

    return add_watermark(fig, textangle=-60, size=75)


@callback_with_exc_handling(
    Output(DATA_DOWNLOAD_POPUP_ID, 'children'),
    Input(DATA_DOWNLOAD_BUTTON_ID, 'n_clicks'),
    prevent_initial_call=True,
)
@log_exception
@log_callback(log_callback_context=False)
def download_data_popup(data_download_button_click):
    popup = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle('Data download will be available soon')),
            # dbc.ModalBody(children='Data download will be available soon.'),
        ],
        id="modal-xl",
        size="xl",
        is_open=True,
    )

    return popup
