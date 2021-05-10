# MOVES matrix transformer.

This directory deals with the MOVES matrix emission
rates constructed by the School of Civil Engineering at the Georgia
Tech and published by the CARTEEH at the Texas A\&M Transportation
Instutute at [https://carteehdata.org/library/dataset/moves-matrix-texas-emissi-e6a3](https://carteehdata.org/library/dataset/moves-matrix-texas-emissi-e6a3).

The script in this directory transforms the emission rates from being
sliced by the vehicle operating mode to being sliced by velocity bins
using the MOVES defaut operating mode distribution.  All MOVES
datasets utilized here (including meteorology, and age distribution)
are obtained directly from the SQL tables of the MOVES model
downloaded from the EPA's website.

### Resources and input preparation
1. Download the Excel dataset
   `s3://tti-data/MOVES/moves_matrix_coverage_04-15-2020.xlsx`.  The
   `IM_fuel` sheet contains the mapping from counties to fuel mix and
   maintenance regions.  Locate the imID and fuelID values for the
   counties you need to get the rates for.  Download the MOVES matrix
   files from S3 for the required fuel/IM region and year.  For
   example, `s3://tti-data/MOVES/f10i0_2015.zip` contains the rates
   for fuelID = 10, imID = 0, and year = 2015.
2. Make a directory where all MOVES files will reside and place
   `MOVES20181022_zoneMonthHour.csv` and `default_opmode_project.csv`
   from `s3://tti-data/MOVES/` along with the already downloaded
   `moves_matrix_coverage_04-15-2020.xlsx` into it.  Unzip the
   downloaded MOVES matrix rates into the MOVES directory.
3. Prepare the `age_distribution.csv` dataset with
   countyID,sourceTypeID,yearID,ageID,ageFraction columns and place it
   into the MOVES directory.  If localized vehicle age distributions
   are not available, the MOVES default age distribution (average over
   the whole US), found at
   `s3://tti-data/MOVES/MOVES20181022_sourceTypeAgeDistribution.csv`
   can be used instead (renamed to `age_distribution.csv`).  The
   columns are:
   - countyID: 5 digit county FIPS
   - sourceTypeID: MOVES source type ID
   - yearID: the year of the scenario
   - ageID: age of the vehicle
   - ageFraction: given fixed yearID and sourceTypeID, ageFractions
     must add up to 1.

### Running the transformer.
Let's assume that all of the MOVES files are in the directory called
MOVES.  Then the MOVES transformer is run as follows:

```bash
$ python3 transformMoves.py 48137,48167 2020 7 MOVES
```

The first command line argument is the comma separated list of county
FIPS, the second and third are the year and month of the scenario and
the last is the path to the directory where all of the MOVES rates as
well as the auxiliary files reside.  The script will output a single
csv with transformed rates named `movesRates_YEAR-MONTH_FIPSLIST.csv`
where YEAR and MONTH are those supplied on the command line and
FIPSLIST is dash delimited list of the supplied FIPS.

### Comment regarding the dummy "fuelTypeID" column in the constructed emission rate dataset.

The MOVES matrix emission rates aggregate all fuel types together
using the MOVES default fuel type distributions by source type.
However, the emissions calculator published here requires the
"fuelTypeID" column.  Therefore the transformer script adds a dummy
fuelTypeID column with value 0.  It can be safely ignored in the
emission dataset that is produced by the emissions calculator.
