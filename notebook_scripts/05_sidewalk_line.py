import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiLineString
from shapely.ops import nearest_points
from shapely import affinity

import warnings
warnings.filterwarnings('ignore')

import argparse
parser = argparse.ArgumentParser(description='set folder')
parser.add_argument('folder', metavar='fd', type=str)
args = parser.parse_args()

# folder 
# folder = r'../example_2'
base_folder = rf"../{args.folder}"

# read param json 
with open(rf'{base_folder}/param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
size = param_dict['size_code']
# decide which scale folder the processing result goes by the scale
base_folder = rf"{base_folder}/data"
folder_temp = rf'{base_folder}/temp'
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}/500'
else:
    scale = 1000
    folder = rf'{base_folder}/1000'

lane_width = param_dict['lane_width']
line_width_meter = scale*param_dict['line_width'] / 1000.0
line_gap_meter = scale*param_dict['line_gap'] / 1000.0

# files

crossing_df = gpd.read_file(rf"{folder}/crossing_lines.geojson")
extent_df = gpd.read_file(rf"{base_folder}/extent_{size}.geojson")
sidewalk_df = gpd.read_file(rf"{base_folder}/sidewalk_lines.geojson")
street_df = gpd.read_file(rf"{base_folder}/snapped_streets.geojson")
street_boundary = gpd.read_file(rf"{folder}/street_boundary_filled.geojson")
try:   
    island_df = gpd.read_file(rf"{folder}/islands_full.geojson")
    island_df = island_df[island_df.geometry.intersects(extent_df.geometry.unary_union)]
except:
    island_df = None
street_boundary = street_boundary[street_boundary.geometry.intersects(extent_df.geometry.unary_union)]

extnet_center = extent_df.geometry.unary_union.centroid

"""the sidewalk tags"""
# process the sidewalk lines from the street 
def getSidewalkTag(tagstr):
    try:
        if 'sidewalk' in tagstr:
            feat = [x for x in tagstr.split(',') if '"sidewalk"' in x][0]
            tag = feat[feat.rfind('>')+2:feat.rfind('"')] 
            return tag
    except:
        return 'no'
def sidewalkFromStreet(x, dist):
    """x is the x in apply x.geometry
    dist in m"""
    # parse tag
    tag = getSidewalkTag(x.other_tags)
    if tag not in ['left', 'right', 'both']:
        return np.nan
    if tag == 'right' or tag == 'left':
        this_dist = dist + line_width_meter*2 + 0.5*x.lanes*lane_width
        new_sidewalk = x.geometry.parallel_offset(this_dist, tag)
        return new_sidewalk
    if tag == 'both':
        this_dist = dist + line_width_meter*2 + 0.5*x.lanes*lane_width
        sleft = x.geometry.parallel_offset(this_dist, 'left')
        sright = x.geometry.parallel_offset(this_dist, 'right')
        new_sidewalk = MultiLineString([sleft, sright])
        return new_sidewalk
street_df['sidewalkk'] = street_df.apply(lambda x: sidewalkFromStreet(x, line_gap_meter), axis=1)
# prepare this for later
st_sw_df = street_df[~street_df['sidewalkk'].isna()]
st_sw_df.set_geometry('sidewalkk', inplace=True)
st_sw_df.drop(columns=['geometry'], inplace=True)
if island_df is not None:
    st_sw_df['on_island'] = st_sw_df.apply(lambda x: x.sidewalkk.intersects(island_df.geometry.unary_union), axis=1)
    st_sw_df['too_short'] = st_sw_df.apply(lambda x: True if x.sidewalkk.length < 5 else False, axis=1)
    st_sw_df = st_sw_df[(st_sw_df['on_island'] == False) & (st_sw_df['too_short'] == False)]
street_sidewalks = st_sw_df.rename(columns={"sidewalkk": "geometry"})


