#!/usr/bin/env python3

'''this script combines the outputs of aermod runs with different
source groups'''

# this script must be run from the directory that contains the .out
# files

pollutant = 'pm25'
from glob import glob
from collections import defaultdict
from aermodConst import exponents
import numpy as np

concentrations = defaultdict(float)

def processOut(outFile):
    with open(outFile) as f:
        for line in f:
            if line.startswith('*'): continue
            vals = line.split()
            c = float(vals[2]) 
            concentrations[(vals[0],vals[1])] += c

outFiles =  glob(f'*.out')
numFiles = len(outFiles)
for idx,outFile in enumerate(outFiles):
    print('Processing',outFile,idx + 1,'out of',numFiles)
    processOut(outFile)

# make and save the a dataframe
rows = []
for (x,y),c in concentrations.items():
    rows.append({
        'x':x,'y':y,'concentrat':c,
        'paf':1. - np.exp(-c*exponents[pollutant])
    })

import pandas as pd
print('Writing results')
pd.DataFrame(rows).to_csv('receptorConc.csv',index = False)
