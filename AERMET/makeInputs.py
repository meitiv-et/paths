#!/usr/bin/env python3

import sys

if len(sys.argv) != 6:
    print('Usage:',sys.argv[0],'year','month','lat','lon','pathToNLCDzip')
    sys.exit(1)

year = int(sys.argv[1])
month = int(sys.argv[2])
lat = float(sys.argv[3])
lon = float(sys.argv[4])
archive = sys.argv[5]

import ncei

isd = ncei.ISD(year,month)
isd.bestStation(lat,lon)
print('Getting surface data for',isd.best['STATION NAME'])
isd.getAndSaveSurfaceData()
isd.makeStage1Input()
isd.makeAerSurfaceInput(archive)
# save the station elevation
with open('bestSurfElev.txt','w') as f:
    f.write(str(isd.best['ELEV(M)']))

import radiosonde

rsd = radiosonde.RadioSonde(year,month)
rsd.bestStation(lat,lon)
print('Getting upper air data for',rsd.best.WBAN)
rsd.saveData()
rsd.makeStage1Input()
with open('bestUpperStation.txt','w') as f:
    f.write(f'{rsd.best.WBAN.zfill(5)}{rsd.best.WMO.zfill(5)}')

# get timezone
from timezonefinder import TimezoneFinder
tzf = TimezoneFinder()
tz = tzf.timezone_at(lat = lat,lng = lon)
print('Using',tz)

# make AERMINUTE input and get ASOS data
import asos
asos1min = asos.ASOS(year,month,tz)
asos1min.getAvailable()
asos1min.bestStation(lat,lon)
print('Getting ASOS 1 min data for',asos1min.best)
asos1min.downloadData()
asos1min.makeInput()

# make the stage 2 input
twoDigitYear = year - 100*int(year/100)
with open('STAGE2.INP','w') as f:
    f.write(
        open('merge_template.inp').read().format(
            asos_file = asos1min.hour_file,
            year = twoDigitYear,
            month = month
        )
    )
