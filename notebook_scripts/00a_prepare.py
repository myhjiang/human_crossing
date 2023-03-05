"""prepare stuff for the following steps:
make extent
make folders"""

# make extent box (polygon) from center coords and sizes

import geopandas as gpd
from shapely.geometry import box

import warnings
warnings.filterwarnings('ignore')

import argparse
parser = argparse.ArgumentParser(description='set folder')
parser.add_argument('folder', metavar='fd', type=str)
args = parser.parse_args()

# folder 
# folder = r'../example_2'
folder = rf"../{args.folder}"

# make new folders


import json

from pyproj import Proj, transform

with open(rf'{folder}/param.json') as fp:
    param_dict = json.load(fp)
with open(r'size_lookup_table_fr.json') as fp:
    size_dict = json.load(fp)

center_lat = param_dict['center_lat']
center_lon = param_dict['center_lon']
size_code = param_dict['size_code']

epsg = param_dict['epsg']


if 'A3' in size_code:
    scale = 500
else:
    scale = 1000
x, y = size_dict[size_code]

folder = rf"{folder}/data"

from pathlib import Path

Path(rf"{folder}/1000").mkdir(parents=True, exist_ok=True)
Path(rf"{folder}/500").mkdir(parents=True, exist_ok=True)
Path(rf"{folder}/temp").mkdir(parents=True, exist_ok=True)

half_x = x / 2.0 * scale / 1000
half_y = y / 2.0 * scale / 1000

inProj = Proj(init='epsg:4326')
outProj = Proj(init=f'epsg:{epsg}')
center_x, center_y = transform(inProj,outProj, center_lon,center_lat)

b = box(center_x-half_x, center_y-half_y, center_x+half_x, center_y+half_y)

print(center_x-half_x, center_y-half_y, center_x+half_x, center_y+half_y)
# quit()

d = {'geometry': [b]}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
gdf.to_file(rf'{folder}/extent_{size_code}.geojson', driver='GeoJSON')  # real extent based on paper choice

# the bigger extent for processing
x, y = [400, 400]
half_x = x / 2.0 
half_y = y / 2.0 
inProj = Proj(init='epsg:4326')
outProj = Proj(init=f'epsg:{epsg}')
center_x, center_y = transform(inProj,outProj, center_lon,center_lat)
b = box(center_x-half_x, center_y-half_y, center_x+half_x, center_y+half_y)
d = {'geometry': [b]}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
gdf.set_geometry('geometry', inplace=True)
gdf.to_file(rf'{folder}/big_extent.geojson', driver='GeoJSON')


print("finished")