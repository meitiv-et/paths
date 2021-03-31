#!/usr/bin/env python3

import sys
if len(sys.argv) != 2:
    print('Usage:',sys.argv[0],'pathToDynaStudioShapeFile')
    sys.exit(1)

epsg = 3082 # this projected EPSG is in meters
import geopandas as gpd
shp = gpd.read_file(sys.argv[1]).to_crs(epsg = epsg)

# get the county FIPS
counties = gpd.read_file('https://www2.census.gov/geo/tiger/GENZ2019/shp/cb_2019_us_county_5m.zip')
from shapely.strtree import STRtree
counties = counties.to_crs(epsg = epsg)
tree = STRtree(counties.geometry)
fipsLookup = dict((r.geometry.wkt,r.GEOID) for r in counties.itertuples())
                          
shp['point'] = [l.interpolate(0.5,normalized = True) for l in shp.geometry]
shp['countyID'] = shp.point.apply(
    lambda p: fipsLookup[tree.nearest(p).wkt]
)                                  

# add the linkID column
shp['linkID'] = [f'{r.A_NODE}-{r.B_NODE}' for r in shp.itertuples()]

# map the roadTypeID
shp['roadTypeID'] = shp['#LTYPE'].apply(
    lambda ID: 4 if ID in [1,2,6,7,8,9,10] else 5
)

milesInMeter = 0.000621371
shp['length'] = shp.geometry.length*milesInMeter

# rename columns
shp = shp.rename(columns = {'#SPEED':'speedLimit','#LANES':'numLanes'})

# output
shp[
    ['linkID','roadTypeID','countyID','length','speedLimit','numLanes']
].to_csv('links.csv',index = False)

