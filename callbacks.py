import pathlib
import toolz
import pandas as pd
import xarray as xr
import dash
from dash import Output, Input, State, Patch, callback
import plotly.graph_objects as go


from log import log_exception, logger, log_callback
from layout import AIRPORT_SELECT_ID, VERTICAL_LAYER_RADIO_ID, FOOTPRINT_MAP_GRAPH_ID, PREVIOUS_TIME_BUTTON_ID, NEXT_TIME_BUTTON_ID, CURRENT_TIME_BY_AIRPORT_STORE_ID
from utils import footprint_viz


footprint_data_dir = pathlib.Path('/home/wolp/data/fp_agg/footprint_by_airport_code')

_ds_by_airport = {}

def get_ds_by_airport(code):
    code = code.upper()
    ds = _ds_by_airport.get(code)
    if ds is None:
        url = footprint_data_dir / f'{code}.nc'
        if not url.exists():
            raise FileNotFoundError(str(url))
        ds = xr.open_dataset(url)
        _ds_by_airport[code] = ds
    return ds


@callback(
    Output(FOOTPRINT_MAP_GRAPH_ID, 'figure'),
    Output(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data'),
    Input(AIRPORT_SELECT_ID, 'value'),
    Input(VERTICAL_LAYER_RADIO_ID, 'value'),
    Input(PREVIOUS_TIME_BUTTON_ID, 'n_clicks'),
    Input(NEXT_TIME_BUTTON_ID, 'n_clicks'),
    State(CURRENT_TIME_BY_AIRPORT_STORE_ID, 'data')
)
@log_exception
def update_footprint_map(airport_code, vertical_layer, previous_time_click, next_time_click, curent_time_by_airport):
    dash_ctx = list(dash.ctx.triggered_prop_ids.values())

    #fig = Patch()

    time_idx = curent_time_by_airport.get(airport_code, 0)

    ds = get_ds_by_airport(airport_code)

    if PREVIOUS_TIME_BUTTON_ID in dash_ctx and time_idx > 0:
        time_idx -= 1
    if NEXT_TIME_BUTTON_ID in dash_ctx and time_idx < len(ds['time']) - 1:
        time_idx += 1
    curr_time = pd.Timestamp(ds['time'][time_idx].item())

    da = ds['res_time_per_km2'].isel({'time': time_idx}).sel(layer=vertical_layer, drop=True).reset_coords(drop=True)
    print(da.sum())
    mapbox_layer = footprint_viz.get_footprint_viz(da.load())

    curent_time_by_airport[airport_code] = time_idx
    #fig['layout']['title'] = f'{airport_code} : {vertical_layer} : {curr_time.strftime("%Y-%m-%d")}'
    #fig['layout']['mapbox_layers'] = mapbox_layer

    fig = go.Figure(
        data=go.Scattermapbox(),
        layout={
            'mapbox_style': 'open-street-map',
            'mapbox_layers' : [mapbox_layer],
            #'mapbox_style': 'carto-positron',
            'margin': {'r': 10, 't': 30, 'l': 10, 'b': 10},
            'title': f'{airport_code} : {vertical_layer} : {curr_time.strftime("%Y-%m-%d")}',
            'width': 1000,
            'height': 600,
        }
    )


    return fig, curent_time_by_airport