"""the sidewalk lines"""
# displace the sidewalk lines with the street
# first remove the little parts and the parts on the island
if island_df is not None:
    sidewalk_df.geometry = sidewalk_df.geometry.intersection(extent_df.geometry.unary_union)
    sidewalk_df = sidewalk_df[sidewalk_df.geometry.is_empty == False]
    sidewalk_df['on_island'] = sidewalk_df.apply(lambda x: x.geometry.intersects(island_df.geometry.unary_union), axis=1)
    sidewalk_df['too_short'] = sidewalk_df.apply(lambda x: True if x.geometry.length < 5 else False, axis=1)
    sidewalk_df = sidewalk_df[(sidewalk_df['on_island'] == False) & (sidewalk_df['too_short'] == False)]

# displace
def azimuth(point1, point2):
    angle = np.arctan2(point2.x - point1.x, point2.y - point1.y)
    return np.degrees(angle) if angle >= 0 else np.degrees(angle) + 360
def displaceSidewalk(curb, sidewalk, distance):
    '''sidewalk is the geom line'''
    nearests = nearest_points(curb, sidewalk)
    if nearests[0].distance(nearests[1])> distance:
        # print('initially ok')
        return sidewalk
    i = 0 
    while i < 1:
        if nearests[0].distance(nearests[1])> distance:
            # print(f"intil {i} and ok")
            return sidewalk
            break
        # move
        # x_sign = 1; y_sign = 1
        b = azimuth(nearests[0], nearests[1]) + 90
        x_sign = 1 if (nearests[1].x > nearests[0].x ) else -1
        y_sign = 1 if (nearests[1].y > nearests[0].y ) else -1
        if nearests[1].x == nearests[0].x and nearests[1].y == nearests[0].y:
            x_sign = 1 if (sidewalk.centroid.x > extnet_center.x) else -1 
            y_sign = 1 if (sidewalk.centroid.y > extnet_center.y) else -1 
            b = azimuth(extnet_center, nearests[1]) + 90
            # print(x_sign, y_sign)
        x_move = distance * abs(np.cos(np.radians(b))) * x_sign 
        y_move = distance * abs(np.sin(np.radians(b))) * y_sign
        sidewalk = affinity.translate(sidewalk, x_move, y_move)
        nearests = nearest_points(curb, sidewalk)
        i = i+1
    return sidewalk
curb = street_boundary.geometry.unary_union.intersection(extent_df.geometry.unary_union)
sidewalk_df.geometry = sidewalk_df.geometry.intersection(extent_df.geometry.unary_union).difference(curb)
sidewalk_df = sidewalk_df[sidewalk_df.geometry.intersects(extent_df.geometry.unary_union)]


displace_distance = line_width_meter + line_gap_meter
sidewalk_df['displaced'] = sidewalk_df.apply(lambda x: displaceSidewalk(curb, x.geometry, displace_distance), axis=1)
sidewalk_df.set_geometry('displaced', inplace=True)
sidewalk_df.drop(columns=['geometry'], inplace=True)
temp = gpd.GeoDataFrame(sidewalk_df, crs=f'epsg:{epsg}', geometry='displaced')

temp.to_file(rf"{folder_temp}/displace_sd.geojson")


"""merge and out """
# merge the two 
sidewalk_df.displaced = sidewalk_df.difference(street_boundary.geometry.unary_union.buffer(line_gap_meter))
sidewalk_df['buffered'] = sidewalk_df.displaced.buffer(line_gap_meter)
buffered = sidewalk_df.buffered.unary_union
# TODO: cut with the streets
street_sidewalks['cut'] = street_sidewalks.geometry.difference(buffered)
street_sidewalks = street_sidewalks[street_sidewalks['cut'].disjoint(street_boundary.geometry.unary_union.buffer(line_gap_meter))]
street_sidewalks.drop(columns=['geometry'], inplace=True)
street_sidewalks.rename(columns={"cut": "displaced"}, inplace=True)

sidewalk_df.drop(columns='buffered', inplace=True)
new_df = pd.concat([sidewalk_df, street_sidewalks])

# out 
out = new_df[['osm_id', 'name', 'highway', 'other_tags', 'displaced']]
out = gpd.GeoDataFrame(out, crs=f'epsg:{epsg}', geometry='displaced')
out = out[out.geometry.intersects(extent_df.geometry.unary_union)]
out.to_file(rf'{folder}/sidewalk_lines.geojson', driver='GeoJSON')

# fin for now. fix the displacement part. 
