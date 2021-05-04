#!/usr/bin/env python3

'''compute the running exhaust emissions using perDistance rates'''

import sys
import pandas as pd
from smart_open import open
import geopandas as gpd
from joblib import Parallel,delayed
import yaml
from argparse import ArgumentParser

def groupRates(rates,vmx,srcTypeGroup,countyID,
               timeIntervalID,roadTypeID,avgSpeedBin):
    # filter the rates
    rateSubset = rates[
        (rates.sourceTypeID.isin(srcTypeGroup)) &
        (rates.countyID == countyID) &
        (rates.roadTypeID == roadTypeID) &
        (rates.timeIntervalID == timeIntervalID) &
        (rates.avgSpeedBinID == avgSpeedBin)
    ]
    # filter the vmx
    vmxSubset = vmx[
        (vmx.sourceTypeID.isin(srcTypeGroup)) &
        (vmx.timeIntervalID == timeIntervalID) &
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
        ['countyID','timeIntervalID','pollutantID','sourceTypeID',
         'fuelTypeID','roadTypeID','avgSpeedBinID']
    ).emRate.sum().reset_index()


def processGroup(rates,vmx,vmap,dmap,vt,hour,speed,rt,fips,group):
    grRate = groupRates(rates,vmx,vmap[vt],fips,dmap[fips],hour,rt,speed)
    group = group.drop(columns = ['vehType']).merge(
        grRate,
        on = ['timeIntervalID','avgSpeedBinID','roadTypeID','countyID']
    )
    group['emquant'] = group.vmt*group.emRate
    return group.groupby(
        ['linkID','pollutantID','sourceTypeID','fuelTypeID']
    ).emquant.sum().reset_index()


def main():
    parser = ArgumentParser()
    parser.add_argument('vmxPath',help = 'path to the vehicle mix CSV')
    parser.add_argument('ratesPath',help = 'path to the emission rates CSV')
    parser.add_argument('year',type = int,help = 'emission rates year')
    parser.add_argument('numCPU',type = int,help = 'number of CPUs to use')
    parser.add_argument('--dayOfTheWeek',default = 'WK')
    args = parser.parse_args()
    vmxPath = args.vmxPath
    ratesPath = args.ratesPath
    year = args.year
    numCPU = args.numCPU
    dayOfTheWeek = args.dayOfTheWeek
    
    # read the vmt
    vmt = pd.read_csv('linkVMT.csv')

    # read the links metadata and merge
    links = pd.read_csv('links.csv')
    vmt = vmt.merge(links,on = 'linkID')

    # read the rates
    rates = pd.read_csv(open(ratesPath))

    # rename hourID to timeIntervalID
    rates = rates.rename(columns = {'hourID':'timeIntervalID'})

    # determine whether timeIntervals in linkVMT are hours and if not
    # exit with "Unimpelemented" error
    if len(set(vmt.timeIntervalID)) != 24:
        print('Intervals other than 60 min long not yet implemented')
        sys.exit(1)

    # rename timeIntervalID timeIntervalID
    vmt = vmt.rename(columns = {'timeIntervalID':'timeIntervalID'})

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
    vmx = vmx.query(
        f'yearID == {selectYear} & dayOfTheWeek == "{dayOfTheWeek}"'
    )
    
    # vmx needs to have timeIntervalID,countyID columns

    # group by
    # ['vehType','timeIntervalID','avgSpeedBinID','roadTypeID','countyID']
    # and compute the average rate for each group
    results = Parallel(n_jobs = numCPU)(
        delayed(processGroup)(rates,vmx,vehTypeMap,distMap,*k,g)
        for k,g in vmt.groupby(
            ['vehType','timeIntervalID','avgSpeedBinID',
             'roadTypeID','countyID']
        )
    )
    
    pd.concat(results).groupby(
        ['linkID','pollutantID','fuelTypeID','sourceTypeID']
    ).emquant.sum().reset_index().to_csv(
        f'emissions_{year}_{dayOfTheWeek}.csv',index = False
    )
    

if __name__ == '__main__':
    main()
