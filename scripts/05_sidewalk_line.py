import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiLineString

# folder 
base_folder = r'..\example_1\data'
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
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}\500'
else:
    scale = 1000
    folder = rf'{base_folder}\1000'

lane_width = param_dict['lane_width']
line_width_meter = scale*param_dict['line_width'] / 1000.0
line_gap_meter = scale*param_dict['line_gap'] / 1000.0

# files
island_df = gpd.read_file(rf"{folder}\islands_full.geojson")
crossing_df = gpd.read_file(rf"{folder}\crossing_lines.geojson")
extent_df = gpd.read_file(rf"{base_folder}\extent_{size}.geojson")
sidewalk_df = gpd.read_file(rf"{base_folder}\sidewalk_lines.geojson")
street_df = gpd.read_file(rf"{base_folder}\snapped_streets.geojson")
street_boundary = gpd.read_file(rf"{folder}\street_boundary_filled.geojson")

island_df = island_df[island_df.geometry.intersects(extent_df.geometry.unary_union)]
street_boundary = street_boundary[street_boundary.geometry.intersects(extent_df.geometry.unary_union)]

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
        this_dist = dist + line_width_meter + 0.5*x.lanes*lane_width
        sleft = x.geometry.parallel_offset(this_dist, 'left')
        sright = x.geometry.parallel_offset(this_dist, 'right')
        new_sidewalk = MultiLineString([sleft, sright])
        return new_sidewalk
street_df['sidewalkk'] = street_df.apply(lambda x: sidewalkFromStreet(x, line_gap_meter), axis=1)
# prepare this for later
st_sw_df = street_df[~street_df['sidewalkk'].isna()]
st_sw_df.set_geometry('sidewalkk', inplace=True)
st_sw_df.drop(columns=['geometry'], inplace=True)
st_sw_df['on_island'] = st_sw_df.apply(lambda x: x.sidewalkk.intersects(island_df.geometry.unary_union), axis=1)
st_sw_df['too_short'] = st_sw_df.apply(lambda x: True if x.sidewalkk.length < 5 else False, axis=1)
st_sw_df = st_sw_df[(st_sw_df['on_island'] == False) & (st_sw_df['too_short'] == False)]
street_sidewalks = st_sw_df.rename(columns={"sidewalkk": "geometry"})


"""the sidewalk lines"""
# displace the sidewalk lines with the street
# first remove the little parts and the parts on the island
sidewalk_df.geometry = sidewalk_df.geometry.intersection(extent_df.geometry.unary_union)
sidewalk_df = sidewalk_df[sidewalk_df.geometry.is_empty == False]
sidewalk_df['on_island'] = sidewalk_df.apply(lambda x: x.geometry.intersects(island_df.geometry.unary_union), axis=1)
sidewalk_df['too_short'] = sidewalk_df.apply(lambda x: True if x.geometry.length < 5 else False, axis=1)
sidewalk_df = sidewalk_df[(sidewalk_df['on_island'] == False) & (sidewalk_df['too_short'] == False)]
# displace 
# QGIS STUFF
import os
import sys

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
context = QgsProcessingContext() 
feedback = QgsProcessingFeedback()
# ---------------- END QGIS STUFF ------------------------------
temp_lines = street_boundary.geometry.union(sidewalk_df.geometry.unary_union).unary_union
d = {'geometry': temp_lines}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
gdf.to_file(rf'{base_folder}\temp\temp_lines.geojson', driver='GeoJSON')

displace_dist = line_gap_meter + 2*line_width_meter

displaced = processing.run('grass7:v.generalize',
            {'input': rf'{base_folder}\temp\temp_lines.geojson',
            'output': rf'{base_folder}\temp\displace_sidewalk.geojson',
            'error': rf'{folder_temp}\error2.geojson',
            'method': 12, # displacement
            'threshold': displace_dist,  # seem not consistent with graphic modeller??
            'alpha': 3,  
            'beta': 3,  
            'GRASS_OUTPUT_TYPE_PARAMETER': 2,
            '-overwrite': True,
            'iterations': 10}, context=context)
# FIXME:
# displaced_df = gpd.read_file(rf'{base_folder}\temp\displace_sidewalk.geojson')
# print(displaced_df)
# quit()

"""merge and out """
# merge the two 
sidewalk_df['buffered'] = sidewalk_df.geometry.buffer(line_gap_meter)
buffered = sidewalk_df.buffered.unary_union
street_sidewalks['cut'] = street_sidewalks.geometry.difference(buffered)
street_sidewalks.drop(columns=['geometry'], inplace=True)
street_sidewalks.rename(columns={"cut": "geometry"}, inplace=True)

sidewalk_df.drop(columns='buffered', inplace=True)
new_df = pd.concat([sidewalk_df, street_sidewalks])

# out 
out = new_df[['osm_id', 'name', 'highway', 'other_tags', 'geometry']]
out = gpd.GeoDataFrame(out, crs=f'epsg:{epsg}', geometry='geometry')
out = out[out.geometry.intersects(extent_df.geometry.unary_union)]
out.to_file(rf'{folder}\sidewalk_lines.geojson', driver='GeoJSON')

# fin for now. fix the displacement part. 
