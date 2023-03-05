'''street processing after manually fixing lane numbers and dangling lines'''
import json
import os.path

import geopandas as gpd
from shapely.geometry import Polygon

import warnings
warnings.filterwarnings('ignore')

import argparse
parser = argparse.ArgumentParser(description='set folder')
parser.add_argument('folder', metavar='fd', type=str)
args = parser.parse_args()

# folder 
# folder = r'../example_2'
base_folder = rf"../{args.folder}"

# # read QGIS setup json
# with open(r"qgis_env.json", 'r') as f:
#     env_dict = json.load(f)
# read param json 
with open(rf'{base_folder}/param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
size = param_dict['size_code']
# size = 'A5'
# decide which scale folder the processing result goes by the scale
base_folder = rf"{base_folder}/data"
folder_temp = rf'{base_folder}/temp'
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}/500'
else:
    scale = 1000
    folder = rf'{base_folder}/1000'

# files
streets_df = gpd.read_file(rf'{base_folder}/snapped_streets.geojson')
# remove None geometry #CHECK: why?? there should'nt be None???
streets_df = streets_df[streets_df['geometry']!=None]


'''with sidewalk or not, the first few steps are all the same:
buffer to area
island estimation'''
# ---------------------------------
# --------------------------------- to area -----------------------------
lane_width = param_dict['lane_width']
line_width_meter = scale*param_dict['line_width'] / 1000.0
streets_df['dist'] = streets_df.lanes.apply(lambda x: (lane_width*x+2*line_width_meter)/2)
streets_df['buffer'] = streets_df.apply(lambda x: x.geometry.buffer(x.dist), axis=1)
streets_df.set_geometry('buffer', inplace=True)
streets_df.drop(columns=['geometry'], inplace=True)
merged = streets_df.unary_union
d = {'geometry': [merged]}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}').to_crs(epsg=epsg)
gdf.to_file(rf'{folder_temp}/buffer_streets.geojson', driver='GeoJSON')

# QGIS STUFF
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
prefixpath = '/srv/conda/envs/notebook/bin/'
from qgis.analysis import QgsNativeAlgorithms
from qgis.core import (QgsApplication, QgsFeature, QgsField, QgsGeometry,
                       QgsPoint, QgsPointXY, QgsProcessingContext,
                       QgsProcessingFeedback, QgsProcessingUtils,
                       QgsVectorLayer)

QgsApplication.setPrefixPath(prefixpath, True)
qgs = QgsApplication([], False)
qgs.initQgis()
sys.path.append(rf"{env_dict['PathAppend']}")
import processing
from processing.core.Processing import Processing
from qgis.analysis import QgsNativeAlgorithms

Processing.initialize()
context = QgsProcessingContext() 
feedback = QgsProcessingFeedback()
# ---------------- END QGIS STUFF ------------------------------
# remove holes
# NOTSURE the way the smallest area is defined? or is this step needed at all? 
icon_space = scale*(param_dict['icon_size']) / 1000.0
removed = processing.run('native:deleteholes', 
        {'INPUT': rf'{folder_temp}/buffer_streets.geojson',
        'MIN_AREA': icon_space*icon_space*4,
        'OUTPUT': rf'{folder_temp}/t2.geojson'})

# remove standalone little street items? TODO:

# smooth
# TODO: really want PAEK like in arc but couldn't get a real implementation working...
smoothed = processing.run('native:smoothgeometry', 
            {'INPUT':removed['OUTPUT'],'ITERATIONS':4,  # 10 gets really slow. for faster purposes use 4 and arc PAEK.
            'MAX_ANGLE':180,'OFFSET':0.25,  # the actual range is [0.0 - 1.0] but qgis doesnot want anything larger than 0.5
            'OUTPUT':rf'{folder}/street_area.geojson'})
# no second smoothing otherwise crash (complex json crash)

# ---------------------------------
# --------------------------------- get island -----------------------------
extent_df = gpd.read_file(rf"{base_folder}/big_extent.geojson")
small_extent = gpd.read_file(rf"{base_folder}/extent_{size}.geojson")
street_area_df = gpd.read_file(rf"{folder}/street_area.geojson")
try:
    buildings_df = gpd.read_file(rf"{base_folder}/buildings.geojson")
except: buildings_df = None
try:
    green_df = gpd.read_file(rf"{base_folder}/green.geojson")
