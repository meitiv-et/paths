import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point,Polygon
from ftplib import FTP
import gzip
import io
from geopy.distance import geodesic
import geopy
import os.path
from glob import glob
import json
import zipfile
import re

class cdoStations(object):
    baseUrl = 'https://www.ncdc.noaa.gov/cdo-web/api/v2/'
    token = 'pePpOevKHYDyQBuDdXVpnHDnHqKmQxXX'
    dataTypes = ''
    def __init__(self):
        self.headers = {'token':self.token}
        self.delta = 0.1
        self.params = {'limit':1000,'offset':0}
        
    def closestStation(self,lat,lon,year):
        # find the closest station that has data for the passed year
        self.params['startdate'] = f'{year}-01-01'
        self.params['enddate'] = f'{year}-12-31'
        
        # load a list of all stations within a rectangle
        self.params['extent'] = ','.join(
            map(str,(lat - self.delta,lon - self.delta,
                     lat + self.delta,lon + self.delta))
        )

        # continue getting stations until offset + limit > count
        stations = []
        while True:
            result = requests.get(
                f'{self.baseUrl}/stations',
                params = self.params,
                headers = self.headers
            ).json()
            stations.extend(result['results'])
            meta = result['metadata']['resultset']
            if meta['offset'] + meta['limit'] > meta['count']:
                break
            self.params['offset'] += self.params['limit']
        
        # get the station that is closest to the passed lat,lon
        # location
        # minDist = 1000.
        # closest = None
        # for station in stations:
        #     distance = geodesic(
        #         (lat,lon),(station['latitude'],station['longitude'])
        #     ).miles
        #     if distance < minDist:
        #         minDist = distance
        #         closest = station

        return stations


