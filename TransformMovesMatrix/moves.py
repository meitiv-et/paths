'''the MOVES class loads all of the distributions and provides a
method for getting the per distance rate given the fips,
time of day,group of sourceTypes,and speed'''

import pandas as pd
import geopandas as gpd
import os
from smart_open import open

monthMap = {1:1,2:1,3:1,4:4,5:7,6:7,7:7,8:7,9:7,10:4,11:1,12:1}

def round5(x):
    return 5*round(x*0.2)

class MOVES(object):
    columns = ['countyID','hourID','pollutantID',
               'processID','sourceTypeID','roadTypeID',
               'avgSpeedBinID','ratePerDistance']
    
    def __init__(self,year,month,movesRoot):
        self.year = year
        self.month = month
        self.root = movesRoot

        # load the age distribution
        print('Loading the age distribution')
        self.ages = pd.read_csv(
            os.path.join(self.root,'age_distribution.csv'),
            dtype = {'countyID':pd.Int64Dtype()}
        )
        # add the required modelYearID column
        self.ages['modelYearID'] = year - self.ages.ageID
        
        # load the meteo for the passed month
        print('Loading the MOVES 20181022 meteorology')
        self.meteo = pd.read_csv(
            os.path.join(self.root,'MOVES20181022_zoneMonthHour.csv')
        ).query(f'monthID == {month}')
        
        # load the mapping from fips to fuel regions
        print('Loading the map from FIPS to fuel and IM regions')
        self.coverage = pd.read_excel(
            os.path.join(
                self.root,'moves_matrix_coverage_04-15-2020.xlsx'
            ),sheet_name = 'IM_fuel'
        )
        
        # load the opModeDist
        print('Loading the default OpMode distribution')
        self.opmode = pd.read_csv(
            os.path.join(self.root,'default_opmode_project.csv')
        )
        
        # init the rates dataframe
        self.rates = pd.DataFrame(columns = self.columns)

        # avoid reading MOVES matrices more than once, keys are
        # (region,T,H)
        self.matrices = {}
        self.meteoMap = {} # keys are (fips,hour) values (T,H)
        self.regionMap = {} # map from fips to fuel region
        

    def loadRates(self,fips,speedBinSize):
        fips = int(fips)
        print('Loading rates for',fips,self.year,self.month)
        # deterimine the fuel region
        row = self.coverage.query(f'countyID == {fips}')
        if len(row) == 0:
            print('Could not get region for county',fips)
            return None
        row = row.squeeze()
        region = f'f{row.fuelID}i{row.imID}'
        self.regionMap[fips] = region

        # for every hour load the rates and transform them using the
        # opmode and age distribututions
        # avoid reading the matrices more than once
        for hour in range(1,25):
            row = self.meteo.query(
                f'zoneID=={fips*10}&monthID=={self.month}&hourID=={hour}'
            ).squeeze()
            T = round5(row.temperature)
            H = round5(row.relHumidity)
            movesMonth = monthMap[self.month]
            self.meteoMap[(fips,hour)] = (T,H)

            if (region,T,H) in self.matrices: continue

            # implement the missing matrix logic
            Horig = H
            Torig = T
            while True:
                try:
                    prefix = os.path.join(
                        self.root,region,str(self.year)
                    )
                    path = os.path.join(
                        prefix,f'{movesMonth}_{T}_{H}.csv'
                    )
                    print('For hour',hour,'read',path)
                    rates = pd.read_csv(path,header = None)
                    rates = rates.iloc[:,:5]
                    rates.columns = [
                        'opModeID','pollutantID','sourceTypeID',
                        'modelYearID','emRate'
                    ]
                    break
                except OSError as e:
                    # print(e)
                    if H < 100:
                        H += 5
                    else:
                        H = Horig
                        T += 5
                        if T > 110:
                            print(
                                'Could not find the matrix for',
                                'region =',region,
                                'T =',Torig,
                                'H =',Horig
                            )
                            return

            # filter the ages on passed fips
            ages = None
            if 'countyID' in self.ages.columns:
                ages = self.ages.query(f'countyID == {fips}')

            if ages is None or len(ages) == 0:
                ages = self.ages
                
            # compute the perDistance rates
            # merge ages into rates and average over the ages
            rates = rates.merge(
                ages[['modelYearID','sourceTypeID','ageFraction']],
                on = ['modelYearID','sourceTypeID']
            )
            rates['rateAge'] = rates.emRate*rates.ageFraction
            rates = rates.groupby(
                ['opModeID','pollutantID','sourceTypeID']
            ).rateAge.sum().reset_index()

            # merge opModeDist and averge over the opModes
            rates = rates.merge(
                self.opmode,on = ['opModeID','sourceTypeID']
            )
            rates['rateOp'] = rates.rateAge*rates.opModeFraction
            rates = rates.groupby(
                ['linkAvgSpeed','sourceTypeID','pollutantID','roadTypeID']
            ).rateOp.sum().reset_index()
            
            # compute the rate perdistance
            rates['ratePerDistance'] = rates.rateOp/rates.linkAvgSpeed

            # average the rates into speedBins
            rates['avgSpeedBinID'] = rates.linkAvgSpeed.apply(
                lambda x: 1 + int((x - 0.000001)/speedBinSize)
            )
            rates = rates.groupby(
                ['sourceTypeID','pollutantID',
                 'roadTypeID','avgSpeedBinID']
            ).ratePerDistance.mean().reset_index()

            # save the rates
            self.matrices[(region,Torig,Horig)] = rates


    def assembleRates(self,fipsList,speedBinSize = 5):
        for fips in fipsList:
            for hourID in range(1,25):
                # get T,H for this hour
                if (fips,hourID) not in self.meteoMap:
                    self.loadRates(fips,speedBinSize)

                T,H = self.meteoMap[(fips,hourID)]

                # get the fuel region
                region = self.regionMap[fips]

                # make sure we have the rates
                if (region,T,H) not in self.matrices:
                    print('Missing rates for',region,T,H)
                    return None

                rates = self.matrices[(region,T,H)].copy()
                rates['countyID'] = fips
                rates['hourID'] = hourID
                rates['processID'] = 1

                # concat
                self.rates = pd.concat((self.rates,rates))
                     

    def outputRates(self,path):
        self.rates.to_csv(open(path,'w'),index = False)
