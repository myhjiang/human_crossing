import json

# folder 
base_folder = r'..\example_1\data'
folder_temp = rf'{base_folder}\temp'
folder_sld = r'..\styles'

# read QGIS setup json
with open(r"qgis_env.json", 'r') as f:
    env_dict = json.load(f)
# read param json 
with open(rf'{base_folder}\param.json') as fp: 
    param_dict = json.load(fp)


# ---------------- QGIS STUFF ------------------------------
import sys
import os
os.environ['PROJ_LIB'] = rf"{env_dict['PROJ_LIB']}"
os.environ['PROJ_DEBUG'] = rf"{env_dict['PROJ_DEBUG']}"
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = rf"{env_dict['QT_QPA_PLATFORM_PLUGIN_PATH']}"
for apath in env_dict['PathAppend']:
    os.environ['PATH'] += rf"{apath}"
from qgis.core import QgsApplication, QgsProcessingFeedback, QgsProcessingContext, QgsProject, QgsPrintLayout, QgsLayoutItemMap, QgsRectangle, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes, QgsProcessingUtils, QgsLayoutItemLabel, QgsLayoutExporter, QgsLayoutItemPage, QgsReadWriteContext, QgsLayerTree, QgsLayerTreeNode
from PyQt5.QtXml import QDomDocument
QgsApplication.setPrefixPath(rf"{env_dict['setPrefixPath']}", True)
qgs = QgsApplication([], False)
qgs.initQgis()
sys.path.append(rf"{env_dict['PathAppend']}")

context = QgsProcessingContext() 
feedback = QgsProcessingFeedback()
# ---------------- END QGIS STUFF ------------------------------
import geopandas as gpd  # this goes after



# defaults
# this order is set and cannot be changed
layer_order_dict = {'island': 0, 'building': 1, 'green': 2, 'parking': 3,
                'crossing': 4, 'street': 5, 'cycleway': 6, 'sidewalk': 7,
                'amenity': 8, 'busstop': 9}
# TODO: this need to be unified, the names
layer_file_dict = {'street': 'street_boundary_original', 'crossing': 'crossing_lines', 
                'building': 'buildings_gen', 'busstop': 'bus_stops',
                "parking": 'parking', 'sidewalk': 'sidewalk', 'green': 'green_gen',
                "amenity": "point_POI", "cycleway": "cycleway", "island": "islands_split"}


