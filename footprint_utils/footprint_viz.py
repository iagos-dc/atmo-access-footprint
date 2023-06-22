import xarray as xr
import colorcet
import numpy as np
import plotly
import plotly.graph_objects as go
from pyproj import Transformer
import datashader
from datashader import transfer_functions as tf

from footprint_utils import xarray_extras  # noq

from log import log_exectime


_gcs_to_3857 = Transformer.from_crs(4326, 3857, always_xy=True)
_3857_to_gcs = Transformer.from_crs(3857, 4326, always_xy=True)


def trim_small_values(da, threshold=0.01, check_if_lon_lat_increasing=False):
    lon, lat = da.geo.get_lon_lat_label()
    if check_if_lon_lat_increasing:
        da = da.xrx.make_coordinates_increasing([lon, lat])
    da_max = da.max()
    da_filtered = da.where(da > da_max * threshold, drop=True)
    lon2, lat2 = da_filtered[lon], da_filtered[lat]
    # BUG fix: lon2, lat2 are 0 size arrays if da has nan's only
    # TODO: do it properly...
    if len(lon2) >= 1 and len(lat2) >= 1:
        da = da.sel({lon: slice(lon2[0], lon2[-1]), lat: slice(lat2[0], lat2[-1])})

    return da.where(da > da_max * threshold)


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


def color_to_alpha(x):
    return np.power(x, 1/2)


def get_footprint_viz(da, color_scale_transform, residence_time_cutoff):
    value_to_color, color_to_value = color_scale_transform

    lat = da.geo.get_lat_label()

    # BUG fix: must avoid poles - otherwise dash/plotly does not want to refresh the image layer on the map
    # lat in [-85, 85] is because of the range of web Mercator projection
    da = da.sel({lat: slice(-85, 85)})

    da = trim_small_values(da, threshold=residence_time_cutoff)

    agg, coordinates = regrid(da, upsampling_resol_factor=(10, 10), is_proj_rectilinear=True)
    agg_max = agg.max().item()
    agg_min = agg.min().item()
    # print(agg_max, agg_min)

    agg_color = value_to_color(agg)
    color_max = value_to_color(agg_max)
    color_min = value_to_color(agg_min)

    agg_alpha = color_to_alpha(agg_color - color_min)
    alpha_max = color_to_alpha(color_max - color_min)
    im1 = tf.shade(agg_color, cmap=colorcet.CET_L17, how='linear', alpha=0, span=[color_min, color_max])
    im2 = tf.shade(agg_alpha, cmap='#000000', how='linear', alpha=255, min_alpha=0, span=[0, alpha_max])
    im = im1 + im2
    img = im[::-1].to_pil()

    # setup colorscale
    colorscale = colorcet.CET_L17
    ncolors = len(colorscale)

    def hex_and_alpha_to_rgba(_hex, a):
        r, g, b = plotly.colors.hex_to_rgb(_hex)
        return f'rgba({r}, {g}, {b}, {a})'

    color_frac = np.linspace(0, 1, ncolors)
    alpha = color_to_alpha(color_frac * (color_max - color_min)) / alpha_max
    cs = [hex_and_alpha_to_rgba(c, a) for c, a in zip(colorscale, alpha)]

    nticks = 11
    tickpos = np.linspace(0, 1, nticks)
    tickvals = color_to_value((1 - tickpos) * color_min + tickpos * color_max)
    ticktext = [f'{v:.1e}' for v in tickvals]
    colorscale_trace = {
        'marker': {
            'cmax': 1, 'cmin': 0,
            'colorbar': {
                'bgcolor': '#d4dadc',
                'outlinewidth': 0,
                'thickness': 25,
                'tickvals': tickpos,
                'ticktext': ticktext,
                'title': {
                    'text': 'Residence<br>time (s km-2)',
                    'font': {'size': 12},
                },
                # 'ticks': 'inside',
                # 'ticklen': 5,
                'orientation': 'v',
                'len': 0.9,
                'lenmode': 'fraction',
                'y': 0,
                'yanchor': 'bottom',
                'yref': 'paper',
            },
            'colorscale': [[c, rgba] for c, rgba in zip(color_frac, cs)],
            'showscale': True,
        },
        'mode': 'markers',
        'showlegend': False,
        'type': 'scatter',
        'x': [None],
        'y': [None],
    }

    return img, coordinates, colorscale_trace
