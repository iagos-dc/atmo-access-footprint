from dash import dcc, Dash
from dash import html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px

import footprint_data_access


GRAPH_CONFIG = {
    'autosizable': True,
    'displayModeBar': True,
    'doubleClick': 'autosize',
    # 'fillFrame': True,
    #'editSelection': True,
    #'editable': False,
    'modeBarButtons': [['zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d'], ['autoScale2d'], ['toImage']],
    'edits': {
        'titleText': True,
        'axisTitleText': False,
        'legendText': True,
        'colorbarTitleText': True,
    },
    'showAxisDragHandles': True,
    'scrollZoom': True,
    'showAxisRangeEntryBoxes': True,
    'showTips': True,
    'displaylogo': False,
    'responsive': True,
}  # for more see: help(dcc.Graph)


GRAPH_MAP_CONFIG = {
    'modeBarButtons': [['zoomInMapbox', 'zoomOutMapbox'], ['resetViewMapbox'], ['toImage']],
    'displayModeBar': True,
    'displaylogo': False,
    'scrollZoom': True,
    'edits': {
        'titleText': True,
        'axisTitleText': False,
        'legendText': True,
        'colorbarTitleText': True,
    },
    'toImageButtonOptions': {
        'filename': 'footprint',
        'format': 'png',
        'width': 1200,
        'height': 800,
    },
}


NON_INTERACTIVE_GRAPH_CONFIG = {
    'autosizable': False,
    'displayModeBar': True,
    'editable': False,
    'modeBarButtons': [['toImage']],
    'showAxisDragHandles': False,
    'showAxisRangeEntryBoxes': False,
    'showTips': True,
    'displaylogo': False,
    'responsive': True,
}  # for more see: help(dcc.Graph)


IAGOS_COLOR_HEX = '#456096'
IAGOS_AIRPORT_SIZE = 8
MAPBOX_STYLES = {
    'open-street-map': 'open street map',
    'carto-positron': 'carto positron',
}
DEFAULT_MAPBOX_STYLE = 'carto-positron'


CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID = 'current_profile_idx_by_airport_store'

AIRPORT_SELECT_ID = 'airport_select'
VERTICAL_LAYER_RADIO_ID = 'vertical_layer_radio'
TIME_INPUT_ID = 'time_input'
PERIOD_FROM_INPUT_ID = 'period_from_input'
PERIOD_TO_INPUT_ID = 'period_to_input'
EMISSION_INVENTORY_CHECKLIST_ID = 'emission_inventory_checklist'
EMISSION_REGION_SELECT_ID = 'emission_region_select'
DATA_DOWNLOAD_BUTTON_ID = 'data_download_button'
PREVIOUS_TIME_BUTTON_ID = 'previous_time_button'
NEXT_TIME_BUTTON_ID = 'next_time_button'
REWIND_TIME_BUTTON_ID = 'rewind_time_button'
FASTFORWARD_TIME_BUTTON_ID = 'fastforward_time_button'
FOOTPRINT_MAP_GRAPH_ID = 'footprint_map_graph'
CO_GRAPH_ID = 'CO_graph'
PROFILE_GRAPH_ID = 'profile_graph'

GEO_REGIONS = ['BONA', 'TENA', 'CEAM', 'NHSA', 'SHSA', 'EURO', 'MIDE', 'NHAF', 'SHAF', 'BOAS', 'CEAS', 'SEAS', 'EQAS', 'AUST', 'TOTAL']

DEFAULT_AIRPORT = 'FRA'


airports_df = footprint_data_access.get_iagos_airports(top=None).sort_values('long_name')
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
        height=600,
        autosize=True,
        # autosize=False,
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
        config=GRAPH_MAP_CONFIG,
    )


