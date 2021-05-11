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

directory=`dirname $0`

${directory}/makeInputs.py $year $month $lat $lon $nlcd
${directory}/aersurface aersurface.inp > /dev/null
echo aerminute.inp|${directory}/aerminute > /dev/null
${directory}/aermet surface.inp > /dev/null
${directory}/aermet upperair.inp > /dev/null
${directory}/aermet STAGE2.INP > /dev/null
${directory}/aermet ${directory}/STAGE3.INP > /dev/null

