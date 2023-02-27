import json

# folder 
base_folder = r'..\example_1'
root_folder = base_folder
folder_sld = r'..\styles'

# make folder
from pathlib import Path
Path(rf"{base_folder}/image").mkdir(parents=True, exist_ok=True)

# read QGIS setup json
with open(r"qgis_env.json", 'r') as f:
    env_dict = json.load(f)
# read param json 
with open(rf'{base_folder}\param.json') as fp: 
    param_dict = json.load(fp)
with open(r'size_lookup_table_fr.json') as fp:
    size_dict = json.load(fp)
epsg_ = param_dict['epsg']
size = param_dict['size_code']
object_list = param_dict['object_list']
style_list = param_dict['style_list']

base_folder = rf"{base_folder}\data"
folder_temp = rf'{base_folder}\temp'

if 'A3' in size:
    scale_ = 500
    folder = rf'{base_folder}\500'
else:
    scale_ = 1000
    folder = rf'{base_folder}\1000'

style_folder = r"..\styles"

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


# add the street objects in the object list
street_objects = ['street', 'crossing']
if os.path.isfile(rf"{folder}\islands_full.geojson"):
    street_objects.append('island')
for x in street_objects:
    if x not in object_list:
        object_list.insert(0, x)
        style_list.insert(0, f'{x}_default')

# don't do sidewalk area if it's not A3!
if 'A3' not in size:
    if 'sidewalk_area' in object_list:
        index = object_list.index('sidewalk_area')
        object_list.pop(index)
        style_list.pop(index)

# if 'A5_on' in size:


# defaults
# this order is set and cannot be changed
layer_order_dict = {'sidewalk_area': 0, 'building': 1, 'island': 2,  'green': 3, 'sidewalk_line': 4,
                'crossing': 6, 'street': 5, 
                'bus_stop': 7}
# TODO: this need to be unified, the names
layer_file_dict = {'street': 'street_boundary_filled', 'crossing': 'crossing_lines', 
                'building': 'buildings_gen', 'bus_stop': 'bus_stop_overlay',
                'sidewalk_area': 'sidewalk_gen', 'green': 'green_gen', "sidewalk_line": "sidewalk_lines",
                "island": "island_split"}

fr_name_dict = {'street': 'routes', 'crossing': 'passage piéton', 'building': 'bâtiments', 'bus_stop': 'arrêt de bus',
                'parking': 'parking', 'sidewalk_line': 'trottoir', 'sidewalk_area': 'trottoir', 'green': 'pelouse', 
                'amenity': 'POI', 'cycleway': 'pistes cyclables', 'island': 'îlots'}


