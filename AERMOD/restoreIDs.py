#!/usr/bin/env python3

import pandas as pd
import geopandas as gpd
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('--epsg',default = 3665,type = int)
args = parser.parse_args()

concPath = 'receptorConc.csv'
print(f'Reading {concPath}')
conc = pd.read_csv(concPath,converters = {'x':str,'y':str})
conc['x'] = conc.x.str.strip('0')
conc['y'] = conc.y.str.strip('0')

print('Reading receptors.geojson')
receptors = gpd.read_file('receptors.geojson')
receptors = receptors.to_crs(epsg = args.epsg)
receptors['x'] = receptors.geometry.apply(
    lambda p: str(round(p.x,5)).strip('0')
)
receptors['y'] = receptors.geometry.apply(
    lambda p: str(round(p.y,5)).strip('0')
)

#assert set(receptors.x) == set(conc.x)
#assert set(receptors.y) == set(conc.y)

# merge the receptorID
print('Merging receptorIDs')
nBefore = len(conc)
conc = conc.merge(receptors[['receptorID','x','y']],on = ['x','y'])
nAfter = len(conc)
if nBefore != nAfter:
    print(f'{nBefore - nAfter} receptors were matched, exiting...')

# upload concentrations with receptorID (drop the un-needed 'x','y'
# columns)
print(f'Saving concentration to {concPath}')
conc.drop(columns = ['x','y'])[
    ['receptorID','concentrat','paf']
].to_csv(concPath,index = False)
