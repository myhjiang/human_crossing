"""same idea with the 04_crossing_lines_2 script
adjustments in the street area / street boundary filled/original differences"""

import itertools
import json
import os

import geopandas as gpd
from shapely import affinity
from shapely.geometry import LineString
from shapely.ops import nearest_points

import argparse
parser = argparse.ArgumentParser(description='set folder')
parser.add_argument('folder', metavar='fd', type=str)
args = parser.parse_args()

# folder 
# folder = r'../example_2'
base_folder = rf"../{args.folder}"

# # folder 
# base_folder = r'../example_2'
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


lane_width = param_dict['lane_width']

crossing_point = gpd.read_file(rf'{base_folder}/crossing_points.geojson')
street_displaced = gpd.read_file(rf'{base_folder}/snapped_streets.geojson')
extent_df = gpd.read_file(rf'{base_folder}/big_extent.geojson')
small_extent = gpd.read_file(rf'{base_folder}/extent_{size}.geojson')
street_area = gpd.read_file(rf'{folder}/street_area.geojson')
street_boundary = gpd.read_file(rf'{folder}/street_boundary_original.geojson')
street_outer_boundary = gpd.read_file(rf'{folder}/street_boundary_filled.geojson')
try:
    island_df = gpd.read_file(rf'{folder}/islands_full.geojson')
except:
    island_df = None

# prepare street dist column 
lane_width = param_dict['lane_width']
line_width_meter = scale*param_dict['line_width'] / 1000.0
street_displaced['dist'] = street_displaced.lanes.apply(lambda x: (lane_width*x+2*line_width_meter)/2)

# TODO: remove the crossing point on the cycleway

# cut with extent
crossing_point['inside_extent'] = crossing_point['geometry'].intersection(extent_df.geometry.tolist()[0])
crossing_point.set_geometry('inside_extent', inplace=True)
crossing_point = crossing_point[(crossing_point.geometry.is_empty==False) & (crossing_point.geometry!=None)]

# snap to street
crossing_point.geometry = crossing_point.apply(lambda x: nearest_points(x.geometry, street_displaced.geometry.unary_union)[1], axis=1)

# point on line intersect with street
crossing_point['buffer'] = crossing_point.geometry.buffer(1)
crossing_point.set_geometry('buffer', inplace=True)
join_df = gpd.sjoin(crossing_point, street_displaced, how="left")
# if get multiple join, take one, either one seems ok though? TODO: keep the more major road
join_df = join_df.sort_values(by=['osm_id_left', 'highway_right']) # actually, after sort, the primary is always above secondary and empty...!, but what about the "links" though?
join_df.drop_duplicates(subset=['osm_id_left'], inplace=True)
join_df.set_index('osm_id_right', inplace=True)

# join back, grow line and rotate
street_displaced.set_index('osm_id', inplace=True)
s = join_df.geometry.intersection(street_displaced.geometry, align=True)
sdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(s)).reset_index()
sdf.rename(columns={'index': 'osm_id'}, inplace=True)
sdf.rename_geometry('short_line', inplace=True)
join_df.reset_index(inplace=True)
join_df = join_df.merge(sdf, left_on='osm_id_right', right_on='osm_id')
join_df.set_geometry('short_line', inplace=True)
join_df['short_line'] = join_df.apply(lambda x: affinity.rotate(x.short_line, 90), axis=1)
# simply a bit so it's not bendy
join_df['short_line'] = join_df.apply(lambda x:x.short_line.simplify(1, preserve_topology=False), axis=1)
join_df['short_line'] = join_df.apply(lambda x: affinity.scale(x.short_line, x.dist, x.dist), axis=1)

# snap to the street
# extend line helper 
def getExtrapoledLine(p1,p2, ratio):
    'Creates a line extrapoled in p1->p2 direction'
    # EXTRAPOL_RATIO = 1.2
    a = p1
    b = (p1.x+ratio*(p2.x-p1.x), p1.y+ratio*(p2.y-p1.y) )
    return LineString([a,b])
def snapStreet(line, street_boundary, width):
    (startpoint, endpoint) = line.boundary[0], line.boundary[1]
    # get the direction right here?
    endpoint_1 = max([startpoint, endpoint], key=lambda x: x.distance(street_boundary))
    startpoint_1 = min([startpoint, endpoint], key=lambda x: x.distance(street_boundary))
    startpoint_snap = nearest_points(startpoint_1, street_boundary)[1]
    endpoint_snap = nearest_points(endpoint_1, street_boundary)[1]
    snapped_line = LineString([startpoint_snap, endpoint_snap])
    while snapped_line.length < width:  # when both ends are snapped to the same side of street 
        # extend the original line on the end side little by little (so it doesn't go boom)
        line = getExtrapoledLine(startpoint_1, endpoint_1, 1.2)
        endpoint = line.boundary[1]
        endpoint_snap = nearest_points(endpoint, street_boundary)[1]
        snapped_line = LineString([startpoint_snap, endpoint_snap])
        endpoint_1 = endpoint
    return snapped_line

