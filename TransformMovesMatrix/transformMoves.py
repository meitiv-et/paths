#!/usr/bin/env python3

'''script to transform the MOVES rates into the per-distance rates
binned by 5 mph velocity bins without the fuelID column'''

from argparse import ArgumentParser
parser = ArgumentParser()
parser.add_argument('fipsList',
                    help = 'comma separated list of counties')
parser.add_argument('year',type = int,help = '4 digit scenario year')
parser.add_argument('month',type = int,
                    help = 'numeric month of the scenario')
parser.add_argument('movesRoot',
                    help = 'directory where MOVES matrix rates reside')
parser.add_argument('--speedBinSize',default = 5,type = int,
                    help = 'speed bin size for aggregation in mph')

args = parser.parse_args()
fipsStrList = args.fipsList.split(',')
fipsIntList = list(map(int,fipsStrList))

import moves

m = moves.MOVES(args.year,args.month,args.movesRoot)
m.assembleRates(fipsIntList,args.speedBinSize)
path = f'movesRates_{args.year}-{args.month}_{"-".join(fipsStrList)}.csv'
m.outputRates(path)
