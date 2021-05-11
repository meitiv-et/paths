#!/bin/bash

numThreads=`nproc`
numThreads=$((numThreads / 2))
home=`dirname $0`

runInput() {
    base=$1
    ${home}/aermod ${base}.inp /dev/null > /dev/null &&
	# remove empty lines
	awk '$3>0' ${base}.out > ${base}_shrink.out &&
	/bin/mv ${base}_shrink.out ${base}.out &&
	/bin/rm ${base}.inp
}

inpFiles=`ls *.inp`
for inpFile in $inpFiles; do
    # wait if already fully loaded
    while [ `ps -C aermod|grep -v PID|wc -l` -ge $numThreads ]; do
	sleep 30
    done

    base=`basename $inpFile .inp`
    
    # check if the .out already exists, and skip aermod if it does
    if [ -s ${base}.out ]; then
	continue
    fi

    echo Processing $base
    runInput $base &
    
    sleep 3
done
