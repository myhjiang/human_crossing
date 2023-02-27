'''August 2022 version
get all the geoms out of the osm file'''

import json

import geopandas as gpd
import networkx as nx
import numpy as np
import ogr
import osgeo.gdal as gdal
import pandas as pd
from shapely.geometry import *
import shapely

# print(gpd.__version__)
# print(shapely.__version__)
# print(gdal.VersionInfo())
# quit()

# folder 
base_folder = r'..\example_1'
folder_temp = rf'{base_folder}\temp'

# read QGIS setup json
with open(r"qgis_env.json", 'r') as f:
    env_dict = json.load(f)
# read param json 
with open(rf'{base_folder}\param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
size = param_dict['size_code']
# decide which scale folder the processing result goes by the scale
base_folder = rf"{base_folder}\data"
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}\500'
else:
    scale = 1000
    folder = rf'{base_folder}\1000'


# might change? not in json yet CHECK:
street_selection_list = ['primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'service', 'trunk', 'trunk_link', 'busway', 'residential']
# TODO point amenity list
amenity_list = ['bank', 'pharmacy', 'hospital', 'social_facility', 'fountain', 'police', 'post_office', 'townhall', 'toilet']
# defaults
lane_dict = {"primary": 2, "secondary": 2, "tertiary": 1, 'service':1, 'residential': 1, 'primary_link': 1, 'secondary_link': 1, "tertiary_link":1, "trunk": 1, 'trunk_link':1, "busway": 1, 'residential':1,"cycleway": 0.5, None: 1}

# data files
osm_file = rf'{base_folder}\map.osm'

# -------- get data from osm ---------------
driver = ogr.GetDriverByName('OSM')
data = driver.Open(osm_file)
line_layer = data.GetLayer('lines')
point_layer = data.GetLayer('points')
polygon_layer = data.GetLayer('multipolygons')
line_features = [x for x in line_layer]
point_features = [x for x in point_layer]
polygon_features = [x for x in polygon_layer]

# parse property from tags
def parseTags(tagstr, tagname):
    try:
        if tagname in tagstr:
            feat = [x for x in tagstr.split(',') if tagname in x][0]
            content = feat[feat.rfind('>')+2:feat.rfind('"')] 
            return content
        else:
            return ''
    except:
        return ''

# lines: street, zebra, sidewalk, cycleway
line_list = []
for feature in line_features:
    data = feature.ExportToJson(as_object=True)
    osm_id = data['properties']['osm_id']
    name = data['properties']['name']
    highway = data['properties']['highway']
    other_tags = data['properties']['other_tags']
    geom = data['geometry']
    if geom['type'] == 'LineString':
        shapely_geo = LineString(geom['coordinates'])
        # TODO remove the "private" service roads
        line_list.append([osm_id, name, highway, other_tags, shapely_geo])
gdf = gpd.GeoDataFrame(line_list, columns=['osm_id', 'name', 'highway', 'other_tags', 'geometry'], crs={'init': 'epsg:4326'}).to_crs(epsg=epsg)

# street
streets_df = gdf[gdf['highway'].isin(street_selection_list)]
# remove some little streets
streets_df = streets_df[~(streets_df['other_tags'].apply(parseTags, args=('access',))=='private')]
streets_df.to_file(rf'{base_folder}\streets.geojson', driver='GeoJSON')
# crossing lines
crossing_lines_df = gdf[(gdf['highway']=='footway') & (gdf['other_tags'].apply(parseTags, args=('footway',))=='crossing')]
if len(crossing_lines_df) > 0:
    crossing_lines_df.to_file(rf'{base_folder}\crossing_lines.geojson', driver='GeoJSON')
    pass
# sidewalk lines 
sidewalk_line_df = gdf[(gdf['highway']=='footway') & 
                        (gdf['other_tags'].apply(parseTags, args=('footway',))!='crossing')]  # CHECK
if len(sidewalk_line_df) > 0:
    sidewalk_line_df.to_file(rf'{base_folder}\sidewalk_lines.geojson', driver='GeoJSON')
# cycleway lines TODO:

point_list = []
for feature in point_features:
    data = feature.ExportToJson(as_object=True)
    osm_id = data['properties']['osm_id']
    name = data['properties']['name']
    highway = data['properties']['highway']
    other_tags = data['properties']['other_tags']
    geom = data['geometry']
    shapely_geo = Point(geom['coordinates'])
    point_list.append([osm_id, name, highway, other_tags, shapely_geo])
gdf = gpd.GeoDataFrame(point_list, columns=['osm_id', 'name', 'highway','other_tags', 'geometry'], crs={'init': 'epsg:4326'}).to_crs(epsg=epsg)
# crossing points
crossing_df = gdf[gdf['highway']=='crossing']
crossing_df.to_file(rf'{base_folder}\crossing_points.geojson', driver='GeoJSON')
# point amenity
try:
    amenity_df = gdf[gdf['other_tags'].apply(parseTags, args=('amenity',)).isin(amenity_list)]
    amenity_df.to_file(rf'{base_folder}\point_POI.geojson', driver='GeoJSON')
except:
    pass
# bus stops
try:
    # CHECK: there are multiple ways to tag a bus stop though, which ones should I take?
    busstop_df = gdf[(gdf['other_tags'].apply(parseTags, args=('public_transport',))=='stop_position') | (gdf['highway']=='bus_stop')]
    busstop_df.to_file(rf'{base_folder}\bus_stop.geojson', driver='GeoJSON')
    pass
except:
    pass
# TODO: take out the bus route (multilinestring) too

# polygons
polygon_list = []
for feature in polygon_features:
    data = feature.ExportToJson(as_object=True)
    osm_id = data['properties']['osm_id']
    osm_way_id = data['properties']['osm_way_id']
    name = data['properties']['name']
    geom = data['geometry']
    amenity = data['properties']['amenity']
    building = data['properties']['building']
    other_tags = data['properties']['other_tags']
    # TODO: those grass tags, incomplete
    landuse = data['properties']['landuse']
    leisure = data['properties']['leisure']
    temp_list = []
    for item in geom['coordinates'][0]:
        temp_list.append(Polygon(item))
    shapely_geo = MultiPolygon(temp_list)
    polygon_list.append([osm_id, osm_way_id, name, amenity, building, landuse, leisure, other_tags, shapely_geo])
gdf = gpd.GeoDataFrame(polygon_list, columns=['osm_id', 'osm_way_id', 'name', 'amenity', 'building', 'landuse', 'leisure', 'other_tags', 'geometry'], crs={'init': 'epsg:4326'}).to_crs(epsg=epsg)
# buildings
building_df = gdf[gdf['building'].notna()]
building_df.to_file(rf'{base_folder}\buildings.geojson', driver='GeoJSON')
# parkings
parking_df = gdf[gdf['amenity'].str.contains('parkingbus', na=False)]
if len(parking_df) > 0:
    parking_df.to_file(rf'{base_folder}\parkings.geojson', driver='GeoJSON')
# greens
grass_df = gdf[gdf['landuse'].str.contains('grass', na=False) | gdf['leisure'].str.contains('garden', na=False)]
if len(grass_df) > 0:
    grass_df.to_file(rf'{base_folder}\green.geojson', driver='GeoJSON')
# sidewalk area
sidewalk_area_df = gdf[(gdf['other_tags'].apply(parseTags, args=('highway',))=='footway') & (gdf['other_tags'].apply(parseTags, args=('footway',))=='sidewalk')]
if len(sidewalk_area_df) > 0:
    # FUCK: the exterior / ring thing
    df = sidewalk_area_df.explode(index_parts=False)
    df.reset_index(inplace=True)
    df['area'] = df.geometry.envelope.area
    df1 = df.sort_values(['index', 'area'], ascending=[False, False])
    df1['geom_shift'] = df1['geometry'].shift(-1)
    df1['index_shift'] = df1['index'].shift(-1)
    df1['ring'] = df1.apply(lambda x: x.geometry.difference(x.geom_shift) if x['index'] == x.index_shift else x.geometry, axis=1)
    df1.drop_duplicates(subset=['index'], keep='first', inplace=True)
    df1.set_geometry('ring', inplace=True)
    df1.drop(columns=['geometry', 'geom_shift', 'index_shift', 'area'], inplace=True)
    df1.columns = [*df1.columns[:-1], 'geometry']
    df1.set_geometry('geometry', inplace=True)
    df1.to_file(rf'{base_folder}\sidewalk_area.geojson', driver='GeoJSON')

'''first step of street processing put here because, need check at the end for lane tagging'''
# -------------------------------------------------------------
# do lane estimation regardless of whether there is an sidewalk area or not
# parse property from tags
def get_lanes_from_tags(tagstr):
    # something could go wrong with the tag though, sometimes it's empty? TODO 
    try:
        if 'lanes' in tagstr:
            feat = [x for x in tagstr.split(',') if '"lanes"' in x][0]
            lanes = feat[feat.rfind('>')+2:feat.rfind('"')] 
            return int(lanes)
    except:
        return np.nan
def recurse_node(G, z, node, edge_list, df, value):
    '''it recursively pass on the lane information to connected streets'''
    '''but I cannot exactly why it works anymore'''
    z.append(node)
    for i in nx.all_neighbors(G, node):
        if (i not in z) and (((i, node) in edge_list) or ((node, i) in edge_list)):  # and edge(i, node) or (node, i) in unlaned_edge
            # change the lane value and take the edge off the unlaned edge
            if ((i, node) in edge_list):
                index = df.index[df['osm_id']==G[i][node]['osm_id']]
                df.loc[index, 'lanes'] = value
                edge_list.remove((i,node))
            if ((node, i) in edge_list):
                index = df.index[df['osm_id']==G[node][i]['osm_id']]
                df.loc[index, 'lanes'] = value
                edge_list.remove((node,i))
            recurse_node(G, z, i, edge_list, df, value)
# directly get lane number from tags
streets_df['lanes'] = streets_df.apply(lambda x: get_lanes_from_tags(x.other_tags), axis=1)
# first step estimation
'''service road *often* has 1 lane (bus lane, parking way etc)'''
streets_df['lanes'] = streets_df.apply(lambda x: 1 if (x.highway=='service' and pd.isnull(x.lanes))  else x.lanes, axis=1)
# second step estimation
'''if two connecting road segments have the same name, one has a lane number and the other doesn't, it gets the same number as the other, 
recurring until you go all the way with the same street name'''
streets_df['from'] = streets_df['geometry'].apply(lambda x: x.coords[0])
streets_df['to'] = streets_df['geometry'].apply(lambda x: x.coords[-1])
G = nx.from_pandas_edgelist(streets_df, 'from', 'to', ['osm_id', 'name', 'lanes'])
street_name_list = set(streets_df['name'].values)
for name in street_name_list:
    laned_edges = [(u,v) for u,v,e in G.edges(data=True) if (e['name']==name) and (~np.isnan(e['lanes']))]
    unlaned_edges = [(u,v) for u,v,e in G.edges(data=True) if (e['name']==name) and (np.isnan(e['lanes']))]
    if len(laned_edges) > 0:
        for edge in laned_edges: 
            lanes = G[edge[0]][edge[1]]['lanes']
            neighbors_0 = [edge[0]]
            neighbors_1 = [edge[1]]
            recurse_node(G, neighbors_0, edge[1], unlaned_edges, streets_df, lanes)
            recurse_node(G, neighbors_1, edge[0], unlaned_edges, streets_df, lanes)
# third estimation
'''fill with default for all the remaining ones, dictionary defined at the top'''
streets_df['lanes'] = streets_df.apply(lambda x: lane_dict[x.highway] if (pd.isnull(x.lanes)) else x.lanes, axis=1)
streets_df.drop(columns=['from', 'to'], inplace=True)
# estimation done
# out in the base folder
streets_df.to_file(rf'{base_folder}\streets_laned.geojson', driver='GeoJSON')


"""some street preprocessing before it goes into scale specific stuff"""

# CHECK: what if I don't displace the streets, can it be properly apart? 
# ---------------- displace streets --------------
import os
import sys

# get the distance to be displaced
lane_width = param_dict['lane_width']
line_width_meter = scale*param_dict['line_width'] / 1000.0
line_gap_meter = scale*param_dict['line_gap'] / 1000.0
displace_dist = lane_width + 2*line_width_meter + line_width_meter 
# ---------------- QGIS GOES LATER OTHERWISE BIG MESS UP WITH THE OGR STUFF BEFORE --------
os.environ['PROJ_LIB'] = rf"{env_dict['PROJ_LIB']}"
os.environ['PROJ_DEBUG'] = rf"{env_dict['PROJ_DEBUG']}"
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = rf"{env_dict['QT_QPA_PLATFORM_PLUGIN_PATH']}"
for apath in env_dict['PathAppend']:
    os.environ['PATH'] += rf"{apath}"
from qgis.analysis import QgsNativeAlgorithms
from qgis.core import (QgsApplication, QgsFeature, QgsField, QgsGeometry,
                       QgsPoint, QgsPointXY, QgsProcessingContext,
                       QgsProcessingFeedback, QgsProcessingUtils,
                       QgsVectorLayer)

QgsApplication.setPrefixPath(rf"{env_dict['setPrefixPath']}", True)
qgs = QgsApplication([], False)
qgs.initQgis()
sys.path.append(rf"{env_dict['PathAppend']}")
import processing
from processing.core.Processing import Processing
from qgis.analysis import QgsNativeAlgorithms

Processing.initialize()
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
context = QgsProcessingContext() 
feedback = QgsProcessingFeedback()
# --------------- END QIGS --------------------
# displace: those little parameters like a and b, by default?
displaced = processing.run('grass7:v.generalize',
            {'input': rf'{base_folder}\streets_laned.geojson',
            'output': rf'{base_folder}\streets_displaced.geojson',
            'error': rf'{folder_temp}\error.geojson',
            'method': 12, # displacement
            'threshold': displace_dist,  # seem not consistent with graphic modeller??
            'alpha': 3,  
            'beta': 3,  
            'GRASS_OUTPUT_TYPE_PARAMETER': 2,
            '-overwrite': True,
            'iterations': 10}, context=context)


# -------------- fix street and snap dangling ends to extent --------------------
extent_df = gpd.read_file(rf'{base_folder}\big_extent.geojson')
streets_df = gpd.read_file(rf'{base_folder}\streets_displaced.geojson')
extent_df['buffer'] = extent_df.geometry.buffer(20, cap_style=2)
extent_df.set_geometry('buffer', inplace=True)
extent_df['boundary'] = extent_df.geometry.boundary

streets_df['extent_intersection_pt'] = streets_df['geometry'].intersection(extent_df.boundary.tolist()[0])
streets_df.set_geometry('extent_intersection_pt', inplace=True)
streets_df['extent_empty_flag'] = streets_df.geometry.apply(lambda x: 1 if x.is_empty else 0)
streets_df.set_geometry('geometry', inplace=True)

def find_hanging(df, line):
    try:
        start_point, end_point = line.boundary
        df_temp = df.drop(df[df['geometry']==line].index)
        points = line.intersection(df_temp['geometry'].unary_union)  # get a bunch of points
        if isinstance(points, Point):
            return list(x for x in [start_point, end_point] if x!=points)[0]
        if isinstance(points, MultiPoint):
            if ((start_point not in points) or (end_point not in points)):
                if start_point not in points: 
                    return start_point
                else:
                    return end_point
            else:
                return Point()
    except:
        return Point()
    
streets_df['hanging'] = streets_df.apply(lambda x: find_hanging(streets_df, x.geometry) if ((x.extent_empty_flag==1) and (x['name']!=None)) else Point(), axis=1)

streets_df['hanging_flag'] = streets_df.apply(lambda x: 0 if (x['hanging'].is_empty) else 1, axis=1)
# TODO this hanging condition, missed bus line, or other service line that might be really "hanging"

# extend the hanging line to extent
def getExtrapoledLine(p1,p2):
    'Creates a line extrapoled in p1->p2 direction'
    EXTRAPOL_RATIO = 100  # TODO check this param
    a = p1
    b = (p1[0]+EXTRAPOL_RATIO*(p2[0]-p1[0]), p1[1]+EXTRAPOL_RATIO*(p2[1]-p1[1]) )
    return LineString([a,b])

def extend_to_extent(line, point, box):
    prev_point = []
    point = list(point.coords[0])
    l_coords = list(line.coords)
    start_point, end_point = list(l_coords[0]), list(l_coords[-1])
    if point == start_point:
        prev_point = list(line.coords)[1]
    elif point == end_point:
        prev_point = list(line.coords)[-2]
    else:
        print('failure')
        return line

    long_line = getExtrapoledLine(prev_point, point)
    if box.intersects(long_line):
        intersection_points = box.intersection(long_line)
        try:  # CHECK: WHY IS THIS
            new_point_coords = list(intersection_points.coords)[0]
        except:
            return line
    else:
        print('not long enough')
        return line
    l_coords.append(new_point_coords)
    new_extended_line = LineString(l_coords)
    return new_extended_line

streets_df['geometry'] = streets_df.apply(lambda x: extend_to_extent(x.geometry, x.hanging, extent_df.geometry.boundary.unary_union) if (x.hanging_flag==1) else x.geometry, axis=1)

# cut street to extent
streets_df['geometry'] = streets_df.apply(lambda x: x.geometry.intersection(extent_df.geometry.unary_union), axis=1)
out = streets_df[['osm_id', 'name', 'highway', 'other_tags', 'lanes', 'geometry']]
out.to_file(rf'{base_folder}\snapped_streets.geojson', driver='GeoJSON')

# fin

# MANUAL: check lane estimation and dangling street snap
