#!/usr/bin/env python3

'''this script takes the scenarioID and laneWidth and an optional zip
code and constructs the sources and receptors shapefiles'''

import argparse
from aermodInput import AermodScenario
from aermodConst import feet2meters

parser = argparse.ArgumentParser()
parser.add_argument('title',help = 'project title')
parser.add_argument('aermetOutputDirectory')
parser.add_argument('sourceGroupSize',type = int,
                    help = 'how many sources per AERMOD run')
parser.add_argument('population',type = int,
                    help = 'population of the urban area')
parser.add_argument('dayOfTheMonth',type = int,
                    help = 'the day of the month on which to use the meteo data')
parser.add_argument('--laneWidthInFeet',type = int,
                    help = 'optionally override the default 12 foot lanes')
parser.add_argument('--epsg',type = int,
                    help = 'optionally override the default epsg:3665, the unit must be "meter"')

args = parser.parse_args()
scenario = AermodScenario(args.epsg,args.laneWidthInFeet)
scenario.readSources()
scenario.readReceptors()
scenario.processAERMETfiles(args.aermetOutputDirectory)
scenario.constructAermodInputs(
    args.title,args.sourceGroupSize,args.population,args.dayOfTheMonth
)

