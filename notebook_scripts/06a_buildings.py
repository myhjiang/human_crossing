import json

import geopandas as gpd

import argparse
parser = argparse.ArgumentParser(description='set folder')
parser.add_argument('folder', metavar='fd', type=str)
args = parser.parse_args()

# folder 
# folder = r'../example_2'
base_folder = rf"../{args.folder}"
folder_temp = rf'{base_folder}/temp'
# read param json 
with open(rf'{base_folder}/param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
building_level = param_dict['building_level']
size = param_dict['size_code']
# size = 'A5_off'
# decide which scale folder the processing result goes by the scale
base_folder = rf"{base_folder}/data"
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}/500'
else:
    scale = 1000
    folder = rf'{base_folder}/1000'


# overlay preference as param, for the bus stop thing before to be integrated
pref = param_dict['overlay_pref']  # "direct", or "displace"
move_dist = param_dict['icon_gap']*scale / 1000

# files 
streets_df = gpd.read_file(rf'{folder}/street_area.geojson')
extent_df = gpd.read_file(rf'{base_folder}/big_extent.geojson')
building_df = gpd.read_file(rf'{base_folder}/buildings.geojson')
working_extent_df = gpd.read_file(rf'{base_folder}/extent_{size}.geojson')
try:
    busstop_df = gpd.read_file(rf'{folder}/bus_stop_overlay.geojson')  # for later
except:
    busstop_df = None

area_gap_meter = param_dict['area_gap'] * scale / 1000  # in m
line_gap_meter = param_dict['line_gap'] * scale / 1000
line_width_meter = param_dict['line_width'] * scale / 1000

try:
    island_df = gpd.read_file(rf'{folder}/islands_full.geojson')
except:
    island_df = None
try: 
    sidewalk_area_df = gpd.read_file(rf'{folder}/sidewalk_gen.geojson')
except:
    sidewalk_area_df = None
try: 
    sidewalk_line_df = gpd.read_file(rf'{folder}/sidewalk_lines.geojson')
except:
    sidewalk_line_df = None

# if sidewalk area exist, directly move away 5mm or so from the sidewalk
if sidewalk_area_df is not None:
    street_area = gpd.read_file(rf'{folder}/street_from_sidewalk.geojson')
    sidewalk_buffer = sidewalk_area_df.geometry.unary_union.buffer(area_gap_meter)
    streets_buffer = street_area.geometry.unary_union.union(sidewalk_buffer)
elif sidewalk_line_df is not None:
    sidewalk_buffer = sidewalk_line_df.geometry.unary_union.buffer(area_gap_meter)
    streets_buffer = streets_df.geometry.unary_union.buffer(area_gap_meter).union(sidewalk_buffer)
# if only street, then move further away to leave space for a potential cycleway or something
else:
    streets_buffer = streets_df.geometry.unary_union.buffer(area_gap_meter+line_gap_meter+line_width_meter)
if (pref == "displace") & (busstop_df is not None):
    # NOTSURE: not tested. 220910
    # if the bus stop has been displaced, the buffer need to add the bus stops
    streets_buffer = streets_buffer.unary_union.union(busstop_df.geometry.unary_union).buffer(area_gap_meter+line_gap_meter+line_width_meter)
# else:
#     streets_buffer = streets_df.geometry.unary_union.buffer(area_gap_meter+line_gap_meter+line_width_meter)

# validity
# TODO: this has to go somewhere. 

# cut buildings
building_df.geometry = building_df.geometry.difference(streets_buffer)
geometry = building_df.geometry.unary_union
# dialation / erosions x 2
def DandE(geom, d, n):
    "dialation - errosion with d and n rounds"
    for i in range(0, n+1):
        geom = geom.buffer(d, cap_style=3, join_style=2)
        geom = geom.buffer(-d, cap_style=3, join_style=2)
        i = i+1
    return geom
def buildingGen(building_level, geometry):
    d1 = 0; d2 = 0
    if building_level == 'rough':
        if 'example_0' in base_folder:
            d1 = 10; d2 = 10
        else:
            d1 = 15; d2 = 10
        geometry = DandE(geometry, d1, 3)
        geometry = geometry.simplify(5)
        # # difference clip again
        # geometry = geometry.difference(streets_buffer)
        geometry = DandE(geometry, d2, 1)
        geometry = geometry.simplify(5)
        geometry = geometry.difference(streets_buffer)
        geometry = geometry.simplify(2)
        single_parts = list(geometry)
        return single_parts
    elif building_level == 'detailed':
        d1 = 3; d2 = 3
        geometry = DandE(geometry, d1, 2)
        # geometry = geometry.simplify(10)
        # # difference clip again
        # geometry = geometry.difference(streets_buffer)
        geometry = DandE(geometry, d2, 2)
        geometry = geometry.simplify(3)
        geometry = geometry.difference(streets_buffer)
        geometry = geometry.simplify(2)
        single_parts = list(geometry)
        return single_parts

    else:
        raise ValueError("building param not correct. it can only be either 'rough' or 'detailed'.")

single_parts = buildingGen(building_level,geometry)

d = {'geometry': single_parts}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
gdf = gdf[gdf.geometry.area>20]
gdf.set_geometry('geometry', inplace=True)

# make interactors
# cut with working extent, remove the empty
gdf['cut'] = gdf.geometry.intersection(working_extent_df.geometry.unary_union)
interactor_df = gdf[gdf.cut.is_empty==False]
# interactor at centroid
interactor_df['point'] = interactor_df.cut.centroid
# interactors need to contain ids, join back with the buildings
interactor_df.set_geometry('cut', inplace=True)
join_df = gpd.sjoin(interactor_df, building_df, how='left')
join_df = join_df[['point', 'osm_way_id']]
# merge the same points
join_df.reset_index(inplace=True)
join_df = gpd.GeoDataFrame(join_df, geometry='point')
interactor_df = join_df.dissolve(by='index', aggfunc=list)
interactor_df.reset_index(inplace=True)
# make the list attribute to string
interactor_df['osm_way_id'] = interactor_df['osm_way_id'].apply(lambda x: ','.join(map(str, sorted(x))))

# out buildings
gdf.drop(columns=['cut'], inplace=True)
gdf.to_file(rf'{folder}/buildings_gen.geojson', driver='GeoJSON')

# out interactors
# interactor_df.drop(columns=['geometry', 'cut'], inplace=True)
interactor_df['highway'] = 'buildings'
# interactor_df.to_file(rf'{folder}/buildings_interactors.geojson', driver='GeoJSON')