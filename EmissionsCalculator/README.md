# Emissions calculator

Broadly speaking, the `computeEmissions.py` python script accepts the
link aggregated VMT produced by the DynusT parser, the on-road vehicle
mix fractions, and the running emission rates and computes the total
emissions by pollutant for each link aggregated over the DynusT
simulation interval (usually 24 hours) attributable to different MOVES
source types.

### Input preparation

1. `linkVMT.csv` produced by the DynusT parser can use used as is.
2. The emission rates CSV must be prepared with the following columns
   whose meaning is parallel to those in the EPA MOVES model
   documentation:
   - pollutantID
   - avgSpeedBinID (must be derived from the same speed bin size as
     used in aggregating VMT)
   - processID (processID = 1, or running emissions)
   - hourID
   - roadTypeID
   - sourceTypeID
   - fuelTypeID (1 - gasolune, 2 - diesel)
   - ratePerDistance (in gram/mile)
   - countyID (5 digit county FIPS)
   - yearID (4 digit year)
3. The on-road vehile mix CSV must have the following columns:
   - yearID (4 digit year)
   - dayOfTheWeek with possible values of [WK|FR|SA|"SU"] (WK refers
     to Monday through Thursday (inclusive)
   - roadTypeID
   - sourceTypeID
   - countyID (5 digit FIPS)
   - VMTmix : fractions that must add up to 1 for every combination of
     all other attributes fixed *except* sourceTypeID
4. `vehTypeMap.yaml` which cointains the mapping from the DynusT's
   vehicle types to MOVES source type ID groups in yaml format.  For
   example:
	```yaml
	1:[11,21,31,32]
	2:[51,52,53,54]
	3:[61,62]
	```

### Output

The script requires 4 command line arguments:
- pathToVMXcsv
- pathToRatesCSV
- year
- numberOfCPUs (number of CPU cores to run on).  For example
```bash
$ python3 computeEmissions.py ../vmx.csv ../rates.csv 2020 18
```
The single output of the script is `emissions_year.csv` where year is
replaced by the 4 digit year supplied on the command line.  The
columns are 
- linkID composed of the origin and destination node IDs separated by
  a dash
- pollutantID 
- sourceTypeID
- fuelTypeID
- emquant (total emissions in grams, grams/mole or Joules depending on
  the pollutantID)
  
Please refer to the EPA MOVES documentation for the meaning and
possible values of pollutantID, sourceTypeID, roadTypeID, fuelTypeID,
and processID.
