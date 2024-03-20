from dash import dcc
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
        'width': 1000,
        'height': 600,
        'scale': 2,
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
FOOTPRINT_MAP_CONTAINER_ID = 'footprint_map_container'
CO_GRAPH_ID = 'CO_graph'
CO_GRAPH_CONTAINER_ID = 'CO_graph_container'
PROFILE_GRAPH_ID = 'profile_graph'
PROFILE_GRAPH_CONTAINER_ID = 'profile_graph_container'
SHOW_TOOLTIPS_SWITCH_ID = 'show_tooltips_switch_id'
DATA_DOWNLOAD_POPUP_ID = 'data_download_popup'
ONLY_SIGNIFICANT_REGIONS_CHECKBOX_ID = 'only_significant_regions_checkbox'
ONLY_SIGNIFICANT_REGIONS_PERCENTAGE_ID = 'only_significant_regions_percentage'
RESIDENCE_TIME_SCALE_RADIO_ID = 'residence_time_scale_radio'
RESIDENCE_TIME_CUTOFF_RADIO_ID = 'residence_time_cutoff_radio'

GEO_REGIONS_WITHOUT_TOTAL = ['BONA', 'TENA', 'CEAM', 'NHSA', 'SHSA', 'EURO', 'MIDE', 'NHAF', 'SHAF', 'BOAS', 'CEAS', 'SEAS', 'EQAS', 'AUST']
GEO_REGIONS = ['TOTAL'] + GEO_REGIONS_WITHOUT_TOTAL
COLOR_HEX_BY_GFED4_REGION = {
    'BONA': '#3460ff',
    'TENA': '#ffab00',
    'CEAM': '#fe01fd',
    'NHSA': '#d8b6ff',
    'SHSA': '#956aff',
    'EURO': '#54ffff',
    'MIDE': '#488db1',
    'NHAF': '#547818',
    'SHAF': '#ff547e',
    'BOAS': '#ffff7e',
    'CEAS': '#aa8449',
    'SEAS': '#00d800',
    'EQAS': '#00acff',
    'AUST': '#e5ffbb',
}
COLOR_HEX_BY_EMISSION_INVENTORY = {
    'GFAS': '#ff0000',
    'CEDS2': '#0000ff',
    'ALL': '#9834eb',
    #'ALL': 'rgba(152, 52, 235, 0.3)',
}
FILLPATTERN_SHAPE_BY_EMISSION_INVENTORY = {
    'CEDS2': '/',
    'GFAS': '',
}

DEFAULT_AIRPORT = 'FRA'

_installed_tooltip_ids = set()


def get_installed_tooltip_ids():
    return list(_installed_tooltip_ids)


def _tooltip_target_to_str(target):
    if isinstance(target, dict):
        target_as_str = '_'.join(f'{k}-{v}' for k, v in target.items())
    elif isinstance(target, str):
        target_as_str = target
    else:
        raise TypeError(f'target must be either str or dict; got type(target)={type(target)}')
    return f'tooltip-to-{target_as_str}'


def get_tooltip(tooltip_text, target, **kwargs):
    global _installed_tooltip_ids
    tooltip_kwargs = {
        'placement': 'top-start',
        'style': {'font-size': '0.8em'}
    }
    tooltip_kwargs.update(kwargs)

    tooltip_id = _tooltip_target_to_str(target)
    _installed_tooltip_ids.add(tooltip_id)
    return dbc.Tooltip(
        tooltip_text,
        id=tooltip_id,
        target=target,
        **tooltip_kwargs
    )


def _get_watermark_size(fig):
    if not isinstance(fig, dict):
        fig = fig.to_dict()

    default_size = 75
    ref_height = 500
    ref_width = 1000

    layout = fig.get('layout')
    if layout is None:
        return default_size
    height = layout.get('height')
    if height is not None:
        return default_size * height / ref_height
    width = layout.get('width', ref_width)
    return default_size * width / ref_width