except: green_df = None
# cut
# CHECK: what if there is no island then?
diff = extent_df.geometry.unary_union.difference(street_area_df.geometry.unary_union)  # multi polygon 
d = {'geometry': [diff]}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
gdf = gdf.explode(index_parts=True)
# if green_df is not None:
#     merged = buildings_df.geometry.unary_union.union(green_df.geometry.unary_union)
#     gdf = gdf[gdf.geometry.disjoint(merged)]
# else:
gdf = gdf[gdf.geometry.disjoint(buildings_df.geometry.unary_union)]
# out
try:
    gdf['split'] = 0
    gdf.to_file(rf"{folder}/islands_full.geojson")
except:
    pass

try:
    island_df = gpd.read_file(rf"{folder}/islands_full.geojson")
except:
    island_df = None

# remove the islands that is out of extent
if island_df is not None:
    island_df = island_df[island_df.geometry.intersects(small_extent.geometry.unary_union)]
    if len(island_df) == 0:
        # remove the file!
        os.remove(rf"{folder}/islands_full.geojson")
        island_df = None
    island_df.to_file(rf"{folder}/islands_full.geojson")

'''if there is sidewalk area data, 
will need to redo the street based on the sidewalk'''
# if sidewalk area data exists
if os.path.exists(rf"{base_folder}/sidewalk_area.geojson"):
    sidewalk_df = gpd.read_file(rf"{base_folder}/sidewalk_area.geojson")
    # carve out street area based on sidewalk
    # NOTSURE: if the sidewalk data is not complete or anything, going to be very problematic
    merged = buildings_df.geometry.unary_union.union(sidewalk_df.geometry.unary_union)  # multipolygon
    # merged = merged.intersection(small_extent.geometry.unary_union)
    if green_df is not None:
        merged = merged.union(green_df.geometry.unary_union)
    cut = extent_df.geometry.unary_union.difference(merged)
    d = {'geometry': [cut]}
    gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
    gdf = gdf.explode(index_parts=True)
    gdf.to_file(rf"{folder_temp}/cut.geojson")

    # only take the big middle piece, other smaller / not connected pieces will be discarded.
    # NOTSURE what condition to use here? biggest area + intersectng island? 
    # TODO: if no island, need a different condition
    if island_df is not None:
        gdf = gdf[gdf.geometry.intersects(island_df.geometry.unary_union)]
    # merge with island, and TODO: get rid of little bits / holes
        gdf.geometry = gdf.geometry.union(island_df.geometry.unary_union)
    else: 
        # CHECK: this condition, disjoint building or intersects streets?
        gdf = gdf[gdf.geometry.intersects(street_area_df.geometry.unary_union)]
        # gdf.to_file(rf"{folder_temp}/cut.geojson")
    # out, street and the "boundary filled"
    gdf.to_file(rf"{folder}/street_from_sidewalk.geojson")
    gdf['boundary'] = gdf.geometry.boundary
    gdf.set_geometry('boundary', inplace=True)
    out = gdf[['boundary']]
    out.to_file(rf"{folder}/street_boundary_filled.geojson")
    # carve out island to have the (original) boundary NOTSURE is this needed after all?
    gdf.set_geometry('geometry', inplace=True)
    if island_df is not None:
        diff = gdf.geometry.unary_union.difference(island_df.geometry.unary_union)
    else: diff = gdf.geometry.unary_union
    boundary = diff.boundary
    d = {'geometry': [boundary]}
    gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
    gdf.to_file(rf"{folder}/street_boundary_original.geojson")
    # finally, make a smoother / generalized sidewalk area for later use (no ruggy edges at the building side)
    sidewalk_df.geometry = sidewalk_df.geometry.buffer(10, cap_style=3, join_style=2).buffer(-10, cap_style=3, join_style=2)
    sidewalk_df.to_file(rf"{folder}/sidewalk_gen.geojson")

# if there is no sidewalk areas
# directly get the filled and original street boundary from the street areas
else:
    street_area_df['move_out'] = street_area_df.geometry.buffer(0.5).boundary
    street_area_df['boundary'] = street_area_df.geometry.boundary  
    street_area_df.set_geometry('boundary', inplace=True)
    out = street_area_df[['boundary']]
    out.to_file(rf"{folder}/street_boundary_original.geojson")
    street_area_df.set_geometry('geometry', inplace=True)
    try: 
        merged = street_area_df.move_out.unary_union.union(island_df.geometry.unary_union)
        boundary = merged.boundary
        d = {'geometry': [boundary]}
        gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
        gdf = gdf.explode(index_parts=True)
        gdf.to_file(rf"{folder}/street_boundary_filled.geojson")
    except:
        street_area_df.set_geometry('move_out', inplace=True)
        out = street_area_df[['move_out']]
        out.to_file(rf"{folder}/street_boundary_filled.geojson")

# fin
print("finished")