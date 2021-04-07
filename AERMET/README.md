# Pipeline for preparing surface and upper air data for AERMOD

This directory contains the scripts to use EPA's AERMET, AERSURFACE,
and AERMINUTE tools to prepare the upper air profile and surface wind
data necessary for running AERMOD.

### Installation
1. Install unzip, gfortran, and python3
```bash
$ sudo apt install unzip gfortran python3 python3-pip
```
2. Download and compile AERMET
```bash
$ wget --no-check-certificate https://gaftp.epa.gov/Air/aqmg/SCRAM/models/met/aermet/aermet_source.zip
$ unzip -d AERMET aermet_source.zip
$ cd AERMET
$ gfortran -fbounds-check -Wuninitialized -O2 -c mod_AsosCommDates.for
$ gfortran -fbounds-check -Wuninitialized -O2 -c *.FOR
$ gfortran -O2 -o ../aermet *.o
```
3. Download and compile AERSURFACE
```bash
$ wget --no-check-certificate https://gaftp.epa.gov/Air/aqmg/SCRAM/models/related/aersurface/aersurface_source.zip
$ unzip aersurface_source.zip
$ cd aersurface_source_code
$ gfortran -fbounds-check -Wuninitialized -O2 -c mod_StartVars.f mod_Constants.f mod_UserParams.f mod_FileUnits.f mod_ErrorHandling.f mod_Geographic.f mod_ProcCtrlFile.f mod_LandCoverParams.f mod_TiffTags.f mod_TiffParams.f mod_InitTiffParams.f mod_GetData.f mod_AvgParams.f mod_SfcChars.f aersurface.f
$ gfortran -o ../aersurface -O2 *.o
```
4. Download and compile AERMINUTE
```bash
$ wget --no-check-certificate https://gaftp.epa.gov/Air/aqmg/SCRAM/models/met/aerminute/aerminute_15272.zip
$ unzip -d AERMINUTE aerminute_15272.zip
$ cd AERMINUTE
$ fortran -O2 -o ../aerminute aerminute_15272.for
```
5. Install the required Python libraries
```bash
$ pip3 install -r requirements.txt
```
6. Download the National Land Cover Database (NLCD) data from
   https://mrlc.gov/viewer using the data download tool (clicking on
   an icon that looks like a down pointing arrow in a circle) to draw
   a rectangle bigger than the study area and selecting the 2016 Tree
   Canopy, Land Cover, and Impervious datasets.  You receive an email
   with the download link for the zip archive with all of the data
   (e.g. NLCD_m7XNYdavHDHGq4P0NPji.zip).

### Running the pipeline

The bash script `runPipeline.sh` requires 5 command line arguments:
year, month, latitude, longitude, and the path to the downloaded NLCD
zip archive
.  For example:
```bash
$ bash runPipeline.sh 2018 7 38.9996681 -77.0449321 ~/Downloads/NLCD_m7XNYdavHDHGq4P0NPji.zip
```
If successful, it generates 4 outputs:
- bestSurfElev.txt contains the elevation above sea level in
  meters of the best match surface weather station
- bestUpperStation.txt contains the WBAN-WMO of the best match upper air
  monitoring weather station
- bestSurfaceStation.txt with the USAF-WBAN of the best match surface
  station
- AERMETSURFACE.SFC is the surface data input for AERMOD
- AERMETUPPER.PFL is the upper air profile input for AERMOD