def _get_fig_center(fig):
    if not isinstance(fig, dict):
        fig = fig.to_dict()

    default_center_by_axis = {
        'xaxis': .5,
        'yaxis': .5,
    }
    def_center = (default_center_by_axis['xaxis'], default_center_by_axis['yaxis'])

    layout = fig.get('layout')
    if layout is None:
        return def_center

    def get_axis_domain_center(axis):
        _axis = layout.get(axis)
        if _axis is None:
            return default_center_by_axis[axis]
        return sum(_axis.get('domain', (0, 1))) / 2

    x = get_axis_domain_center('xaxis')
    y = get_axis_domain_center('yaxis')
    return x, y


def add_watermark(fig, textangle=-30, size=None):
    if size is None:
        size = _get_watermark_size(fig)
    #x, y = _get_fig_center(fig)
    x, y = 0.5, 0.5

    annotations = [dict(
        name="watermark",
        text="ATMO-ACCESS",
        textangle=textangle,
        opacity=0.05,
        font=dict(color="black", size=size),
        xref="paper",
        yref="paper",
        #xref='x domain',
        #yref='y domain',
        x=x,
        y=y,
        showarrow=False,
    )]

    fig.update_layout(annotations=annotations)
    return fig



def get_app_tooltips():
    ts_graph_tooltip = get_tooltip(
        html.Div([
            'Use drag-and-drop or the toolbox in the right-top to zoom, pan or download the plot',
            html.Br(),
            'Click on a legend item to hide or show it on the plot',
            html.Br(),
            'Click on any point on the plot to set a footprint and a profile time for the plots below'
        ]),
        CO_GRAPH_CONTAINER_ID,
    )
    profile_graph_tooltip = get_tooltip(
        html.Div([
            'Use drag-and-drop or the toolbox in the right-top to zoom, pan or download the plot',
            html.Br(),
            'Click on a legend item to hide or show it on the plot',
            html.Br(),
            'Double-click on the plot title or a legend item annotation to edit it'
        ]),
        PROFILE_GRAPH_CONTAINER_ID,
    )
    footprint_map_tooltip = get_tooltip(
        'Click on the map to select an airport',
        FOOTPRINT_MAP_CONTAINER_ID,
    )

    time_input_tooltip = get_tooltip(
        html.Div([
            'Click on any point on the plot above to set a footprint and a profile time',
            html.Br(),
            'The current time is indicated on the plot above with the dashed vertical line'
        ]),
        TIME_INPUT_ID,
    )
    prev_time_tooltip = get_tooltip(
        html.Div('Previous time step'),
        PREVIOUS_TIME_BUTTON_ID,
    )
    next_time_tooltip = get_tooltip(
        html.Div('Next time step'),
        NEXT_TIME_BUTTON_ID,
    )
    rew_time_tooltip = get_tooltip(
        html.Div('Jump several time steps back'),
        REWIND_TIME_BUTTON_ID,
    )
    ff_time_tooltip = get_tooltip(
        html.Div('Jump several time steps ahead'),
        FASTFORWARD_TIME_BUTTON_ID,
    )

    return [
        ts_graph_tooltip, profile_graph_tooltip, footprint_map_tooltip,
        time_input_tooltip, prev_time_tooltip, next_time_tooltip, rew_time_tooltip, ff_time_tooltip,
    ]


def get_app_data_stores():
    return [
        dcc.Store(id=CURRENT_PROFILE_IDX_BY_AIRPORT_STORE_ID, data={}, storage_type='session')
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
        zoom=1,
        center={'lon': 30, 'lat': 30},
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
        margin={'autoexpand': True, 'r': 0, 't': 60, 'l': 0, 'b': 0},
        height=650,
        autosize=True,
        # autosize=False,
        # selectdirection='h', ???
        clickmode='event',
        dragmode='pan',
        hoverdistance=1, hovermode='closest',  # hoverlabel=None,
        selectionrevision=False,  # this is crucial !!!
        #showlegend=True,
        xaxis={'visible': False},
        yaxis={'visible': False},
    )

    # print(fig)

    return dcc.Graph(
        id=FOOTPRINT_MAP_GRAPH_ID,
        figure=add_watermark(fig),
        config=GRAPH_MAP_CONFIG,
    )


