# Tactile maps for street intersections

## set-ups

**The scripts are developed on a Windows machine. It could work differently on other systems especially the pyQGIS part. Modify accordingly**

### Requirements

- geopandas 
- pyqgis

Set up PyQGIS on Windows like this [Anita's blog]. And in the `qgis_env.json` file, change the paths accordingly. 

It requires Braille Type Font to be installed on the machine to print the braille characters. This font can be found here. 

### file structure

to do.

### the param.json

There is a `param.json` file that contains the parameters used in the scripts. An example of this file and the parameters:

```json
{
    "size_code": "A3",  // "A3", "A4", "A5_on", "A5_off"
    "center_lat": 48.58622,  // lat of the intersection center 
    "center_lon": 7.76322,  // lon of the intersection center
    "line_width": 1, // major line width, in mm
    "line_gap": 3,  // gap between parallel lines, in mm
    "area_gap": 5,  // gap between lines and areas, in mm
    "icon_size": 4,  // point icon size, in mm
    "icon_gap": 3,  // gap around the point, in mm
    "building_level": "rough",  // building generalization level, either "rough" or "detailed"
    "overlay_pref": "direct",  // point-line overlay preference, either "direct" or "displace"
    "opbjects": ["street", "crossing", "island"],  // objects to include on the map. A3 maps allow max 11, A4 max 7, A5_on max 3, A5_off max 5. Exceeding the number = no map. 
    "style_list": ["street_default", "crossing_default", "island_default"],  // the symbol choice, name from the "symbol table", in the same order with the objects. 
    "lane_width": 3.5,  // default, don't change this. 
    "epsg": "3857"  // default, don't change this.
}
```

**Now I don't have parameter value checks. So setting weird values would screw it up. Change them only when you know exactly what you are doing.**

## run the scripts

to do

## defining your own templates and symbols

