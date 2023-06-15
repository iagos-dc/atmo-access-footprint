import pkg_resources
import logging
import functools
import time
import cProfile, pstats, io

import dash


_logger = None
_streamHandler = logging.StreamHandler()


_callback_args_by_time = None


def logger():
    return _logger


def callback_args_by_time():
    if _callback_args_by_time is None:
        raise RuntimeError('_callback_args_by_time is None !!!')
    return _callback_args_by_time


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


def log_callback(log_callback_context=True):
    def _log_callback(func):
        @functools.wraps(func)
        def log_callback_wrapper(*args, **kwargs):
            #args_as_json = [json.dumps(arg) for arg in args]
            #kwargs_as_json = {kw: json.dumps(arg) for kw, arg in kwargs.items()}
            d = {}
            try:
                d = {
                    'module': func.__module__,
                    'name': func.__qualname__,
                    'args': args,
                    'kwargs': kwargs,
                }
                if log_callback_context:
                    from dash import ctx
                    d['ctx'] = (ctx.triggered_id, ctx.triggered_prop_ids)

                import pandas as pd
                timenow = pd.Timestamp.now()
                #while str(timenow) in callback_args_by_time().keys():
                while str(timenow) in callback_args_by_time():
                    timenow += pd.Timedelta(1, 'us')
                callback_args_by_time()[str(timenow)] = d
            except Exception as e:
                try:
                    logger().exception(f'Could not log the request {d}')
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
            d = {
                'module': func.__module__,
                'name': func.__qualname__,
                'args': args,
                'kwargs': kwargs,
            }
            if log_callback_context:
                from dash import ctx
                d['ctx'] = (ctx.triggered_id, ctx.triggered_prop_ids, ctx.inputs_list, ctx.outputs_list, ctx.states_list, ctx.triggered)

            import pandas as pd
            timenow = pd.Timestamp.now()
            #while str(timenow) in callback_args_by_time().keys():
            while str(timenow) in callback_args_by_time():
                timenow += pd.Timedelta(1, 'us')

            try:
                ret_val = func(*args, **kwargs)
                d['ret_val'] = ret_val
                return ret_val
            except Exception as e:
                d['exception'] = str(e)
                raise e
            finally:
                callback_args_by_time()[str(timenow)] = d

        return log_callback_wrapper
    return _log_callback


def log_exception(func):
    @functools.wraps(func)
    def log_exception_wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except dash.exceptions.PreventUpdate:
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
    global _callback_args_by_time
    import diskcache
    _callback_args_by_time = diskcache.Cache(log_filename)


logfile = pkg_resources.resource_filename('log', 'log.txt')
start_logging(log_filename=logfile, logging_level=logging.INFO)
