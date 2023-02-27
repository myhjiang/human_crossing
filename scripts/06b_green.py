import json

import geopandas as gpd

# folder 
base_folder = r'..\example_0'
folder_temp = rf'{base_folder}\temp'
# read param json 
with open(rf'{base_folder}\param.json') as fp: 
    param_dict = json.load(fp)
epsg = param_dict['epsg']
size = param_dict['size_code']
# size = 'A5_off'
# decide which scale folder the processing result goes by the scale
base_folder = rf"{base_folder}\data"
if 'A3' in size:
    scale = 500
    folder = rf'{base_folder}\500'
else:
    scale = 1000
    folder = rf'{base_folder}\1000'

# overlay preference as param, for the bus stop thing before to be integrated
pref = param_dict['overlay_pref']  # "direct", or "displace"
move_dist = param_dict['icon_gap']*scale / 1000

# files 
streets_df = gpd.read_file(rf'{folder}\street_area.geojson')
extent_df = gpd.read_file(rf'{base_folder}\big_extent.geojson')
green_df = gpd.read_file(rf'{base_folder}\green.geojson')

working_extent_df = gpd.read_file(rf'{base_folder}\extent_{size}.geojson')
try:
    busstop_df = gpd.read_file(rf'{folder}\bus_stop_overlay.geojson')  # for later
except:
    busstop_df = None

area_gap_meter = param_dict['area_gap'] * scale / 1000  # in m
line_gap_meter = param_dict['line_gap'] * scale / 1000
line_width_meter = param_dict['line_width'] * scale / 1000

try:
    island_df = gpd.read_file(rf'{folder}\islands_full.geojson')
    # remove the green that is on the island
    green_df = green_df[green_df.geometry.disjoint(island_df.geometry.unary_union)]
except:
    island_df = None
try: 
    sidewalk_area_df = gpd.read_file(rf'{folder}\sidewalk_gen.geojson')
except:
    sidewalk_area_df = None
try: 
    sidewalk_line_df = gpd.read_file(rf'{folder}\sidewalk_lines.geojson')
except:
    sidewalk_line_df = None
try:
    buildings_df = gpd.read_file(rf'{base_folder}\buildings_gen.geojson')
except:
    buildings_df = None


# if sidewalk area exist, directly move away 5mm or so from the sidewalk
if sidewalk_area_df is not None:
    street_area = gpd.read_file(rf'{folder}\street_from_sidewalk.geojson')
    sidewalk_buffer = sidewalk_area_df.geometry.unary_union.buffer(area_gap_meter)
    streets_buffer = street_area.geometry.unary_union.union(sidewalk_buffer)
if sidewalk_line_df is not None:
    sidewalk_buffer = sidewalk_line_df.geometry.unary_union.buffer(area_gap_meter)
    streets_buffer = streets_df.geometry.unary_union.buffer(area_gap_meter).union(sidewalk_buffer)
# if only street, then move further away to leave space for a potential cycleway or something
else:
    if (pref == "displace") & (busstop_df is not None):
        # NOTSURE: not tested. 220910
        # if the bus stop has been displaced, the buffer need to add the bus stops
        streets_buffer = streets_df.geometry.unary_union.union(busstop_df.geometry.unary_union).buffer(area_gap_meter+line_gap_meter+line_width_meter)
    else:
        streets_buffer = streets_df.geometry.unary_union.buffer(area_gap_meter+line_gap_meter+line_width_meter)

if buildings_df is not None:
    buildings_buffer = buildings_df.geometry.unary_union.buffer(area_gap_meter)
    all_buffer = streets_buffer.union(buildings_buffer)
else:
    all_buffer = streets_buffer
# cut
green_df.geometry = green_df.geometry.difference(all_buffer)
geometry = green_df.geometry.unary_union
# dialation / erosions x 2
def DandE(geom, d, n):
    "dialation - errosion with d and n rounds"
    for i in range(0, n+1):
        geom = geom.buffer(d, cap_style=3, join_style=2)
        geom = geom.buffer(-d, cap_style=3, join_style=2)
        i = i+1
    return geom
geometry = DandE(geometry, 5, 2)
geometry = geometry.simplify(2)
single_parts = list(geometry)
d = {'geometry': single_parts}
gdf = gpd.GeoDataFrame(d, crs=f'epsg:{epsg}')
gdf.set_geometry('geometry', inplace=True)
gdf.to_file(rf'{folder}\green_gen.geojson', driver='GeoJSON')