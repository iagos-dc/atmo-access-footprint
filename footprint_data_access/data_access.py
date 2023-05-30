import importlib.resources
import pandas as pd


_iagos_airports = None


def get_iagos_airports(top=None):
    global _iagos_airports
    if _iagos_airports is None:
        ref = importlib.resources.files('footprint_data_access') / 'resources/iagos_airports.json'
        with importlib.resources.as_file(ref) as url:
            _iagos_airports = pd.read_json(url, orient='records')
    if top is not None:
        return _iagos_airports.nlargest(top, 'nprofiles')
    else:
        return _iagos_airports
