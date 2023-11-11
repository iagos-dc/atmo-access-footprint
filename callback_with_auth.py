from dash import callback
from auth import callback_with_auth_decorator


callback_with_auth = callback_with_auth_decorator(callback)
