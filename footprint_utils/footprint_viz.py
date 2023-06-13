import xarray as xr
import colorcet
import numpy as np
import plotly.graph_objects as go
from pyproj import Transformer
import datashader
from datashader import transfer_functions as tf

from footprint_utils import xarray_extras  # noq


_gcs_to_3857 = Transformer.from_crs(4326, 3857, always_xy=True)
_3857_to_gcs = Transformer.from_crs(3857, 4326, always_xy=True)


def trim_small_values(da, threshold=0.01, check_if_lon_lat_increasing=False):
    lon, lat = da.geo.get_lon_lat_label()
    if threshold is not None and threshold > 0:
        if check_if_lon_lat_increasing:
            da = da.xrx.make_coordinates_increasing([lon, lat])
        da_filtered = da.where(da >= da.max() * threshold, drop=True)
        lon2, lat2 = da_filtered[lon], da_filtered[lat]
        # BUG fix: lon2, lat2 are 0 size arrays if da has nan's only
        # TODO: do it properly...
        if len(lon2) >= 1 and len(lat2) >= 1:
            da = da.sel({lon: slice(lon2[0], lon2[-1]), lat: slice(lat2[0], lat2[-1])})

    if threshold is None:
        threshold = 0
    return da.where(da > threshold)


def assign_proj_coords(data, proj, is_proj_rectilinear=False):
    lon, lat = data.geo.get_lon_lat_label()
    if is_proj_rectilinear:
        lon_coords, lat_coords = data[lon].values, data[lat].values
        x, _ = proj.transform(lon_coords, np.zeros_like(lon_coords))
        _, y = proj.transform(np.zeros_like(lat_coords), lat_coords)
        return data.assign_coords({lon: x, lat: y}).rename({lon: 'x', lat: 'y'})
    else:
        lon_coords, lat_coords = np.meshgrid(data[lon].values, data[lat].values)
        shp = lon_coords.shape
        x, y = proj.transform(np.ravel(lon_coords), np.ravel(lat_coords))
        return data.assign_coords({
            'x': ([lat, lon], np.reshape(x, shp)),
            'y': ([lat, lon], np.reshape(y, shp)),
        })


def get_spatial_extent(da, proj):
    x_coords, y_coords = da['x'].values, da['y'].values
    x_corners, y_corners = np.meshgrid(x_coords[[0, -1]], y_coords[[0, -1]])
    lon_corners, lat_corners = proj.transform(np.ravel(x_corners)[[0, 1, 3, 2]], np.ravel(y_corners)[[0, 1, 3, 2]])
    return list(zip(lon_corners, lat_corners))


def regrid(da, upsampling_resol_factor=None, proj=3857, regrid_resol=None, is_proj_rectilinear=False):
    da = da.reset_coords(drop=True)

    if proj == 3857:
        proj_tr = _gcs_to_3857
        proj_tr_inv = _3857_to_gcs
    else:
        proj_tr = Transformer.from_crs(4326, proj, always_xy=True)
        proj_tr_inv = Transformer.from_crs(proj, 4326, always_xy=True)

    lon, lat = da.geo.get_lon_lat_label()

    if regrid_resol is None:
        if proj == 3857:
            regrid_resol = (len(da[lon]), len(da[lat]) * 4)
        else:
            raise ValueError('for projection other than 3857, must provide regrid_resol=(lon, lat)')
    assert isinstance(regrid_resol, (tuple, list)) and len(regrid_resol) == 2

    regrid_lon, regrid_lat = regrid_resol

    cvs = datashader.Canvas(plot_height=regrid_lat, plot_width=regrid_lon)
    da2 = assign_proj_coords(da, proj_tr, is_proj_rectilinear=is_proj_rectilinear)
    da_regridded = cvs.quadmesh(da2, x='x', y='y')

    if upsampling_resol_factor is not None:
        assert isinstance(upsampling_resol_factor, (tuple, list)) and len(upsampling_resol_factor) == 2
        cvs = datashader.Canvas(plot_height=upsampling_resol_factor[1] * len(da[lat]),
                                plot_width=upsampling_resol_factor[0] * len(da[lon]))
        da_regridded = cvs.raster(da_regridded)

    return da_regridded, get_spatial_extent(da_regridded, proj_tr_inv)


def get_footprint_viz(da, threshold=0.003):
    # BUG fix: must avoid poles - otherwise dash/plotly does not want to refresh the image layer on the map
    # lat in [-85, 85] is because of the range of web Mercator projection
    da = da.sel(latitude=slice(-85, 85))

    da = trim_small_values(da, threshold=threshold)
    agg, coordinates = regrid(da, upsampling_resol_factor=(10, 10), is_proj_rectilinear=True)
    im1 = tf.shade(agg, cmap=colorcet.CET_L17, how='linear', alpha=0)
    agg2 = agg - agg.min()
    agg2 = agg2 / agg2.max()
    im2 = tf.shade(np.power(agg2, 1 / 4), cmap='#000000', how='linear', alpha=255, min_alpha=0)
    im = im1 + im2
    img = im[::-1].to_pil()

    mapbox_layer = {
        "sourcetype": "image",
        "source": img,
        "coordinates": coordinates,
    }
    return mapbox_layer
