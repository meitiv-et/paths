#!/bin/bash

if [ $# -ne 5 ]; then
    echo Usage: $0 year month lat lon NLCDdataPath
    exit 1
fi

year=$1
month=$2
lat=$3
lon=$4
nlcd=$5

./makeInputs.py $year $month $lat $lon $nlcd
./aersurface aersurface.inp > /dev/null
echo aerminute.inp|./aerminute > /dev/null
./aermet surface.inp > /dev/null
./aermet upperair.inp > /dev/null
./aermet STAGE2.INP > /dev/null
./aermet STAGE3.INP > /dev/null

