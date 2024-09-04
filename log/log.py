import logging
import functools
import time
import cProfile
import pstats
import io

import pandas as pd
import dash

import config
try:
    from auth import get_request_metadata
except ImportError as e:
    logging.exception('Cound not find auth module; requests metadata will contain time only', exc_info=e)
    def get_request_metadata():
        return pd.Timestamp.now(tz='UTC')


_logger = None
_streamHandler = logging.StreamHandler()


_requests_deque = None


def logger():
    return _logger


def get_requests_deque():
    if _requests_deque is None:
        raise RuntimeError('_requests_deque is None !!!')
    return _requests_deque


def log_args(func):
    @functools.wraps(func)
    def log_args_wrapper(*args, **kwargs):
        # args_str = ', '.join(f'{arg}' for arg in args)
        # kwargs_str = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
        # params_str = ', '.join([s for s in (args_str, kwargs_str) if s])
        log_str_lines = [f'{func.__module__}.{func.__qualname__}']
        for arg in args:
            log_str_lines.append(f'  {arg}')
        for k, v in kwargs.items():
            log_str_lines.append(f'  {k}={v}')
        logger().info('\n'.join(log_str_lines))

        ret = func(*args, **kwargs)

        log_str_lines.append(f'result: {ret}')
        logger().info('\n'.join(log_str_lines))

        return ret
    return log_args_wrapper


def log_callback(log_callback_context=True, comment_func=None):
    """
    Decorator of a Dash callback which makes the callback to log its call arguments, http request context, etc. into
    a persistent diskcache.Deque _requests_deque. The log entry is a dictionary:
     {
       'user_email' -> user_email (only if authentication in place),
       'time' -> UTC_time_of_the_call,
       'ip_address' -> ip_address (only if authentication in place),
       'module' -> callback_module_name,
       'name' -> callback_function_name,
       'args' -> callback_call_args,
       'kwargs' -> callback_call_kwargs,
       'ctx' -> dash_trigger (if log_callback_context is True; see below),
       'comment' -> comment_str (if comment_func is not None)
     }
    :param log_callback_context: bool; if True, log {'ctx': (dash.ctx.triggered_id, dash.ctx.triggered_prop_ids)}
    :param comment_func: a callable or None; a callable should take the same arguments as the callback and produce
    a string with a description of the callback call
    :return: a callable which transforms a callback function into a callback with logging
    """
    def _log_callback(func):
        @functools.wraps(func)
        def log_callback_wrapper(*args, **kwargs):
            #args_as_json = [json.dumps(arg) for arg in args]
            #kwargs_as_json = {kw: json.dumps(arg) for kw, arg in kwargs.items()}
            request_metadata = {}
            try:
                request_metadata = get_request_metadata()
                request_metadata.update({
                    'module': func.__module__,
                    'name': func.__qualname__,
                    'args': args,
                    'kwargs': kwargs,
                })
                if log_callback_context:
                    from dash import ctx
                    request_metadata['ctx'] = (ctx.triggered_id, ctx.triggered_prop_ids)
                if comment_func is not None:
                    request_metadata['comment'] = comment_func(*args, **kwargs)

                get_requests_deque().append(request_metadata)
            except Exception as e:
                try:
                    logger().exception(f'Could not log the request {request_metadata}', exc_info=e)
                except Exception:
                    pass
            return func(*args, **kwargs)
        return log_callback_wrapper
    return _log_callback


def print_callback(log_callback_context=True):
    def _log_callback(func):
        @functools.wraps(func)
        def log_callback_wrapper(*args, **kwargs):
            #args_as_json = [json.dumps(arg) for arg in args]
            #kwargs_as_json = {kw: json.dumps(arg) for kw, arg in kwargs.items()}
            d = {
                'module': func.__module__,
                'name': func.__qualname__,
                'args': args,
                'kwargs': kwargs,
            }
            if log_callback_context:
                from dash import ctx
                d['ctx'] = (ctx.triggered_id, ctx.triggered_prop_ids)

            # print(d)

            return func(*args, **kwargs)
        return log_callback_wrapper
    return _log_callback


