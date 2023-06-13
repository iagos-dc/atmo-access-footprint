from dash import dcc, Dash
from dash import html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc


from layout import get_app_data_stores, get_layout
import callbacks  # noq


# logos
ATMO_ACCESS_LOGO_FILENAME = 'atmo_access_logo.png'
IAGOS_LOGO_FILENAME = 'iagos_logo.png'


# Begin of definition of routines which constructs components of the dashboard

def get_dashboard_layout(app):
    # logo and application title
    title_and_logo_bar = html.Div(
        style={'display': 'flex', 'justify-content': 'space-between', 'margin-bottom': '0px'},
        children=[
            html.Div(
                children=[
                    html.H4('IAGOS viewer of FLEXPART (Lagrangian model) footprints and modeled SOFT-IO CO contributions', style={'font-weight': 'bold'}),
                    html.H5('tropospheric vertical profiles', style={'font-weight': 'bold'}),
                ],
                style={'text-align': 'center'},
            ),
            html.Div(children=[
                html.A(
                    html.Img(
                        src=app.get_asset_url(ATMO_ACCESS_LOGO_FILENAME),
                        style={'float': 'right', 'height': '80px', 'margin-top': '10px'}
                    ),
                    href="https://www.atmo-access.eu/",
                ),
            ]),
        ]
    )

    app_layout = get_layout(title_and_logo_bar)

    layout = html.Div(
        id='app-container-div',
        style={'margin': '10px', 'padding-bottom': '0px'},
        children=get_app_data_stores() + [app_layout]
    )

    return layout


app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.3.0/font/bootstrap-icons.css',
        #'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
    ],
)

server = app.server

app.layout = get_dashboard_layout(app)

# Launch the Dash application in development mode
if __name__ == "__main__":
    app.run_server(debug=True, host='0.0.0.0', port=8048)
