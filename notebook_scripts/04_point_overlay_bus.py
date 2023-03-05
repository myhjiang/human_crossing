'''bus stop with an overlay-strategy parameter
a different way than the previous one'''

import json
import geopandas as gpd
from shapely.geometry import LineString, Point
import numpy as np
from shapely import affinity

import argparse
parser = argparse.ArgumentParser(description='set folder')
parser.add_argument('folder', metavar='fd', type=str)
args = parser.parse_args()

# folder 
# folder = r'../example_2'
base_folder = rf"../{args.folder}"

# # folder 
# base_folder = r'../example_0'
folder_temp = rf'{base_folder}/temp'
# read param json 
with open(rf'{base_folder}/param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
size = param_dict['size_code']
# decide which scale folder the processing result goes by the scale
base_folder = rf"{base_folder}/data"
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}/500'
else:
    scale = 1000
    folder = rf'{base_folder}/1000'
# overlay preference as param
pref = param_dict['overlay_pref']  # "direct", or "displace"
move_dist = param_dict['icon_gap']*scale / 1000 + 2

# files
bus_df = gpd.read_file(rf'{base_folder}/bus_stop.geojson', driver='GeoJSON')
street_boundary_df = gpd.read_file(rf'{folder}/street_boundary_filled.geojson', driver='GeoJSON')
street_line_df = gpd.read_file(rf'{base_folder}/snapped_streets.geojson', driver='GeoJSON')

# NOTSURE only do the stop position? is a match needed here？
bus_df['type'] = bus_df.apply(lambda x: 'center' if 'stop_position' in x.other_tags else 'side', axis=1)
# print(bus_df)
bus_df['buffer'] = bus_df.geometry.buffer(15)  # NOTSURE this 15m distance is too far? this condition needs check
bus_dup = bus_df.copy()
bus_dup.set_geometry('buffer', inplace=True)
bus_df.drop(columns=['buffer'], inplace=True)
bus_df = bus_df[bus_df['type']=='center']; bus_dup = bus_dup[bus_dup['type']=='side']
join_df = gpd.sjoin(bus_dup, bus_df, how='inner')
join_df = join_df[join_df['name_left'] == join_df['name_right']]
# print(join_df.columns)
join_df = join_df[['osm_id_left', 'geometry', 'osm_id_right']]
# regular join back on osm id to get the other geometry
join_df = join_df.merge(bus_df, left_on='osm_id_right', right_on='osm_id')
join_df['line'] = join_df.apply(lambda x: LineString([x.geometry_x.centroid, x.geometry_y]), axis=1)
join_df['intersect'] = join_df.apply(lambda x: x.line.intersection(street_boundary_df.geometry.unary_union), axis=1)
# this is the intersection point with the street boundary line
# this point will stay there if param = direct, otherwise move towards the sidewalk side with a dist
def azimuth(point1, point2):
    angle = np.arctan2(point2.x - point1.x, point2.y - point1.y)
    return np.degrees(angle) if angle >= 0 else np.degrees(angle) + 360
def movePerpendicular(line, point, dist, outside_point):
    buffer = point.buffer(1)
    intersect = line.intersection(buffer)
    if intersect.geom_type == "GeometryCollection":
        return Point()
    b = azimuth(intersect.boundary[0], intersect.boundary[1]) + 90
    x_sign = -1; y_sign = -1  #CHECK: this direction, forgot how it should be now...
    x_move = dist * abs(np.cos(np.radians(b))) * x_sign 
    y_move = dist * abs(np.sin(np.radians(b))) * y_sign 
    point = affinity.translate(point, x_move, y_move)
    return point

# pref = "direct"
if pref == "direct":
    join_df['newpoint'] = join_df['intersect']
if pref == "displace":
    join_df['newpoint'] = join_df.apply(lambda x: movePerpendicular(x.line, x.intersect, move_dist, x.geometry_y), axis=1)

# out
gdf = gpd.GeoDataFrame(join_df, crs=f"EPSG:{epsg}", geometry='newpoint')
out = gdf[['osm_id', 'newpoint']]
out.to_file(rf'{folder}/bus_stop_overlay.geojson', driver='GeoJSON')