# will snap to the boundary_original, no matter where that original come from (sidewalk, or original street)
join_df['short_line'] = join_df.apply(lambda x: snapStreet(x.short_line, street_boundary.geometry.unary_union, x.dist), axis=1)

# before shrinking on the island side:
# remove the islands that are not connected by the zebras and redo the street boundaries
# also remove the "fake ones" outside the extent
def standaloneIsland(island_df, crossing_df, street_area_df):
    extended_crossing = crossing_df.copy()
    extended_crossing.short_line = extended_crossing.apply(lambda x: affinity.scale(x.short_line, 1.01, 1.01), axis=1)
    island_df = island_df[island_df.geometry.intersects(extent_df.geometry.unary_union)]
    if len(island_df) == 0:
        # remove the file!
        os.remove(rf"{folder}/islands_full.geojson")
        return 
    island_df['connected'] = island_df.geometry.intersects(extended_crossing.geometry.unary_union)
    island_df = island_df[island_df['connected']==True]
    # output new files
    if len(island_df) > 0:
        island_df.to_file(rf"{folder}/islands_full.geojson")
    else:
        os.remove(rf"{folder}/islands_full.geojson")
    # CHECK: do I need to redo the street boundaries again? which ones? 

if island_df is not None:
    standaloneIsland(island_df, join_df, street_area)

# shrink line helper
def shrinkLine(p1,p2, shrink_dist):
    'Creates a line extrapoled in p1->p2 direction'
    len_line = p1.distance(p2)
    RATIO = 1 - shrink_dist / len_line
    a = p1
    b = (p1.x+RATIO*(p2.x-p1.x), p1.y+RATIO*(p2.y-p1.y) )
    # a = (b[0]+RATIO*(p1.x-b[0]), b[1]+RATIO*(p1.y-b[1]) )
    return LineString([a,b])
def shrinkCrossing(line, island):  # only on the island side!!
    shrink_dist = 1  # in meter
    buf = line.buffer(1)
    inter_p = buf.intersection(island).centroid
    # inter_p = line.intersection(street_boundary.geometry.unary_union).intersection(island)
    if inter_p.is_empty:
        # print('empty')
        return line
    else:
        (startpoint, endpoint) = line.boundary[0], line.boundary[1]
        p2 = min([point for point in [startpoint, endpoint]], key=lambda x: x.distance(inter_p))
        p1 = max([point for point in [startpoint, endpoint]], key=lambda x: x.distance(inter_p))
        new_line = shrinkLine(p1, p2, shrink_dist)
        # print(line.length, new_line.length)
        return new_line
if not island_df is None:
    island_full = island_df.geometry.unary_union
    join_df['short_line'] = join_df.apply(lambda x: shrinkCrossing(x.short_line, island_full), axis=1)


# check for "double zebra" because of the parallel street situation
# count how many street lines (not street boundary!!) each one cross
join_df.set_geometry('short_line', inplace=True)
# remove the duplicate first 
'''for each crossing, take the short line that has the shortest distance with it'''
join_df['dist_point_line'] = join_df.apply(lambda x: x['geometry'].distance(x.short_line), axis=1)
join_df.sort_values(by=['osm_id_left','dist_point_line'], inplace=True)
join_df = join_df[['osm_id_left', 'name_right', 'highway_left', 'other_tags_left', 'short_line']]
name_list = ['osm_id', 'name', 'highway', 'other_tags', 'short_line']
join_df.columns = name_list
join_df.drop_duplicates(subset=['osm_id'], keep='first', inplace=True)
join_df = gpd.sjoin(join_df, street_displaced, how="left")
join_df = join_df[['osm_id', 'name_left', 'highway_left', 'other_tags_left', 'short_line', 'index_right']]
join_df = join_df.groupby('osm_id').agg({x: 'first' if x in ['short_line', 'name_left', 'highway_left', 'other_tags_left', 'osm_id'] else lambda x: list(x) for x in join_df}).reset_index(drop=True)