def get_layout(title_bar):
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
        value=DEFAULT_AIRPORT,
    )

    vertical_layer_radio = dbc.RadioItems(
        id=VERTICAL_LAYER_RADIO_ID,
        options=[
            {'label': 'Lower troposphere (< 3km)', 'value': 'LT'},
            {'label': 'Free troposphere (3km - 8km)', 'value': 'FT'},
            {'label': 'Upper troposphere (> 8km)', 'value': 'UT'},
        ],
        # options=[
        #     {'label': 'LT (< 3km)', 'value': 'LT'},
        #     {'label': 'FT (3km - 8km)', 'value': 'FT'},
        #     {'label': 'UT (> 8km)', 'value': 'UT'},
        # ],
        value='LT',
        inline=False,
        # inline=True,
    )

    _placeholder = 'YYYY-MM-DD HH:MM'
    time_selection = dbc.Input(
        id=TIME_INPUT_ID,
        type='text',
        debounce=True,
        placeholder=_placeholder,
        maxLength=len(_placeholder),
        invalid=False,
        style={'text-align': 'center'},
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

    data_download_button = dbc.Button(
        id=DATA_DOWNLOAD_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        style={'font-weight': 'bold'},
        children='Data download'
    )

    rewind_time_button = dbc.Button(
        id=REWIND_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-double-left')
    )
    previous_time_button = dbc.Button(
        id=PREVIOUS_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-left')
    )
    next_time_button = dbc.Button(
        id=NEXT_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-right')
    )
    fastforward_time_button = dbc.Button(
        id=FASTFORWARD_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-double-right')
    )

    options_form = dbc.Form(
        [
            get_form_item('Airport', airport_selection),
            get_form_item('Vertical layer', vertical_layer_radio),
            dbc.Row(
                [
                    dbc.Label('Time', width=4),
                    # TODO: do it in one Div (see how it reacts to window resize)
                    dbc.Col(rewind_time_button, width='auto'),
                    dbc.Col(previous_time_button, width='auto'),
                    dbc.Col(time_selection, width='auto'),
                    dbc.Col(next_time_button, width='auto'),
                    dbc.Col(fastforward_time_button, width='auto'),
                ],
                justify='between',
                class_name='g-0',  # no-gutters
            ),
            get_form_item(html.Div(['CO contribution', html.Br(), '(emission inventory)']), emission_inventory_checklist),
            get_form_item(html.Div(['CO contribution', html.Br(), '(emission region)']), emission_region_selection),
            dbc.Row(dbc.Col(data_download_button, width='auto'), justify='center'),
        ],
    )

    footprint_map = get_airports_map(airports_df)

    graph_config = dict(GRAPH_CONFIG)
    graph_config.update({
        'toImageButtonOptions': {
            'filename': 'CO-time-series',
            'format': 'svg',
            'height': 600,
            'width': 1200,
            # 'scale': 2,
        },
    })
    ts_graph = dcc.Graph(
        id=CO_GRAPH_ID,
        figure=go.Figure(),
        config=graph_config,
        # style={'width': '100%', 'height': '100%'}
    )

    graph_config = dict(NON_INTERACTIVE_GRAPH_CONFIG)
    graph_config.update({
        'toImageButtonOptions': {
            'filename': 'CO-profile',
            'format': 'svg',
            'height': 800,
            'width': 600,
            # 'scale': 2,
        },
    })
    profile_graph = dcc.Graph(
        id=PROFILE_GRAPH_ID,
        figure=go.Figure(),
        config=graph_config,
        # style={'width': '100%', 'height': '100%'}
    )

    footer = [
        html.Div('Developed by P. Wolff (pawel.wolff@aero.obs-mip.fr) (CNRS) under ATMO-ACCESS, EU grant agreement No 101008004.'),
        html.Br(),
        html.Div('Adapted from Sauvage, B., Fontaine, A., Eckhardt, S., Auby, A., Boulanger, D., Petetin, H., Paugam, R., Athier, '
        'G., Cousin, J.-M., Darras, S., Nédélec, P., Stohl, A., Turquety, S., Cammas, J.-P., and Thouret, V.: '
        'Source attribution using FLEXPART and carbon monoxide emission inventories: SOFT-IO version 1.0, '
        'Atmos. Chem. Phys., 17, 15271–15292, https://doi.org/10.5194/acp-17-15271-2017, 2017.'),
        html.Br(),
        html.Div('The calculations were performed using NUWA - the computational cluster of Laboratoire d\'Aérologie in Toulouse, France'),
    ]

    layout_body = dbc.Container(
        [
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody(options_form)), width=4),
                dbc.Col(dbc.Card(dbc.CardBody(ts_graph)), width=8),
            ]),
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody(profile_graph)), width=4),
                dbc.Col(dbc.Card(dbc.CardBody(footprint_map)), width=8),
                # dbc.Col(footprint_map, width=8),
            ])
        ],
        fluid=True,
    )

    layout = dbc.Card([
        dbc.CardHeader(title_bar),
        dbc.CardBody(layout_body),
        dbc.CardHeader(footer)
    ])

    return layout
