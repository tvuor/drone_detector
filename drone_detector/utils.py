# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_utils.ipynb (unless otherwise specified).

__all__ = ['rangeof', 'fix_multipolys', 'cone_v', 'cut_cone_v']

# Cell

from .imports import *

# Cell

def rangeof(iterable):
    "Equivalent for range(len(iterable))"
    return range(len(iterable))

# Cell

import shapely
def fix_multipolys(multipoly:shapely.geometry.MultiPolygon):
    """Convert MultiPolygon to a single Polygon.
    The resulting Polygon has the exterior boundaries of the largest geometry of the MultiPolygon"""
    temp_poly = None
    max_area = 0
    for geom in multipoly.geoms:
        area = geom.area
        if area > max_area:
            max_area = area
            temp_poly = geom
    return shapely.geometry.Polygon(temp_poly.exterior)

# Cell

def cone_v(r:float, h:float) -> float:
    "V = (Ah)/3"
    A = np.pi * r**2
    V = (A * h) / 3
    return V

def cut_cone_v(r_1:float, r_2:float, h:float):
    "V = (h(A + sqrt(A*A') + A))/3"
    A_1 = np.pi * r_1**2
    A_2 = np.pi * r_2**2
    V = (h*(A_1 + np.sqrt(A_1 * A_2) + A_2))/3
    return V
