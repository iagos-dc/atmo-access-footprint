from dash import dcc, Dash
from dash import html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc


def get_dashboard_layout(app):
    return html.Div(children='Hello from ATMO-ACCESS footprint service!')


app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
    ],
)

server = app.server

app.layout = get_dashboard_layout(app)


# Begin of callback definitions and their helper routines.
# See: https://dash.plotly.com/basic-callbacks
# for a basic tutorial and
# https://dash.plotly.com/  -->  Dash Callback in left menu
# for more detailed documentation


# Launch the Dash application in development mode
if __name__ == "__main__":
    app.run_server(debug=True, host='0.0.0.0', port=8048)
