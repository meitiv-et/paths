#!/usr/bin/env python3

'''this script takes the scenarioID and year code and constructs the
sources and receptors shapefiles'''

import argparse
from aermodConst import feet2meters
import sys

parser = argparse.ArgumentParser()
parser.add_argument('linkGeometriesPath',help = 'path to the dataset with link geometries, A and B nodeIDs and number of lanes')
parser.add_argument('emissionsPath',help = 'path to the emissions dataset')
parser.add_argument('--epsg',help = 'optional projected EPSG to use, if omitted 3665 will be used')

args = parser.parse_args()
from aermodInput import AermodScenario
scenario = AermodScenario(args.epsg,12)

if not scenario.readSources():
    print('Making sources')
    scenario.getLinkGeometries(args.linkGeometriesPath)
    scenario.constructNetwork()
    scenario.mergeEmissionRate(args.emissionsPath)
    scenario.makeSources()
    scenario.saveSources()
    
if scenario.readReceptors():
    print('Receptors already constructed')
else:
    scenario.makeLinkReceptors()
    scenario.makeGridReceptors()
    scenario.dropReceptorsInSources()
    scenario.saveReceptors()
