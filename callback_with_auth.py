from dash import callback
from auth import auth


_callback_with_auth_decorator = auth.get_callback_with_auth_decorator()

callback_with_auth = _callback_with_auth_decorator(callback)
