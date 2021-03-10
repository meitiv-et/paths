#!/usr/bin/env python3

'''compute the running exhaust emissions using perDistance rates'''

import sys
import pandas as pd
from smart_open import open
import geopandas as gpd
from joblib import Parallel,delayed
import yaml

def groupRates(rates,vmx,srcTypeGroup,countyID,
               hourID,roadTypeID,avgSpeedBin):
    # filter the rates
    rateSubset = rates[
        (rates.sourceTypeID.isin(srcTypeGroup)) &
        (rates.countyID == countyID) &
        (rates.roadTypeID == roadTypeID) &
        (rates.hourID == hourID) &
        (rates.avgSpeedBinID == avgSpeedBin)
    ]
    # filter the vmx
    vmxSubset = vmx[
        (vmx.sourceTypeID.isin(srcTypeGroup)) &
        (vmx.hourID == hourID) &
        (vmx.roadTypeID == roadTypeID) &
        (vmx.countyID == countyID)
    ]
    # merge
    rateSubset = rateSubset.merge(
        vmxSubset[['sourceTypeID','fuelTypeID','VMTmix']],
        on = ['sourceTypeID','fuelTypeID']
    )
    # average and return
    rateSubset['emRate'] = rateSubset.ratePerDistance*\
                           rateSubset.VMTmix/vmxSubset.VMTmix.sum()
    return rateSubset.groupby(
        ['countyID','hourID','pollutantID','sourceTypeID',
         'fuelTypeID','roadTypeID','avgSpeedBinID']
    ).emRate.sum().reset_index()


def processGroup(rates,vmx,vmap,dmap,vt,hour,speed,rt,fips,group):
    grRate = groupRates(rates,vmx,vmap[vt],fips,dmap[fips],hour,rt,speed)
    group = group.drop(columns = ['vehType']).merge(
        grRate,
        on = ['hourID','avgSpeedBinID','roadTypeID','countyID']
    )
    group['emquant'] = group.vmt*group.emRate
    return group.groupby(
        ['linkID','pollutantID','sourceTypeID','fuelTypeID']
    ).emquant.sum().reset_index()


def main(argv):
    if len(sys.argv) != 5:
        print('Usage:',argv[0],'vmxPath','ratesPath','year','numCPU')
        sys.exit(1)

    vmxPath = argv[1]
    ratesPath = argv[2]
    year = int(argv[3])
    numCPU = int(argv[4])

    # read the vmt
    vmt = pd.read_csv('linkVMT.csv')

    # read the links metadata and merge
    links = pd.read_csv('links.csv')
    vmt = vmt.merge(links,on = 'linkID')

    # read the rates
    rates = pd.read_csv(open(ratesPath))

    # determine whether timeIntervals in linkVMT are hours and if not
    # exit with "Unimpelemented" error
    if len(set(vmt.timeIntervalID)) != 24:
        print('Intervals other than 60 min long not yet implemented')
        sys.exit(1)

    # rename timeIntervalID hourID
    vmt = vmt.rename(columns = {'timeIntervalID':'hourID'})

    # read the vehType to sourceType map
    vehTypeMap = yaml.load(open('vehTypeMap.yaml'))

    # filter on year
    rates = rates.query(f'yearID == {year}').drop(columns = ['yearID'])
        
    # filter running exhaust processID == 1
    rates = rates.query('processID == 1').drop(columns = ['processID'])

    if len(rates) == 0:
        print('No emission rates for year',year)
        sys.exit(1)

    # transform the volumes by vehType into volumes by sourceType using
    # the VMX dataset
    vmx = pd.read_csv(open(vmxPath))

    # determine which year in the vmx subset is closest to the
    # scenario year
    availableYears = set(vmx.yearID)
    dist = 100
    selectYear = None
    for vmxYear in availableYears:
        d = abs(vmxYear - year)
        if d < dist:
            selectYear = vmxYear
            dist = d
            
    # filter on year and weekday
    vmx = vmx.query(f'yearID == {selectYear} & dayOfTheWeek == "WK"')
    
    # vmx needs to have hourID,countyID columns

    # group by
    # ['vehType','hourID','avgSpeedBinID','roadTypeID','countyID']
    # and compute the average rate for each group
    results = Parallel(n_jobs = numCPU)(
        delayed(processGroup)(rates,vmx,vehTypeMap,distMap,*k,g)
        for k,g in vmt.groupby(
            ['vehType','hourID','avgSpeedBinID',
             'roadTypeID','countyID']
        )
    )
    
    pd.concat(results).groupby(
        ['linkID','pollutantID','fuelTypeID','sourceTypeID']
    ).emquant.sum().reset_index().to_csv(
        f'emissions_{year}.csv',index = False
    )
    

if __name__ == '__main__':
    main(sys.argv)
