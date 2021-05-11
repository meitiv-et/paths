## DynusT parser

Inputs: `output_vehicle.dat.bz2`, `VehTrajectory.dat.bz2`,
`links.csv`; optional input: `elecIDs.txt`.  Outputs: `linkVMT.csv`,
`linkData.csv`, and `numberOfTrips.csv`.

### Requirements
1. `csv.h` from
   [https://github.com/ben-strasser/fast-cpp-csv-parser](https://github.com/ben-strasser/fast-cpp-csv-parser)
   placed into the source code directory.
2. Libboost `system`, `filesystem` and `iostreams`.  On a
   Debian-derived Linux distribution:
```bash
$ sudo apt install libboost-system-dev libboost-iostreams-dev libboost-filesystem-dev
```
3. GNU C++ compiler.  If you would like to use a different compiler,
   modify the first line of the `Makefile`.  Some of the compatibility
   flags may need to be modified as well.

### Compilation
```bash
$ make
```
should yield an executable `volumes.exe`

### Input preparation
1. Make a working directory and copy DynusT's outputs
   `VehTrajectory.dat` and `output_vehicle.dat` into it.
   Compress with bzip2.
2. Prepare `links.csv` with a row for each link in the network with
   column names: "linkID","roadTypeID","fips","length","speedLimit"
   and place it into the working directory.  The columns:
   - "linkID" is composed from the IDs of the origin and destination
     nodes separated by a dash, e.g. "2342-5673".
   - "roadTypeID" is the EPA MOVES road type: you will need to develop
      a mapping from the DynusT road types to the MOVES road types
      (more about this mapping in the `EmissionsCalculator` README.
   - "countyID" is the 5 digit county identifier into which most of the
     link happens to fall.
   - "length" is in miles.
   - "speedLimit" is in mph.
   This repository contains a python3 script `makeLinks.py` which can
   be used to transform the DynaStudio links `shapefile` into the
   `csv` needed by the parser.  To use this script first install
   geopandas
   ```bash
   $ pip3 install -r requirements.txt
   ```
   and then run
   ```bash
   $ python3 makeLinks.py pathToShapeFile
   ```
3. Optionally, one may prepare `elecIDs.txt` containing a list of
vehicle IDs (one per line) to be removed from the DynusT roster before
computing the aggregate link VMT.  This file must be placed in the
project directory and will be read automatically if exists.

### Running the parser

The parser requires two command line arguments: the first one is
`aggInt`, the length (in minutes) of the time interval to aggregate
volumes into.  The output will contain timeIntervalIDs starting from 1
and ending with `1440/aggInt`.  The second command line argument is
`speedBin` which is the size of the speed bins in mph.  The highest
possible speed is 80 mph.  Therefore, if, for example `speedBin = 5`,
there will be 16 speed bins from 1 to 16 (inclusive).  In the below
example, VMT is aggregated into hour intervals and 5 mph speed bins.
The program must be run while in the working directory.  In the
example below the program `volumes.exe` is located in the parent
directory.
```bash
$ cd ProjectDirectory
$ ../volumes.exe 60 5
```

### Outputs

The program `volumes.exe` will output two comma separated value files.
1. `linkVMT.csv` with columns:
   linkID,vehType,timeIntervalID,avgSpeedBinID,vmt.  The
   timeIntervalID columns contains the IDs of the aggregation
   intervals that start with 1 (not 0).
2. `linkData.csv` with columns: linkID,vehType,metric,unit,value
   contains link metrics that are aggregated over the whole DynusT
   simulation time window.  Metrics include: VMT, delay, signalDelay,
   and toll (if present in `VehTrajectory.dat`).  All metrics are
   available by vehicle type.
3. `numberOfTrips.csv` contains the total number of trips in the
   roster by vehicle type, after the trips with IDs in the
   `elecIDs.txt` have been removed.