class ISD(object):
    host = 'ftp.ncei.noaa.gov'
    directory = 'pub/data/noaa'
    baseURL = f'ftp://{host}/{directory}'
    def __init__(self,year,month,home):
        self.year = int(year)
        self.month = int(month)
        self.monthAbbr = pd.to_datetime(
            f'{year}{str(month).zfill(2)}01'
        ).strftime('%b').upper()

        self.sfc_template = open(os.path.join(home,'sfc_template.inp')).read()
        self.asf_template = open(os.path.join(home,'asf_template.inp')).read()
        
    def getAllStations(self):
        # load the isd-history.csv
        self.stations = pd.read_csv(
            f'{self.baseURL}/isd-history.csv',
            converters = {'BEGIN':pd.to_datetime,'END':pd.to_datetime}
        )

        # construct an ID field from USAF and WBAN
        self.stations['ID'] = self.stations.apply(
            lambda row: f'{row.USAF}{str(row.WBAN).zfill(5)}',
            axis = 1
        )

        # make a geo-data-frame
        self.stations['geometry'] = self.stations.apply(
            lambda row: Point((row.LON,row.LAT)),
            axis = 1
        )
        self.stations = gpd.GeoDataFrame(
            self.stations,
            geometry = 'geometry',
            crs = 'epsg:4326'
        )

        # get the number of observations for each station by year
        # load the isd inventory
        self.inventory = pd.read_csv(
            f'{self.baseURL}/isd-inventory.csv.z',
            compression = 'gzip',
            low_memory = False,
            converters = {'BEGIN':pd.to_datetime,'END':pd.to_datetime}
        )

        self.inventory['ID'] = self.inventory.apply(
            lambda row: f'{row.USAF.zfill(6)}{str(row.WBAN).zfill(5)}',
            axis = 1
        )        

                
    def bestStation(self,lat,lon):
        if not hasattr(self,'stations'):
            self.getAllStations()
            
        # filter the stations that contain the month
        monthStart = pd.to_datetime(
            f'{self.year}{str(self.month).zfill(2)}01'
        )
        monthEnd = monthStart + pd.to_timedelta('30D')
        # also filter out stations without meaningful location info
        # ??? filter out stations without USAF
        self.candidates = self.stations[
            (self.stations.BEGIN < monthStart) &
            (self.stations.END > monthEnd) &
            ~(self.stations.LAT.isnull()) &
            ~(self.stations.LON.isnull()) &
            (self.stations.USAF != '999999')
        ].copy()

        # compute the distance from the passed lat,lon
        self.candidates['DIST'] = self.candidates.apply(
            lambda r: geodesic((lat,lon),
                               (r.geometry.y,r.geometry.x)).miles,
            axis = 1
        )
        
        # merge the number of observations
        self.candidates = pd.merge(
            self.candidates,
            self.inventory.query(f'YEAR == {self.year}')[
                ['ID',self.monthAbbr]
            ],
            on = 'ID'
        )

        # compute the sorting field
        factor = 100
        self.candidates['SORT'] = self.candidates[self.monthAbbr] - \
                                  factor*self.candidates.DIST

        # sort and save the ID of the top hit
        self.best = self.candidates.sort_values(
            'SORT'
        ).iloc[-1].squeeze()

        # output the ID
        self.dataPath = f'{self.best.USAF}{str(self.best.WBAN).zfill(5)}'
        with open('bestSurfaceStation.txt','w') as f:
            f.write(self.dataPath)
    

    def getAndSaveSurfaceData(self):
        fn = f'{self.best.USAF}-{str(self.best.WBAN).zfill(5)}-{self.year}.gz'
        with open(self.dataPath,'wb') as out:
            with FTP(self.host,'anonymous') as ftp:
                ftp.cwd(f'{self.directory}/{self.year}')
                with io.BytesIO() as f:
                    ftp.retrbinary(f'RETR {fn}',f.write)
                    out.write(gzip.decompress(f.getvalue()))


    def makeStage1Input(self,timeOffset = 6):
        with open('surface.inp','w') as inp:
            p = geopy.point.Point(self.best.LAT,self.best.LON)
            vals = [abs(float(c)) for c in p.format_decimal().split(',')]
            dirs = [c[-1] for c in p.format().split(',')]
            inp.write(self.sfc_template.format(
                self.dataPath,
                self.year % 100,
                self.month,
                # self.best.WBAN,
                str(self.best.WBAN).zfill(8),
                f'{vals[1]:.3f}{dirs[1]}',f'{vals[0]:.3f}{dirs[0]}',
                timeOffset,
                self.best['ELEV(M)']
            ))


    def makeAerSurfaceInput(self,nlcdZipPath):
        # define variables
        airport = 'AP' in self.best['STATION NAME'] or \
                  'AIRPORT' in self.best['STATION NAME']

        # extract the tiff files from the archive
        archive = zipfile.ZipFile(nlcdZipPath)

        # get the list of years available
        years = set(int(f.split('_')[1]) for f in
                    archive.namelist() if f.startswith('NLCD_2'))

        # select the year that is closest to self.year
        dist = 100
        selectedYear = None
        for year in years:
            if abs(self.year - year) < dist:
                dist = abs(self.year - year)
                selectedYear = year

        fileNames = {} # keys are 'cover','canopy', and 'imperv'
        matchData = {
            'cover':re.compile(f'NLCD_{selectedYear}_Land_Cover_L48.*[.]tiff$'),
            'canopy':re.compile(f'NLCD_{selectedYear}_Tree_Canopy_L48.*[.]tiff$'),
            'imperv':re.compile(f'NLCD_{selectedYear}_Impervious_L48.*[.]tiff$')
        }
        for filename in archive.namelist():
            if not filename.startswith('NLCD_2'): continue
            year = int(filename.split('_')[1])
            if year != selectedYear: continue
            for key,pattern in matchData.items():
                if pattern.search(filename):
                    fileNames[key] = filename
                    archive.extract(filename)
        
        with open('aersurface.inp','w') as inp:
            inp.write(self.asf_template.format(
                self.best['STATION NAME'],self.best['LAT'],self.best['LON'],
                fileNames['cover'],fileNames['canopy'],fileNames['imperv'],
                'AP' if airport else 'NONAP'
            ))
