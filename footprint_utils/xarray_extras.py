import xarray as xr


@xr.register_dataset_accessor('xrx')
@xr.register_dataarray_accessor('xrx')
class xrx:
    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def make_coordinates_increasing(self, coord_labels, allow_sorting=True):
        """
        Sorts coordinates
        :param self: an xarray Dataset or DataArray
        :param coord_labels: a string or an interable of strings - labels of dataset's coordinates
        :param allow_sorting: bool; default True; indicate if sortby method is allowed to be used as a last resort
        :return: ds with a chosen coordinate(s) in increasing order
        """
        ds = self._obj
        if isinstance(coord_labels, str):
            coord_labels = (coord_labels, )
        for coord_label in coord_labels:
            if not ds.indexes[coord_label].is_monotonic_increasing:
                if ds.indexes[coord_label].is_monotonic_decreasing:
                    ds = ds.isel({coord_label: slice(None, None, -1)})
                elif allow_sorting:
                    ds = ds.sortby(coord_label)
                else:
                    raise ValueError(f'{ds.xrx.short_dataset_repr()} has coordinate {coord_label} which is neither increasing nor decreasing')
        return ds


@xr.register_dataset_accessor('geo')
@xr.register_dataarray_accessor('geo')
class geo:
    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def get_lon_label(self):
        ds = self._obj
        ds_dims = ds.dims
        if 'longitude' in ds_dims:
            label = 'longitude'
        elif 'lon' in ds_dims:
            label = 'lon'
        else:
            raise ValueError('neither "longitude" nor "lon" dimension found in ds')
        return label

    def get_lat_label(self):
        ds = self._obj
        ds_dims = ds.dims
        if 'latitude' in ds_dims:
            label = 'latitude'
        elif 'lat' in ds_dims:
            label = 'lat'
        else:
            raise ValueError('neither "latitude" nor "lat" dimension found in ds')
        return label

    def get_lon_lat_label(self):
        ds = self._obj
        return ds.geo.get_lon_label(), ds.geo.get_lat_label()
