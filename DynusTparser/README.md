## DynusT parser

Inputs: `output_vehicle.dat.bz2`, `vehTrajectory.dat.bz2`,
`links.csv`; optional input: `elecIDs.txt`.  Outputs: `linkVMT.csv`
and `linkData.csv`.

### Requirements
1. `csv.h` from [https://github.com/ben-strasser/fast-cpp-csv-parser](https://github.com/ben-strasser/fast-cpp-csv-parser) placed into the source code directory.
2. Libboost `system`, `filesystem` and `iostreams`.  On a Debian-derived Linux distribution:
```bash
$ sudo apt install libboost-system-dev libboost-iostreams-dev libboost-filesystem-dev
```

### Compilation
```bash
$ make
```
Should yield an executable `volumes.exe`

### Input preparation
1. Make a working directory and copy DynusT's outputs into it.  Compress with bzip2.
2. Prepare `links.csv` with a row for each link in the network with
   column names: "linkID","roadTypeID","fips","length","speedLimit".
   1. "linkID" is a composed from the IDs of the origin and destination
	  nodes separated by a dash, e.g. "2342-5673".
   2. "roadTypeID" is the EPA MOVES road types: you will need to
      develop a mapping from the DynusT road types to the MOVES
	  road types.
   3. "fips" is the 5 digit county identifier into which most of the
	  link happens fall.
   4. "length" is in miles.
   5. "speedLimit" is in mph.
3. Optionally, one may prepare `elecIDs.txt` which contains the list
of vehicle IDs (one per line) to be removed from the DynusT roster
before computing the aggregate link VMT.

### Running the parser

The parser requires two command line arguments: the first one is
`aggInt`, the length (in minutes) of the time interval to aggregate
volumes into.  The output will contain intervalIDs starting from 1 and
ending with `1440/aggInt`.  The second command line argument is
`speedBin` which is the size of the speed bins in mph.  The highest
possible speed is 80 mph.  Therefore, if, for example `speedBin = 5`,
there will be 16 speed bins from 1 to 16 (inclusive).  In the below
example, VMT is aggregated into hour intervals and 5 mph speed bins.
```bash
$ ./volumes.exe 60 5
```

### Outputs

The program `volumes.exe` will output two comma separated value files.
1. `linkVMT.csv` with columns: linkID,vehType,timeIntervalID,avgSpeedBinID,vmt
2. `linkData.csv` with columns: linkID,vehType,metric,unit,value
   contains link metrics that are aggregated over the whole DynusT
   simulation time window.  Metrics include: VMT, delay, signalDelay,
   and toll (if present in `VehTrajectory.dat`).  All metrics are
   available by vehicle type.
