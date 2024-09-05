import functools
import warnings
from dash import html, Output, no_update, ctx
from dash.exceptions import DashException
import dash_bootstrap_components as dbc
from log import dump_exception_to_log
from dash import callback


ALERT_POPUP_ID = 'alert_popup'


class AppException(Exception):
    pass


class EmptyFigureException(AppException):
    pass


class AppWarning(UserWarning):
    pass


alert_popups = []


def get_alert_popup(errors_msgs, warnings_msgs, modal_id):
    msgs = []
    for warning_msgs in warnings_msgs:
        msgs.append('Warning: ' + '; '.join(warning_msgs))
    for error_msgs in errors_msgs:
        msgs.append('Error: ' + '; '.join(error_msgs))
    if len(msgs) == 0:
        return no_update

    if len(msgs) > 1:
        msg = [msgs[0]] + sum(([html.Br(), _msg] for _msg in msgs[1:]), start=[])
    else:
        msg = msgs[0]

    title = []
    if len(warnings_msgs) == 1:
        title.append('warning')
    elif len(warnings_msgs) > 1:
        title.append(f'{len(warnings_msgs)} warnings')
    if len(errors_msgs) == 1:
        title.append('error')
    elif len(errors_msgs) > 1:
        title.append(f'{len(errors_msgs)} errors')
    title = ' and '.join(title).capitalize()

    popup = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle(title)),
            dbc.ModalBody(children=msg),
        ],
        id=modal_id,
        size='lg',
        is_open=True,
    )
    return popup


def handle_exception(callback_decorator, *default_outputs):
    def callback_decorator_with_exception_handler(*args, **kwargs):
        alert_popup_id = f'{ALERT_POPUP_ID}-{len(alert_popups) + 1}'
        # print(alert_popup_id)
        alert_popups.append(html.Div(id=alert_popup_id))

        no_outputs = len([arg for arg in args if isinstance(arg, Output)])
        no_default_outputs = len(default_outputs)
        if no_default_outputs > no_outputs:
            raise ValueError(f'len(default_outputs)={no_default_outputs} must be <= no_outputs={no_outputs}')

        # set the extra error popup output as the last output;
        # this is important if a callback relies on the indices of the outputs,
        # cf. utils/graph_with_horizontal_selection_AIO.py/update_from_and_to_input_values (line ca. 107)
        new_args = args[:no_outputs] + (Output(alert_popup_id, 'children'), ) + args[no_outputs:]

        def callback_func_transform(callback_func):
            @functools.wraps(callback_func)
            def callback_func_with_exception_handling(*callback_args):
                error_msgs = None
                with warnings.catch_warnings(record=True) as warnings_list:
                    # show AppWarning only
                    warnings.resetwarnings()
                    warnings.simplefilter('ignore', category=Warning)
                    warnings.simplefilter('always', category=AppWarning)

                    try:
                        callback_result = callback_func(*callback_args)
                    except DashException:
                        # Dash exceptions (e.g. PreventUpdate) are keep as is
                        raise
                    except AppException as e:
                        error_msgs = e.args
                        dump_exception_to_log(e, func=callback_func, args=callback_args)
                    except Exception as e:
                        error_msgs = ('Internal application error. Please try another action and/or choose another dataset(s).', )
                        dump_exception_to_log(e, func=callback_func, args=callback_args)

                warnings_msgs = [warn.message.args for warn in warnings_list]
                if error_msgs is None:
                    if no_outputs == 1:
                        callback_result = (callback_result,)
                    elif no_outputs == 0:
                        callback_result = ()
                    alert_popup = get_alert_popup([], warnings_msgs, f'{alert_popup_id}-modal')
                    callback_func_with_exception_handling_result = callback_result + (alert_popup, )
                else:
                    outputs = default_outputs + (no_update, ) * (no_outputs - no_default_outputs)
                    alert_popup = get_alert_popup([error_msgs], warnings_msgs, f'{alert_popup_id}-modal')
                    callback_func_with_exception_handling_result = outputs + (alert_popup, )
                return callback_func_with_exception_handling_result
            return callback_decorator(*new_args, **kwargs)(callback_func_with_exception_handling)

        return callback_func_transform
    return callback_decorator_with_exception_handler


callback_with_exc_handling = handle_exception(callback)