# output this double street id for later label placement 
street_ids = join_df.index_right.values.tolist()
doubles = [x for x in street_ids if len(x) > 1]
unique_doubles = [list(x) for x in set(tuple(x) for x in doubles)]
try:
    with open(rf'{folder_temp}/double_streets.json', 'w') as fp:
        json.dump([ob for ob in unique_doubles], fp)
except:
    pass

doubles_df = join_df[join_df['index_right'].str.len()>1]
doubles_df = doubles_df.groupby(doubles_df['index_right'].map(tuple)).agg({'osm_id': lambda x: list(x), 'short_line': lambda x: list (x)})
print(doubles_df)

def removeDoubles(id_list, line_list):
    removed_list = []
    # print(len(id_list), id_list, [x.length for x in line_list])
    line_list_copy = line_list.copy()
    line_list_copy_2 = line_list.copy()
    id_list_copy = id_list.copy()
    id_list_copy_2 = id_list.copy()
    for line in line_list_copy:
        if line not in line_list_copy_2:
            continue
        # # print(line_list)
        line_id = id_list_copy_2[line_list_copy_2.index(line)]
        print(line_id)
        # print('remaining lines: ', [idx for idx in id_list_copy])
        # print('distances: ', [linex.distance(line) for linex in line_list_copy])
        line_list_copy_2.remove(line)
        # print(len(line_list_copy))
        if len(line_list_copy_2) < 1:
            continue
        nearest_line = min([linex for linex in line_list_copy_2], key=lambda x: x.distance(line))
        print(line.distance(nearest_line))
        if line.distance(nearest_line) < 5:  # meter
            removed_list.append(line_id)
            id_list_copy_2.remove(line_id)
            # print(len(id_list_copy), len(line_list_copy))
            print('removed, ', line_id)
    return removed_list

if doubles_df.empty==False:
    doubles_df['removed_id'] = doubles_df.apply(lambda x: removeDoubles(x.osm_id, x.short_line), axis=1)
    removed_ids = list(itertools.chain(*doubles_df.removed_id.values.tolist()))
    # print(removed_ids)
    # remove these ids from the join df
    join_df = join_df[~join_df.osm_id.isin(removed_ids)]

# remove the very close ones, for whatever reasons
def removeTooClose(df):
    gdf1 = gpd.GeoDataFrame(df, geometry='short_line').reset_index()
    buffered = gdf1.buffer(1)
    buffered_df = gpd.GeoDataFrame(geometry=buffered)
    joined = gpd.sjoin(gdf1, buffered_df, op='intersects', lsuffix='leftleft', rsuffix='rightright')

    close_pairs = joined[joined.index < joined.index_rightright]
    to_drop = close_pairs.index_rightright.tolist()
    gdf1 = gdf1.drop(to_drop)
    return gdf1


join_df = removeTooClose(join_df)


# interactors on the end of the zebras, but not on the islands? 
interactor_df = gpd.GeoDataFrame(join_df, crs=f'epsg:{epsg}', geometry='short_line')
interactor_df['short_line'] = interactor_df.apply(lambda x: getExtrapoledLine(x.short_line.boundary[0], x.short_line.boundary[1], 1.01), axis=1)
interactor_df['short_line'] = interactor_df.apply(lambda x: getExtrapoledLine(x.short_line.boundary[1], x.short_line.boundary[0], 1.01), axis=1)
interactor_df['points'] = interactor_df.geometry.intersection(street_outer_boundary.geometry.unary_union)

# out zebra file
out = gpd.GeoDataFrame(join_df, crs=f'epsg:{epsg}', geometry='short_line')
out['street_ids'] = out['index_right'].apply(lambda x: ','.join(map(str, sorted(x))))
out = out[['osm_id', 'name_left', 'highway_left', 'other_tags_left', 'short_line', 'street_ids']]
name_list = ['osm_id', 'name', 'highway', 'other_tags', 'short_line', 'street_ids']
out.columns = name_list
out.to_file(rf'{folder}/crossing_lines.geojson', driver='GeoJSON')

# out interactor file 
# TODO: give the interactor the 'crossing' type attribute? or just in the 'highway'?
interactor_df.set_geometry('points', inplace=True)
out2 = interactor_df[['osm_id', 'name_left', 'highway_left', 'other_tags_left', 'points']]
name_list = ['osm_id', 'name', 'highway', 'other_tags', 'points']
out2.columns = name_list
# out2.to_file(rf'{folder}/crossing_lines_interactors_on_curb.geojson', driver='GeoJSON')
# fin for now

# re-id the island here? CHECK:
# TODO: active integration of the line crossing lines parsed directly from the osm file?


