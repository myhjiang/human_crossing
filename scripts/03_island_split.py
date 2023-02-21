"""an improved way hopefully with less qgis components
TODO: this is pretty much stand alone, doesn't have to be done now for the sidewalk automation
the old script still work. (03_split_island_2)"""

import json
from macpath import join

import geopandas as gpd
import numpy as np
from shapely import affinity
from shapely.geometry import (LineString, MultiLineString, MultiPoint,
                              MultiPolygon, Point, Polygon)
from shapely.ops import nearest_points

# folder 
base_folder = r'..\example_1\data'
folder_temp = rf'{base_folder}\temp'
# read param json 
with open(rf'{base_folder}\param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
size = param_dict['size_code']
# decide which scale folder the processing result goes by the scale
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}\500'
else:
    scale = 1000
    folder = rf'{base_folder}\1000'

# files
island_df = gpd.read_file(rf"{folder}\islands_full.geojson")
crossing_df = gpd.read_file(rf"{folder}\crossing_lines.geojson")
extent_df = gpd.read_file(rf"{base_folder}\big_extent.geojson")

# TODO: clip and remove the crossing lines out of extent



# second hand param NOTSURE
move_dist = param_dict['area_gap'] / 2.0

# intersect crossing lines with island area => multipoints
# grow crossing lines a little bit longer
def getExtrapoledLine(p1,p2):
    'Creates a line extrapoled in p1->p2 and p2 <- p1 direction'
    length = p1.distance(p2) # in meter
    EXTRAPOL_RATIO = (length + 1) / length
    a = p1
    b = (p1.x+EXTRAPOL_RATIO*(p2.x-p1.x), p1.y+EXTRAPOL_RATIO*(p2.y-p1.y) )
    a = (p2.x+EXTRAPOL_RATIO*(p1.x-p2.x), p2.y+EXTRAPOL_RATIO*(p1.y-p2.y) )
    return LineString([a,b])
crossing_df['extended'] = crossing_df.geometry.apply(lambda x: getExtrapoledLine(x.boundary[0], x.boundary[1]))
crossing_df.set_geometry('extended', inplace=True)
crossing_df['geom_copy'] = crossing_df['extended']
crossing_df.drop(columns=['geometry'], inplace=True)
island_df['intersection'] = island_df.geometry.boundary.intersection(crossing_df.extended.unary_union)
island_df['intersection_count'] = island_df['intersection'].apply(lambda x: len(x.geoms) if x.geom_type == 'MultiPoint' else 0)

'''count = 2 -> regular split
   count = 3 -> triangle split and remove the middle
   count even but > 2 -> big median scenario, double regular split 
   odd count > 3 ?? is that possible? NOTSURE'''
# a little join to get the crossing line geometry involved
join_df = gpd.sjoin(island_df, crossing_df, how="left")
if 'fid_left' in join_df.columns:  # for legacy code only
    join_df.rename(columns={'fid_left':'level_1'}, inplace=True)
if 'fid' in join_df.columns:  # for legacy code only
    join_df.rename(columns={'fid':'level_1'}, inplace=True)

join_df = join_df[['level_1', 'geometry', 'intersection', 'intersection_count', 'osm_id', 'geom_copy', 'split']]
join_df.set_geometry('geom_copy', inplace=True)
# before aggregate, save the crossing ids each island is connected to, for later
# make a dict here with the 'level_1' as key (island id), and will find all the crossing ids later when output
id_df = join_df.groupby('level_1')['osm_id'].apply(list).reset_index(name='crossing_ids')
# aggregate together
join_df = join_df.dissolve(by='level_1', aggfunc='first')
join_df.set_geometry('geometry', inplace=True)

# split geometry
def splitPolygonByLine(polygon, line):
    '''to multi polygon'''
    line_buffer = line.buffer(1e-3)
    new_polygon = polygon.difference(line_buffer)
    return new_polygon

def azimuth(point1, point2):
    angle = np.arctan2(point2.x - point1.x, point2.y - point1.y)
    return np.degrees(angle) if angle >= 0 else np.degrees(angle) + 360

def bearing(line1, line2, point1, point2):
    '''collective bearing to move the lines'''
    b1 = azimuth(Point(line1.coords[0]), Point(line1.coords[-1]))
    b2 = azimuth(Point(line2.coords[0]), Point(line2.coords[-1]))
    b3 = azimuth(point1, point2)
    b1, b2 = [x-180 if x>180 else x for x in [b1, b2]]
    b_avg = (b1 + b2) / 2 if abs(b1-b2) <30 else b3  # NOTSURE if this is correct  
    # print(b1, b2, b3, b_avg)
    return b_avg