def get_layout(title_bar, app):
    def get_form_item(label, input_component):
        form_item = dbc.Row([
            dbc.Label(label, width=4),
            dbc.Col(input_component, width=8),
        ])
        return form_item

    airport_selection = dbc.Select(
        id=AIRPORT_SELECT_ID,
        options=[
            {'label': f'{long_name} ({short_name}) - {footprint_data_access.nprofiles_by_airport[short_name]} profiles', 'value': short_name}
            for short_name, long_name in footprint_data_access.airport_name_by_code.items()
        ],
        value=DEFAULT_AIRPORT,
        persistence=True,
        persistence_type='session',
        size='lg',
    )

    vertical_layer_radio = dbc.RadioItems(
        id=VERTICAL_LAYER_RADIO_ID,
        # options=[
        #     {'label': 'Lower troposphere (< 3km)', 'value': 'LT'},
        #     {'label': 'Free troposphere (3km - 8km)', 'value': 'FT'},
        #     {'label': 'Upper troposphere (> 8km)', 'value': 'UT'},
        # ],
        options=[
            {'label': 'LT (< 3km)', 'value': 'LT'},
            {'label': 'FT (3km - 8km)', 'value': 'FT'},
            {'label': 'UT (> 8km)', 'value': 'UT'},
        ],
        value='LT',
        inline=True,
        persistence=True,
        persistence_type='session',
    )

    _placeholder = 'YYYY-MM-DD HH:MM'
    time_selection = dbc.Input(
        id=TIME_INPUT_ID,
        type='text',
        debounce=True,
        placeholder=_placeholder,
        maxlength=len(_placeholder),
        invalid=False,
        readonly=True,
        # persistence=True,
        # persistence_type='session',
        style={'text-align': 'center'},
        size='lg',
    )

    emission_inventory_checklist = dbc.Checklist(
        id=EMISSION_INVENTORY_CHECKLIST_ID,
        options=[
            {'label': 'Biomass burning (GFAS v1.2)', 'value': 'GFAS'},
            {'label': 'Anthropogenic (CEDS v2; until 2019)', 'value': 'CEDS2'},
        ],
        value=['GFAS', 'CEDS2'],
        inline=False,
        persistence=True,
        persistence_type='session',
    )

    emission_region_selection = dbc.Select(
        id=EMISSION_REGION_SELECT_ID,
        options=[
            {'label': region, 'value': region}
            for region in GEO_REGIONS
        ],
        value='TOTAL',
        persistence=True,
        persistence_type='session',
        size='lg',
    )

    show_tooltips_switch = dbc.Switch(
        id=SHOW_TOOLTIPS_SWITCH_ID,
        label='Show tooltips',
        value=True,
        persistence=True,
        persistence_type='local',
    )

    data_download_button = dbc.Button(
        id=DATA_DOWNLOAD_BUTTON_ID,
        disabled=True,
        n_clicks=0,
        color='primary', type='submit',
        style={'font-weight': 'bold'},
        children='Data download',
        # size='lg',
    )

    rewind_time_button = dbc.Button(
        id=REWIND_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-double-left'),
    )
    previous_time_button = dbc.Button(
        id=PREVIOUS_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-left'),
    )
    next_time_button = dbc.Button(
        id=NEXT_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-right'),
    )
    fastforward_time_button = dbc.Button(
        id=FASTFORWARD_TIME_BUTTON_ID,
        n_clicks=0,
        color='primary', type='submit',
        children=html.Div(className='bi bi-chevron-double-right'),
    )

    # time_selection_group = dbc.Row(
    #     [
    #         dbc.Label('Time', width=4),
    #         # TODO: do it in one Div (see how it reacts to window resize)
    #         dbc.Col(rewind_time_button, width='auto'),
    #         dbc.Col(previous_time_button, width='auto'),
    #         dbc.Col(time_selection, width='auto'),
    #         dbc.Col(next_time_button, width='auto'),
    #         dbc.Col(fastforward_time_button, width='auto'),
    #     ],
    #     justify='between',
    #     class_name='g-0',  # no-gutters
    # )

    options_form = dbc.Form(
        [
            get_form_item('Airport', airport_selection),
            get_form_item('Vertical layer', vertical_layer_radio),
            # time_selection_group,
            get_form_item(html.Div(['CO contribution', html.Br(), '(emission inventory)']), emission_inventory_checklist),
            get_form_item(html.Div(['CO contribution', html.Br(), '(emission region)']), emission_region_selection),
            dbc.Row(
                html.Img(
                    src=app.get_asset_url('GFED-regions.png'),
                    style={'margin-bottom': '24px', 'margin-top': '24px'},
                    # style={'float': 'right', 'height': '80px', 'margin-top': '10px'},
                ),
            ),
        ],
    )

    footprint_map = get_airports_map(footprint_data_access.airports_df)

    graph_config = dict(GRAPH_CONFIG)
    graph_config.update({
        'toImageButtonOptions': {
            'filename': 'CO-time-series',
            'format': 'png',
            'height': 500,
            'width': 1000,
            'scale': 2,
        },
    })
    ts_graph = dcc.Graph(
        id=CO_GRAPH_ID,
        figure=go.Figure(),
        config=graph_config,
        # style={'width': '100%', 'height': '100%'}
    )

    # graph_config = dict(NON_INTERACTIVE_GRAPH_CONFIG)
    graph_config = dict(GRAPH_CONFIG)
    graph_config.update({
        'toImageButtonOptions': {
            'filename': 'CO-profile',
            'format': 'png',
            'height': 700,
            'width': 500,
            'scale': 2,
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
        html.Div([
            'Adapted from Sauvage, B., Fontaine, A., Eckhardt, S., Auby, A., Boulanger, D., Petetin, H., Paugam, R., Athier, '
            'G., Cousin, J.-M., Darras, S., Nédélec, P., Stohl, A., Turquety, S., Cammas, J.-P., and Thouret, V.: '
            'Source attribution using FLEXPART and carbon monoxide emission inventories: SOFT-IO version 1.0, '
            'Atmos. Chem. Phys., 17, 15271–15292, ',
            html.A('https://doi.org/10.5194/acp-17-15271-2017', href='https://doi.org/10.5194/acp-17-15271-2017', target='_blank'),
            ', 2017.'
        ]),
        html.Br(),
        html.Div([
            'The calculations were performed using NUWA - the computational cluster of ',
            html.A('Laboratoire d\'Aérologie', href='https://www.aero.obs-mip.fr/', target='_blank'),
            ' in Toulouse, France.'
        ]),
    ]

    time_selection_group = dbc.InputGroup(
        [
            dbc.InputGroupText('Time'),
            rewind_time_button,
            previous_time_button,
            time_selection,
            next_time_button,
            fastforward_time_button,
        ],
        size='lg',
    )
    time_control = dbc.Row(dbc.Col(time_selection_group, width='auto'), justify='left')

    softio_cutoff_group = dbc.InputGroup(
        [
            dbc.InputGroupText([
                dbc.Checkbox(
                    id=ONLY_SIGNIFICANT_REGIONS_CHECKBOX_ID,
                    value=True,
                    persistence=True,
                    persistence_type='session',
                ),
                'Show only regions with > ',
            ]),
            dbc.Input(
                id=ONLY_SIGNIFICANT_REGIONS_PERCENTAGE_ID,
                type='number',
                maxlength=3,
                min=0, max=100, value=1,
                persistence=True, persistence_type='session',
                debounce=False,
                size='sm',
            ),
            dbc.InputGroupText([
                '% of the total contribution',
            ]),
        ],
        size='lg',
    )
    softio_cutoff_controller = dbc.Row(dbc.Col(softio_cutoff_group, width='auto'), justify='left')

    residence_time_scale_group = dbc.InputGroup(
        [
            dbc.InputGroupText([
                'Scale for the residence time: ',
                dbc.RadioItems(
                    id=RESIDENCE_TIME_SCALE_RADIO_ID,
                    options=[
                        {'label': 'linear', 'value': 'lin'},
                        {'label': 'power (0.5)', 'value': 'sqrt'},
                        {'label': 'log', 'value': 'log'},
                    ],
                    value='sqrt',
                    inline=True,
                    persistence=True,
                    persistence_type='session',
                ),
            ]),
        ],
        size='lg',
    )
    residence_time_cutoff_group = dbc.InputGroup(
        [
            dbc.InputGroupText([
                'Cut-off residence time values smaller than ',
                dbc.RadioItems(
                    id=RESIDENCE_TIME_CUTOFF_RADIO_ID,
                    options=[
                        {'label': '0.03 %', 'value': 3e-4},
                        {'label': '0.1 %', 'value': 1e-3},
                        {'label': '0.3 %', 'value': 3e-3},
                        {'label': '1 %', 'value': 1e-2},
                        {'label': '3 %', 'value': 3e-2},
                    ],
                    value=3e-3,
                    inline=True,
                    persistence=True,
                    persistence_type='session',
                ),
                ' of max',
            ]),
        ],
        size='lg',
    )
    residence_time_scale_controller = dbc.Row(
        [
            dbc.Col(residence_time_scale_group, width='auto'),
            dbc.Col(residence_time_cutoff_group, width='auto'),
        ],
        justify='between'
    )

    tooltips = get_app_tooltips()

    layout_body = dbc.Container(
        [
            dbc.Row([
                dbc.Col(
                    dbc.Card([
                        dbc.CardBody(options_form),
                        dbc.CardFooter(dbc.Row(
                            dbc.Col(show_tooltips_switch, width='auto'),
                            justify='between'
                        ))
                    ]),
                    width=4
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardBody(html.Div(ts_graph, id=CO_GRAPH_CONTAINER_ID)),
                                # for some reason the tooltip to dcc.Graphs must point to Div's
                                # containing the graphs to work correctly.
                                # Otherwise, tooltips do not show after the page refresh
                            dbc.CardFooter(dbc.Row(
                                [
                                    dbc.Col(time_control, width='auto'),
                                    dbc.Col(data_download_button, width='auto'),
                                ],
                                justify='between'
                            )),
                        ],
                    ),
                    width=8,
                ),
            ]),
            dbc.Row([
                dbc.Col(
                    dbc.Card([
                        dbc.CardBody(html.Div(profile_graph, id=PROFILE_GRAPH_CONTAINER_ID)),
                        dbc.CardFooter(softio_cutoff_controller),
                    ]),
                    width=4
                ),
                dbc.Col(
                    dbc.Card([
                        dbc.CardBody(html.Div(footprint_map, id=FOOTPRINT_MAP_CONTAINER_ID)),
                        dbc.CardFooter(residence_time_scale_controller),
                    ]),
                    width=8
                ),
            ]),
            *tooltips,
        ],
        fluid=True,
    )

    layout = dbc.Card([
        dbc.CardHeader(title_bar),
        dbc.CardBody(layout_body),
        dbc.CardHeader(footer)
    ])

    data_download_popup = html.Div(id=DATA_DOWNLOAD_POPUP_ID)

    return html.Div([layout, data_download_popup])
