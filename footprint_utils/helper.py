import numpy as np
import pandas as pd
import numba


@numba.njit
def _insert_nan(a, na, nan_idx, ni, b):
    """
    For each index i in the array b, find the last index j in the array a, such that a[j] <= b[i];
    if it does not exist, j == -1.
    :param a: numpy 1d-array
    :param nan_idx: numpy 1d-array
    :return: numpy array of int8 of size of the array b
    """
    j = 0
    k = 0
    for i in range(na):
        b[j] = a[i]
        j += 1
        if k < ni and nan_idx[k] == i:
            j += 1
            k += 1
    return b


@numba.njit
def _insert_nan2(a, na, nan_idx, ni, idx):
    """
    For each index i in the array b, find the last index j in the array a, such that a[j] <= b[i];
    if it does not exist, j == -1.
    :param a: numpy 1d-array
    :param nan_idx: numpy 1d-array
    :return: numpy array of int8 of size of the array b
    """
    j = 0
    k = 0
    for i in range(na):
        idx[i] = j
        j += 1
        if k < ni and nan_idx[k] == i:
            j += 1
            k += 1
    return idx


def insert_nan(a_, nan_idx, fill_value=None):
    a = a_.values if isinstance(a_, pd.Series) else a_
    ni = len(nan_idx)
    if ni == 0:
        return a

    dtype_kind = a.dtype.kind
    if fill_value is None:
        if dtype_kind == 'f':
            fill_value = np.nan
        elif dtype_kind == 'M':
            fill_value = np.datetime64('nat')
        elif dtype_kind == 'm':
            fill_value = np.timedelta64('nat')
        elif dtype_kind == 'i':
            fill_value = 0
        else:
            raise ValueError(f'a has unsupported dtype kind={dtype_kind}; dtype={a.dtype}')

    if dtype_kind == 'f':
        a = a.astype('f8')

    na = len(a)
    b = np.full(shape=na + ni, fill_value=fill_value, dtype=a.dtype)
    idx = np.empty_like(a, dtype='i8')
    idx = _insert_nan2(a, na, nan_idx, ni, idx)
    b[idx] = a

    if isinstance(a_, pd.Series):
        t = insert_nan(a_.index.values, nan_idx)
        return pd.Series(b, index=t)
    else:
        return b