def splitIsland(x):
    '''the x is the same x in apply lambda x.geometry'''
    # non crossing island
    if x.intersection_count == 0:
        return x.geometry
    # regular split
    points = x.geom_copy.intersection(x.geometry.boundary)
    if x.intersection_count == 2:
        # print(x.osm_id)
        # get the two intersection point to make a line
        line = LineString([points[0], points[1]])
        split = splitPolygonByLine(x.geometry, line)
        # move the two split parts, bearing from the two crossing lines combined
        b_avg = bearing(x.geom_copy[0], x.geom_copy[-1], points[0], points[1])
        # move
        poly_list = []
        for poly in split:
            x_sign = 1; y_sign = 1
            if poly.centroid.x < x.geometry.centroid.x:
                x_sign = -1  # part moves left
            if poly.centroid.y < x.geometry.centroid.y:
                y_sign = -1  # part moves down
            x_move = move_dist * abs(np.cos(np.radians(b_avg))) * x_sign 
            y_move = move_dist * np.sin(np.radians(b_avg)) * y_sign 
            # print(x_move, y_move, b_avg)
            poly = affinity.translate(poly, x_move, y_move)
            poly_list.append(poly)
        split = MultiPolygon(poly_list)
        return split
    # big median split NOTE: I can only do the 4 point scenario right now
    # TODO: the parts need to shrink, otherwise when you have two head-to-head median, the little part will meet at the middle of the street
    elif x.intersection_count > 2 and x.intersection_count % 2 ==0 :
        p1 = points[0]
        p2 = nearest_points(p1, points.difference(p1))[1]
        p3 = points.difference(p1).difference(p2)[0]
        p4 = nearest_points(p3, points.difference(p1).difference(p2).difference(p3))[1]
        # p1 and p2 in pairs to make line 1, and p3 with p4 to make line 2
        line1 = LineString([p1, p2]); line2=LineString([p3, p4])
        pair_dict = {}
        pair_dict_reverse = {}
        for point in [p1, p2, p3, p4]:
            nearest_line = min([line for line in x.geom_copy], key=lambda x: x.distance(point))
            pair_dict[f"{point}"] = nearest_line
            pair_dict_reverse[f"{nearest_line}"] = point
        # pair_dict = {'p1': line object} ; pair_dict_reverse = {'line1' : point object}
        split = splitPolygonByLine(x.geometry, MultiLineString([line1, line2]))
        # bearings for each of the lines NOTE: now there are only two lines
        bv1 = bearing(pair_dict[str(p1)], pair_dict[str(p2)], p1, p2)  # for line1, made of p1 p2, not necessarily the left
        bv2 = bearing(pair_dict[str(p3)], pair_dict[str(p4)], p3, p4)  # same, for line 2
        bearing_dict = {f"{line1}": bv1, f"{line2}": bv2}
        # the middle one don't move, the two ends parts go further 
        left_x = min([line1.centroid.x, line2.centroid.x]); right_x = max([line1.centroid.x, line2.centroid.x])
        low_y = min([line1.centroid.y, line2.centroid.y]); top_y = max([line1.centroid.y, line2.centroid.y])
        poly_list = []
        if split.geom_type != 'MultiPolygon':
            return split
        for poly in split:
            x_sign = 1; y_sign = 1
            if poly.centroid.x < left_x:
                x_sign = -1  # part moves left
            if poly.centroid.y < low_y:
                y_sign = -1  # part moves down
            # the middle one wont move (middle one is centroid x y both within range)
            # and the middle part will be cut a bit shorter to be away from the zebra end
            if poly.centroid.x > left_x and poly.centroid.x < right_x and poly.centroid.y > low_y and poly.centroid.y < top_y:
                line1_buff = line1.buffer(move_dist)
                line2_buff = line2.buffer(move_dist)
                poly = poly.difference(line1_buff.union(line2_buff))
                poly_list.append(poly)
                continue
            # to move with the correct / corresponding b_avg
            b_move = bearing_dict[str(min([line1, line2], key=(lambda x: poly.distance(x))))]
            x_move = move_dist * abs(np.cos(np.radians(b_move))) * x_sign * 2
            y_move = move_dist * np.sin(np.radians(b_move)) * y_sign * 2
            poly = affinity.translate(poly, x_move, y_move)
            poly_list.append(poly)
        split = MultiPolygon(poly_list)
        return split
    # triangular split TODO: move the three parts away from each other, and remove the middle part
    # NOTE:this is not tested !!
    elif x.intersection_count == 3:
        p1 = points[0]; p2 = points[1]; p3 = points[2]
        line1 = LineString([p1, p2]); line2=LineString([p2, p3]); line3 = LineString([p1,p3])
        # there is no avg bearing for this, because the zebra is not in the same direction with the intersection lines
        b1 = azimuth(p1, p2); b2 = azimuth(p2, p3); b3 = azimuth(p1, p3)
        bearing_dict = {f"{line1}": b1, f"{line2}": b2, f"{line3}": b3}
        split = splitPolygonByLine(x.geometry, MultiLineString([line1, line2, line3]))
        left_x = min([line1.centroid.x, line2.centroid.x, line3.centroid.x]); right_x = max([line1.centroid.x, line2.centroid.x, line3.centroid.x])
        low_y = min([line1.centroid.y, line2.centroid.y, line3.centroid.y]); top_y = max([line1.centroid.y, line2.centroid.y, line3.centroid.y])
        poly_list = []
        for poly in split:
            x_sign = 1; y_sign = 1
            # the middle part get removed (not added to the list)
            if poly.centroid.x > left_x and poly.centroid.x < right_x and poly.centroid.y > low_y and poly.centroid.y < top_y:
                continue
            if poly.centroid.x < left_x:
                x_sign = -1  # part moves left
            if poly.centroid.y < low_y:
                y_sign = -1  # part moves down
            # move
            b_move = bearing_dict[str(min([line1, line2], key=(lambda x: poly.distance(x))))]
            x_move = move_dist * abs(np.cos(np.radians(b_move))) * x_sign * 2
            y_move = move_dist * np.sin(np.radians(b_move)) * y_sign * 2
            poly = affinity.translate(poly, x_move, y_move)
            poly_list.append(poly)
        split = MultiPolygon(poly_list)
        return split
    else:
        print((x.intersection_count))
        return x.geometry
        pass
    

