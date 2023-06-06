from dash import dcc, Dash
from dash import html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px

import footprint_data_access


IAGOS_COLOR_HEX = '#456096'
IAGOS_AIRPORT_SIZE = 10
MAPBOX_STYLES = {
    'open-street-map': 'open street map',
    'carto-positron': 'carto positron',
}
DEFAULT_MAPBOX_STYLE = 'carto-positron'


CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID = 'current_profile_idx_by_airport_store'

AIRPORT_SELECT_ID = 'airport_select'
VERTICAL_LAYER_RADIO_ID = 'vertical_layer_radio'
TIME_SELECT_ID = 'time_select'
PERIOD_FROM_INPUT_ID = 'period_from_input'
PERIOD_TO_INPUT_ID = 'period_to_input'
EMISSION_INVENTORY_CHECKLIST_ID = 'emission_inventory_checklist'
EMISSION_REGION_SELECT_ID = 'emission_region_select'
DATA_DOWNLOAD_BUTTON_ID = 'data_download_button'
PREVIOUS_TIME_BUTTON_ID = 'previous_time_button'
NEXT_TIME_BUTTON_ID = 'next_time_button'
FOOTPRINT_MAP_GRAPH_ID = 'footprint_map_graph'
CO_GRAPH_ID = 'CO_graph'

GEO_REGIONS = ['BONA', 'TENA', 'CEAM', 'NHSA', 'SHSA', 'EURO', 'MIDE', 'NHAF', 'SHAF', 'BOAS', 'CEAS', 'SEAS', 'EQAS', 'AUST', 'TOTAL']


airports_df = footprint_data_access.get_iagos_airports(top=10).sort_values('long_name')
airport_name_by_code = dict(zip(airports_df['short_name'], airports_df['long_name']))


def get_app_data_stores():
    return [
        dcc.Store(id=CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, data={})
    ]


def get_airports_map(airports_df):
    fig = px.scatter_mapbox(
        airports_df,
        lat='latitude', lon='longitude', #color=IAGOS_COLOR_HEX,
        hover_name="long_name",
        hover_data={
             'nprofiles': True,
             'longitude': ':.2f',
             'latitude': ':.2f',
             'ground elevation': airports_df['altitude'].round(0).fillna('N/A').to_list(),
             # 'marker_size': False
         },
        size_max=7,
        zoom=2,
        # width=1200, height=700,
        center={'lon': 10, 'lat': 55},
        title='IAGOS airports',
    )

    fig.update_traces(
        marker={'color': IAGOS_COLOR_HEX, 'size': IAGOS_AIRPORT_SIZE},
        marker_sizemode='area',
        name='IAGOS airports',
        #legendgroup='IAGOS airports3',
        showlegend=True,
    )

    # fig.update_layout(
    #     {
    #         #'mapbox_style': 'open-street-map',
    #         'mapbox_style': 'carto-positron',
    #         'margin': {'r': 10, 't': 30, 'l': 10, 'b': 10},
    #         'width': 1000,
    #         'height': 600,
    #     }
    # )
    fig.update_layout(
        mapbox_style=DEFAULT_MAPBOX_STYLE,
        margin={'autoexpand': True, 'r': 0, 't': 40, 'l': 0, 'b': 0},
        # width=1100, height=700,
        autosize=True,
        # selectdirection='h', ???
        clickmode='event',
        dragmode='pan',
        hoverdistance=1, hovermode='closest',  # hoverlabel=None,
        selectionrevision=False,  # this is crucial !!!
        #showlegend=True,
    )

    # print(fig)

    return dcc.Graph(
        id=FOOTPRINT_MAP_GRAPH_ID,
        figure=fig,
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'scrollZoom': True,
        }
    )


