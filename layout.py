from dash import dcc, Dash
from dash import html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


CURRENT_TIME_BY_AIRPORT_STORE_ID = 'current_time_by_airport_store'

AIRPORT_SELECT_ID = 'airport_select'
VERTICAL_LAYER_RADIO_ID = 'vertical_layer_radio'
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


def get_app_data_stores():
    return [
        dcc.Store(id=CURRENT_TIME_BY_AIRPORT_STORE_ID, data={})
    ]


def get_layout():
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
            #{'label': 'Frankfurt (FRA)', 'value': 'FRA'},
            {'label': 'Paris (CDG)', 'value': 'CDG'},
            {'label': 'Munich (MUC)', 'value': 'MUC'},
            {'label': 'Chicago (ORD)', 'value': 'ORD'},
        ],
        value='CDG',
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

    period_input = dbc.InputGroup(
        [
            dbc.InputGroupText('From'),
            time_input_field(PERIOD_FROM_INPUT_ID),
            dbc.InputGroupText('to'),
            time_input_field(PERIOD_TO_INPUT_ID),
        ],
        # id=interval_input_group_id(aio_id, aio_class),
        # className='mb-3',
    )

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
        get_form_item('Period', period_input),
        get_form_item('CO contribution (emission inventory)', emission_inventory_checklist),
        get_form_item('CO contribution (emission region)', emission_region_selection),
    ])

    footprint_map_fig = go.Figure(
        data=go.Scattermapbox(),
        layout={
            #'mapbox_style': 'open-street-map',
            'mapbox_style': 'carto-positron',
            'margin': {'r': 10, 't': 30, 'l': 10, 'b': 10},
            'width': 1000,
            'height': 600,
        }
    )
    footprint_map = dcc.Graph(
        id=FOOTPRINT_MAP_GRAPH_ID,
        figure=footprint_map_fig,
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'scrollZoom': True,
        }
    )

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