join_df['test'] = join_df.apply(lambda x: splitIsland(x) if x.split==1 else x.geometry, axis=1)

# make interactors in the middle of the split, similar to the split function
def makeInteractors(x):
    """the x is the same x in apply lambda x.geometry,
    returns point / MultiPoint  TODO: make this unnified. """ 
    # non crossing island
    if x.intersection_count == 0:
        # make an interactor in the middle / centroid
        return x.geometry.centroid
    # regular split
    points = x.geom_copy.intersection(x.geometry.boundary)
    if x.intersection_count == 2:
        # get the two intersection point to make a line, and the interactor is the split line centroid
        line = LineString([points[0], points[1]])
        return line.centroid
    # big median split NOTE: I can only do the 4 point scenario right now
    elif x.intersection_count > 2 and x.intersection_count % 2 ==0 :
        p1 = points[0]
        p2 = nearest_points(p1, points.difference(p1))[1]
        p3 = points.difference(p1).difference(p2)[0]
        p4 = nearest_points(p3, points.difference(p1).difference(p2).difference(p3))[1]
        # p1 and p2 in pairs to make line 1, and p3 with p4 to make line 2
        line1 = LineString([p1, p2]); line2=LineString([p3, p4])
        return MultiPoint([line1.centroid, line2.centroid])
    # triangular split, find the centroid of the middle triangle
    # NOTE:this is not tested !!
    elif x.intersection_count == 3:
        p1 = points[0]; p2 = points[1]; p3 = points[2]
        poly = Polygon([p1, p2, p3])
        return poly.centroid
join_df['interactors'] = join_df.apply(lambda x: makeInteractors(x), axis=1)

# get the crossing ids for the island interactor
join_df = join_df.merge(id_df, on='level_1')
# then get the street ids from the crossing file
def getStreetIDs(x, crossing_df):
    '''same x as apply lambda x.geometry'''
    street_id_list = []
    for id in x.crossing_ids:
        # df.loc[df['B'] == 3, 'A']
        print(crossing_df.loc[crossing_df['osm_id']==id, 'street_ids'].values.tolist())
        try: 
            street_id = crossing_df.loc[crossing_df['osm_id']==id, 'street_ids'].values.tolist()[0]
            street_id_list.append(street_id)
        except:
            street_id_list.append('-9999')
    street_id_list = list(set(street_id_list))
    return street_id_list

join_df['street_ids'] = join_df.apply(lambda x: getStreetIDs(x, crossing_df), axis=1)
join_df['street_ids'] = join_df['street_ids'].apply(lambda x: ','.join(map(str, sorted(x))))

# out island file
join_df.reset_index(inplace=True)
join_df.set_geometry('test', inplace=True)
out = join_df[['level_1', 'test', 'street_ids']]
out.to_file(rf'{folder}\island_split.geojson', driver='GeoJSON')

# out interactor file
join_df.set_geometry('interactors', inplace=True)
out2 = join_df[['level_1', 'interactors', 'street_ids']]
out2['highway'] = 'island'
out2.to_file(rf'{folder}\island_interactors_1.geojson', driver='GeoJSON')

# fin