def exportLayout(template_code, object_list, style_list):
    '''
    1st input takes 1 string: e.g. A5_on
    2nd input takes a list of strings for objects: street, crossing_lines etc
    3rd input takes a list of strings for styles: area_1, line_2 etc'''

    # folder, epsg, scale, size_dict = getParam(location_code, template_code)
    epsg = epsg_ 
    size = template_code
    scale = scale_

    # get map extent in map unit
    # TODO on the server, this need to be in the fucntion, because, import will read and save it before the function is called.
    extent_df = gpd.read_file(rf'{base_folder}\extent_{template_code}.geojson')
    box = extent_df.geometry.unary_union.bounds

    # decode the template to size
    size_code = template_code.split('_')[0]
    layout_code = template_code
    x, y = size_dict[layout_code]  # this is in mm
    x_map = x * scale / 1000.0
    y_map = y * scale / 1000.0

    project = QgsProject.instance()             #gets a reference to the project instance
    layout = QgsPrintLayout(project)            #makes a new print layout object, takes a QgsProject as argument

    layout = QgsPrintLayout(project)
    layout.initializeDefaults() 
    pc = layout.pageCollection()
    pc.pages()[0].setPageSize(size_code, QgsLayoutItemPage.Landscape) 

    # ------- ADD LAYERS TO MAP AND STYLE THEM -----------
    # TODO how to name the layers and files better? 
    print(object_list)
    print(style_list)
    for obj in object_list:
        if obj == '':
            continue
        obj_index = object_list.index(obj)
        ly = QgsProcessingUtils.mapLayerFromString(rf'{folder}\{layer_file_dict[obj]}.geojson', context)
        project.addMapLayer(ly)
        ly.setName(obj)  # TODO not good with the "busstop" 
        # ------------ APPLY STYLES -------------------
        # TODO: the qml file naming needs to be unified 
        # chosen_style = [style for style in style_list if obj.replace(" ", "") in style][0]
        chosen_style = style_list[obj_index]
        # # NOTE very weird comprimise for now
        # if obj == 'crossing' and 'A3' in template_code:
        #     chosen_style = style_list[obj_index].replace('1000', '500')
        style_file = rf'{folder_sld}\{chosen_style}.qml'
        ly.loadNamedStyle(style_file)
        ly.triggerRepaint()

    # ------------ APPLY TEMPLATE ----------------
    # TODO: the template names
    with open(rf'..\templates\{layout_code}_fr.qpt', encoding="utf-8") as f:
        template_content = f.read()
    doc = QDomDocument()
    doc.setContent(template_content)
    items, ok = layout.loadFromTemplate(doc, QgsReadWriteContext(), False)
    title_item = layout.itemById('title_braille')
    # NOTE: this title TODO
    # title_item.setText(f'{location_code.replace("_", "-")}') 
    title_item.setText(f'location X')
    title_item_print = layout.itemById('title_print')
    # NOTE: this title
    # title_item_print.setText(f'{location_code}_print')
    title_item_print.setText(f'location x')
    map_item = layout.itemById('Map 1')
    rectangle = QgsRectangle(box[0], box[1], box[2], box[3])         
    map_item.setExtent(rectangle)

    # -------- ADD LEGEND ITEMS -----------------
    legend_item = layout.itemById('legend')
    root = QgsLayerTree()
    # sort the layers first according to area-line-point order with the pre-defined order list
    layer_list = []
    for ly in project.mapLayers().values():  # this a fucking dict !!! not ordered !! 
        layer_list.append({layer_order_dict[ly.name()]: ly})
    layer_sorted = sorted(layer_list, key=lambda d: list(d.keys())) 
    # add to root of layer tree then to legend
    i = 0 
    for ly in layer_sorted:
        list(ly.values())[0].setName(fr_name_dict[list(ly.values())[0].name()])
        # if the layer is street, remove it's own legend and add the ghost layer legend
        # TODO it's hardcoded for now, and the street boundary file need to be the copy file
        if list(ly.values())[0].name() == 'routes': 
            ghost_ly = QgsProcessingUtils.mapLayerFromString(rf'{base_folder}\snapped_streets.geojson', context)
            ghost_ly.loadNamedStyle(rf'{folder_sld}\street_ghost.qml')
            tree_ly = root.addLayer(ghost_ly)
            tree_ly.setUseLayerName(False)
            tree_ly.setName('routes')
        else:
            tree_ly = root.addLayer(list(ly.values())[0])
        # for template A5_on, need to modify braille and print labels, because they are not part of the legend 
        # TODO: I'll probably also need print labels for A4 A3 etc.
        if template_code == 'A5_on':
            braille_label = layout.itemById(f"label_{i}")
            braille_label.setText(list(ly.values())[0].name())
            braille_label.setVisibility(True)
            print_label = layout.itemById(f"label_print_{i}")
            print_label.setText(list(ly.values())[0].name())
            print_label.setVisibility(True)
        if 'A4' in template_code or 'A3' in template_code:
            print_label = layout.itemById(f"label_print_{i}")
            print_label.setText(list(ly.values())[0].name())
            print_label.setVisibility(True)
        # remove the excessive dots on the A5_off layout if there are not that many legend items
        if template_code == 'A5_off':
            dot = layout.itemById(f"marker_{i}")
            dot.setVisibility(True)
        # if legend is without braille (a5 both), take away the legend names
        if size_code == 'A5':
            tree_ly.setUseLayerName(False)
            tree_ly.setName('')
        i = i+1
    legend_item.model().setRootGroup(root)

    # --------- LINK SCALE BAR TO MAP ---------------
    scalebar_item = layout.itemById('scale_bar')
    if scalebar_item:
        scalebar_item.setLinkedMap(map_item)
        # TODO it seems a bit wrong? the lines? check later

    # export 
    exporter = QgsLayoutExporter(layout)  
    # TODO how to name this inline with the callback? (timestamp so it doesn't crash?)
    exporter.exportToImage(rf'{root_folder}\image\{template_code}.png', QgsLayoutExporter.ImageExportSettings()) 

    # pdf 
    exporter.exportToPdf(rf'{root_folder}\image\{template_code}.pdf', QgsLayoutExporter.PdfExportSettings())

    # clear project so you don't get those fucking re-loads from nowhere!!
    project.clear()

exportLayout(size, object_list, style_list)
