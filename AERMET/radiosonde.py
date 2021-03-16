'''this library provides a way to download the upper air soundings in
FSL format given a state and a date range'''

import requests
from datetime import datetime
import geopy
from geopy.distance import geodesic
import re
import sys
import shapely.geometry as gm
import geopandas as gpd

class RadioSonde(object):
    formURL = 'https://ruc.noaa.gov/raobs/GetRaobs.cgi'
    delta = 3.
    def __init__(self,year,month):
        self.year = year
        self.month = month
        self.data = {}
        self.data['shour'] = 'All Times'
        self.data['ltype'] = 'All Levels'
        self.data['wunits'] = 'Tenths of Meters'
        self.data['oformat'] = 'FSL format (ASCII text)'
        self.data['osort'] = 'Station Series Sort'
        self.data['bdate'] = f'{year}{str(month).zfill(2)}0100'
        self.data['edate'] = f'{year}{str(month).zfill(2)}3123'
        self.template = open('ua_template.inp').read()


    def getDataByState(self,state):
        self.data['access'] = 'State'
        self.data['States'] = [state]
        result = requests.get(self.formURL,params = self.data)
        if result.status_code != 200:
            self.result =  None
        else:
            self.result = result.content
        

    def getDataByLatLon(self,lat,lon):
        self.data['access'] = 'Lat / Lon Coordinates'
        self.data['blon'] = lon - self.delta
        self.data['blat'] = lat - self.delta
        self.data['elon'] = lon + self.delta
        self.data['elat'] = lat + self.delta
        result = requests.get(self.formURL,params = self.data)
        if result.status_code != 200:
            self.result = None
        else:
            self.result = result.content


    def extractStations(self):
        self.stations = None
        if self.result is None or \
           re.search('No data',self.result.decode()): return
        
        stations = set()
        pattern = re.compile(r'\d+[.]\d*[NWSE]')        
        for line in self.result.splitlines():
            line = line.decode()
            if pattern.search(line):
                stations.add((
                    line[7:14].strip(),
                    line[14:21].strip(),
                    line[21:29].strip(),
                    line[29:36].strip()
                ))

        rows = []
        for s in stations:
            p = geopy.point.Point(f'{s[2]} {s[3]}')
            rows.append({
                'WBAN':s[0],'WMO':s[1],'LAT':s[2],'LON':s[3],
                'geometry':gm.Point((p[1],p[0]))
            })

        if rows:
            self.stations = gpd.GeoDataFrame(
                rows,geometry = 'geometry',crs = 'epsg:4326'
            )


    def bestStation(self,lat,lon):
        self.best = None
        if not hasattr(self,'result'):
            self.getDataByLatLon(lat,lon)
            
        if not hasattr(self,'stations'):
            self.extractStations()
            
        if self.stations is None:
            print('No stations')
            self.best = None
            return

        self.stations['DIST'] = self.stations.apply(
            lambda row: geodesic(
                (lat,lon),(row.geometry.y,row.geometry.x)
            ).miles,
            axis = 1
        )

        self.best = self.stations.sort_values(
            'DIST'
        ).iloc[0].squeeze()


    def saveData(self):
        if self.best is None:
            print('Did not find the best station')
            sys.exit(1)
        self.dataPath = f'{self.best.WBAN}.FSL'
        with open(self.dataPath,'wb') as f:
            f.write(self.result)


    def makeStage1Input(self):
        with open('upperair.inp','w') as inp:
            inp.write(self.template.format(
                self.dataPath,
                self.year % 100,
                self.month,
                str(self.best.WBAN).zfill(8),
                self.best.LAT,self.best.LON
            ))