def get_layout():
    airports_df = footprint_data_access.get_iagos_airports(top=10).sort_values('long_name')
    # with open('/home/wolp/tmp/top50_airports.txt', mode='w') as f:
    #     f.writelines([f'{item}\n' for item in stations.short_name])

    def get_form_item(label, input_component):
        form_item = dbc.Row([
            dbc.Label(label, width=4),
            dbc.Col(input_component, width=8),
        ])
        return form_item

    def time_input_field(i):
        placeholder = 'YYYY-MM-DD'
        return dbc.Input(
            id=i,
            type='text',
            debounce=True,
            placeholder=placeholder,
            maxLength=len(placeholder),
            invalid=False,
        )

    airport_selection = dbc.Select(
        id=AIRPORT_SELECT_ID,
        options=[
            {'label': f'{long_name} ({short_name})', 'value': short_name}
            for short_name, long_name in airport_name_by_code.items()
        ],
        value='FRA',
    )

    vertical_layer_radio = dbc.RadioItems(
        id=VERTICAL_LAYER_RADIO_ID,
        options=[
            {'label': 'Lower troposphere (< 3km)', 'value': 'LT'},
            {'label': 'Free troposphere (3km - 8km)', 'value': 'FT'},
            {'label': 'Upper troposphere (> 8km)', 'value': 'UT'},
        ],
        value='LT',
        inline=False
    )

    time_selection = dbc.Select(
        id=TIME_SELECT_ID,
    )
    # period_input = dbc.InputGroup(
    #     [
    #         dbc.InputGroupText('From'),
    #         time_input_field(PERIOD_FROM_INPUT_ID),
    #         dbc.InputGroupText('to'),
    #         time_input_field(PERIOD_TO_INPUT_ID),
    #     ],
    #     # id=interval_input_group_id(aio_id, aio_class),
    #     # className='mb-3',
    # )

    emission_inventory_checklist = dbc.Checklist(
        id=EMISSION_INVENTORY_CHECKLIST_ID,
        options=[
            {'label': 'Biomass burning (GFAS v1.2)', 'value': 'GFAS'},
            {'label': 'Anthropogenic (CEDS v2)', 'value': 'CEDS2'},
        ],
        value=['GFAS', 'CEDS2'],
        inline=False,
    )

    emission_region_selection = dbc.Select(
        id=EMISSION_REGION_SELECT_ID,
        options=[
            {'label': region, 'value': region}
            for region in GEO_REGIONS
        ],
        value='TOTAL',
    )

    options_form = dbc.Form([
        get_form_item('Airport', airport_selection),
        get_form_item('Vertical layer', vertical_layer_radio),
        get_form_item('Time', time_selection),
        get_form_item('CO contribution (emission inventory)', emission_inventory_checklist),
        get_form_item('CO contribution (emission region)', emission_region_selection),
    ])

    footprint_map = get_airports_map(airports_df)

    data_download_button = dbc.Button(
        id=DATA_DOWNLOAD_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        style={'font-weight': 'bold'},
        children='Data download'
    )

    previous_time_button = dbc.Button(
        id=PREVIOUS_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        style={'font-weight': 'bold'},
        children='Previous'
    )
    next_time_button = dbc.Button(
        id=NEXT_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        style={'font-weight': 'bold'},
        children='Next'
    )
    time_navigation_buttons = dbc.Container(dbc.Row(
        [
            dbc.Col(previous_time_button, width=4, align='right'),
            dbc.Col(next_time_button, width=4, align='left'),
        ],
        align='top',
        justify='between',
    ))

    ts_graph = dcc.Graph(
        id=CO_GRAPH_ID,
        figure=go.Figure(),
    )

    layout = html.Div(
        style={'margin': '20px'},
        children=dbc.Container([
            dbc.Row(dbc.Container(id='foo-container')),
            dbc.Row([
                dbc.Col([options_form, data_download_button], width=4),
                dbc.Col([footprint_map, time_navigation_buttons], width=8),
            ]),
            dbc.Row([
                ts_graph,
            ])
        ], fluid=True)
    )

    return layout