def log_callback_with_ret_value(log_callback_context=True):
    def _log_callback(func):
        @functools.wraps(func)
        def log_callback_wrapper(*args, **kwargs):
            #args_as_json = [json.dumps(arg) for arg in args]
            #kwargs_as_json = {kw: json.dumps(arg) for kw, arg in kwargs.items()}
            request_metadata = {}
            try:
                request_metadata = get_request_metadata()
                request_metadata.update({
                    'module': func.__module__,
                    'name': func.__qualname__,
                    'args': args,
                    'kwargs': kwargs,
                })
                if log_callback_context:
                    from dash import ctx
                    request_metadata['ctx'] = (ctx.triggered_id, ctx.triggered_prop_ids, ctx.inputs_list, ctx.outputs_list, ctx.states_list, ctx.triggered)
            except Exception as e:
                try:
                    logger().exception(f'Could not log the request {request_metadata}', exc_info=e)
                except Exception:
                    pass

            try:
                ret_val = func(*args, **kwargs)
                request_metadata['ret_val'] = ret_val
                return ret_val
            except Exception as e:
                request_metadata['exception'] = str(e)
                raise e
            finally:
                get_requests_deque().append(request_metadata)

        return log_callback_wrapper
    return _log_callback


def dump_exception_to_log(exc, func=None, args=None, kwargs=None):
    if func is not None:
        func_module = func.__module__
        func_qualname = func.__qualname__
    else:
        func_module = '???'
        func_qualname = '???'
    logger().exception(
        f'exception in {func_module}.{func_qualname}\n'
        f'args={args}\n'
        f'kwargs={kwargs}',
        exc_info=exc
    )


def log_exception(func):
    @functools.wraps(func)
    def log_exception_wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except dash.exceptions.DashException:
            raise
        except Exception as e:
            logger().exception(
                f'ooOOoo unhandled exception in {func.__module__}.{func.__qualname__} ooOOoo\n'
                f'args={args}\n'
                f'kwargs={kwargs}',
                exc_info=e
            )
            raise
        return result
    return log_exception_wrapper


def log_exectime(func):
    @functools.wraps(func)
    def log_exectime_wrapper(*args, **kwargs):
        logger().info(f'{func.__module__}.{func.__name__} started')
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger().info(f'{func.__module__}.{func.__name__} finished in {end - start:.3e} sec')
        return result
    return log_exectime_wrapper


def log_profiler_info(sortby='cumulative'):
    def _log_profiler_info(func):
        @functools.wraps(func)
        def log_profiler_info_wrapper(*args, **kwargs):
            prof = cProfile.Profile()
            result = prof.runcall(func, *args, **kwargs)
            s = io.StringIO()
            ps = pstats.Stats(prof, stream=s).sort_stats(sortby)
            ps.print_stats()
            logger().info(f'{func.__module__}.{func.__name__} profiler info: {s.getvalue()}')
            return result
        return log_profiler_info_wrapper
    return _log_profiler_info


def start_logging(log_filename=None, logging_level=logging.WARNING):
    global _logger
    _logger = logging.getLogger(__name__)

    current_logging_level = logger().getEffectiveLevel()
    if not current_logging_level or current_logging_level > logging_level:
        logger().setLevel(logging_level)

    if not log_filename:
        handler = _streamHandler
    else:
        logger().removeHandler(_streamHandler)
        handler = logging.FileHandler(str(log_filename))

    handler.setLevel(logging_level)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - in %(pathname)s:%(funcName)s (line %(lineno)d): %(message)s')
    handler.setFormatter(formatter)
    logger().addHandler(handler)


def start_logging_callbacks(log_filename):
    global _requests_deque
    import diskcache
    _requests_deque = diskcache.Deque(directory=log_filename)


start_logging(log_filename=config.APP_LOGS, logging_level=logging.INFO)
