import pandas as pd
from rtree import index
from ftplib import FTP
import io
import pytz
from datetime import datetime
import math
import os.path

class ASOS(object):
    host = 'ftp.ncdc.noaa.gov'
    directory = 'pub/data/asos-onemin'
    def __init__(self,year,month,tz,home):
        self.year = year
        self.month = month
        self.home = home
        # compute the UTC offset
        dt = pytz.timezone(tz).utcoffset(datetime(year,month,1))
        tz = '-' if dt.days < 0 else '+'
        tz += str(int(dt.seconds/3600)).zfill(2)
        minutes = int(60*math.modf(dt.seconds/3600)[0])
        tz += str(minutes).zfill(2)
        # read the stations, filter on ASOS
        self.stations = pd.read_csv(
            os.path.join(home,'stations.csv'),
            converters = {
                'Archive Begins':pd.to_datetime,
                'Archive Ends':pd.to_datetime
            }
        )
        self.stations = self.stations[
            self.stations['IEM Network'].str.contains('ASOS')
        ]

        # filter out stations that dont cover the whole month
        self.start = pd.to_datetime(
            f'{year}{str(month).zfill(2)}{tz}',format = '%Y%m%z'
        )
        month += 1
        if month == 13:
            month = 1
            year += 1
        self.end = pd.to_datetime(
            f'{year}{str(month).zfill(2)}{tz}',format = '%Y%m%z'
        )
        self.stations = self.stations[
            (self.stations['Archive Begins'] < self.start) &
            ((self.stations['Archive Ends'] > self.end) |
             (self.stations['Archive Ends'].isnull()))
        ]
        
        # construct the rtree index
        self.idx = index.Index()
        for i,station in self.stations.iterrows():
            x = station.Longitude1
            y = station.Latitude1
            self.idx.insert(i,(x,y,x,y))

        # read the AERMINUTE input file template
        self.template = open(os.path.join(home,'aermin_template.inp')).read()
                            

    def getAvailable(self):
        with FTP(self.host,'anonymous') as ftp:
            files = ftp.nlst(f'{self.directory}/6405-{self.year}')

        self.available = {}
        for filename in files:
            if not filename.endswith('.dat'): continue
            filename = filename.split('/')[-1]
            month = int(filename[-6:-4])
            if month != self.month: continue
            call = filename[6:9]
            letter = filename[5]
            self.available[call] = letter
            

    def bestStation(self,lat,lon):
        nearest = list(self.idx.nearest((lon,lat,lon,lat),3))
        # iterate over the indices and keep the first available
        for idx in nearest:
            ID = self.stations.loc[idx].ID
            if ID in self.available:
                self.best = self.available[ID] + ID
                return

        print('Did not find an ASOS station for',lat,lon)
        self.best = None


    def downloadData(self):
        fn = f'64050{self.best}{self.year}{str(self.month).zfill(2)}.dat'
        self.dataPath = fn
        with open(self.dataPath,'wb') as out:
            with FTP(self.host,'anonymous') as ftp:
                ftp.cwd(f'{self.directory}/6405-{self.year}')
                with io.BytesIO() as f:
                    ftp.retrbinary(f'RETR {fn}',f.write)
                    out.write(f.getvalue())


    def bestIsIFW(self):
        # download the ice free wind install dates
        install = pd.read_csv(os.path.join(self.home,'ice-wind.csv'))
        install['INSTALL DATE'] = pd.to_datetime(
            install['INSTALL DATE'],errors = 'coerce'
        )
        row = install[install.ID == self.best[1:]]
        if len(row) != 1: return False
        installDate = row.squeeze()['INSTALL DATE']
        if pd.isnull(installDate): return False
        date = pd.to_datetime(f'{self.year}{self.month}',format = '%Y%m')
        if installDate > date: return False
        self.ifwDate = installDate
        return True


    def makeInput(self):
        ifw = self.bestIsIFW()
        self.hour_file = f'{self.best}_{self.year}-{self.month}.DAT'
        with open('aerminute.inp','w') as f:
            f.write(self.template.format(
                start_month = self.start.month,
                start_year = self.start.year,
                end_month = self.start.month, # same as start
                end_year = self.start.year,
                ifw_status = 'Y' if ifw else 'N',
                comm_month = self.ifwDate.month if ifw else '',
                comm_day = self.ifwDate.day if ifw else '',
                comm_year = self.ifwDate.year if ifw else '',
                input_file = self.dataPath,
                hour_file = self.hour_file
            ))
