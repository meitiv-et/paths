# Use EPA's AERMOD model to compute the dispersion of PM2.5 emitted on roadways 
Combine the geometries of the transportation network links, 24 hour
emissions on each link, and the meteorologic parameters computed using
the AERMET pipeline to produce a set of receptor coordinates with the
24 hour average PM2.5 concentrations.

### Installation
1. Install `gfortran` and a tool to covert windows encoded files to unix
   ```bash
   $ sudo apt install gfortran dos2unix
   ```
2. Install the required Python modules
   ```bash
   $ pip3 install -r requirements.txt
   ```
2. Download and compile AERMOD (check for the latest version)
   ```bash
   $ wget --no-check-certificate https://gaftp.epa.gov/Air/aqmg/SCRAM/models/preferred/aermod/aermod_source.zip
   $ unzip aermod_source.zip
   $ cd aermod_source_XXXXX (replace XXXXX with the aermod version)
   $ dos2unix gfortran*.bat
   $ for f in `grep '%COM' gfortran*.bat|tr -d ' \t'|awk -F'%' '{print $NF}'`; do gfortran -O2 -c $f; done
   $ gfortran -O2 -o ../aermod *.o
   ```

### Input preparation
To run the AERMOD pipeline one needs to prepare the following inputs
1. The emissions CSV (can be compressed) with at minimum
   `"linkID","pollutantID","emquant"` columns.  The `"linkID"` must be
   the origin and destination node IDs separated by a dash.
2. A dataset with the link geometries (in any format that `geopandas`
   can read, such as shapefile, geojson, geopackage, etc).  Besides
   the geometry each link needs to have at least the
   `"A_NODE","B_NODE","#LANES"` attributes.
3. The outputs of running the `AERMET` pipeline.

### Running the AERMOD pipeline
1. Make the sources and receptors
   ```bash
   $ python3 makeSourcesReceptors.py --epsg EPSG LINKS EMISSIONS
   ```
   where `EPSG` is replaced by the epsg to use (if omitted, 3665 will be
   used), `LINKS` is replaced by the path to the dataset with link
   geometries, and `EMISSIONS` is replaced by the path to the dataset
   with the emissions.  This script will use all available CPUs and
   will create `sources.geojson` and `receptors.geojson`.
2. Split the sources into groups and make the `AERMOD`
   inputs for each source group
   ```bash
   $ python3 makeInputs.py TITLE AERMET sourcesPerGroup POP DAY
   ```
   where `TITLE` is replaced by an arbitrary string (without spaces),
   `AERMET` is replaced by a path to the directory with the results of
   running the `AERMET` pipeline, `sourcesPerGroup` is an integer
   specifying the number of sources in each group, `POP` is the
   population size of the urban study area, and `DAY` is the day of
   the month for which to use the meteorology data.
   This script will read `sources.geojson` and `receptors.geojson` and
   create an `.inp` file for every source group.
3. Run `AERMOD` for every source group input file
   ```bash
   $ bash run.sh
   ```
   This will use all available CPUs and produce a `*.out` file for
   each `*.inp` file.
4. Assemble the `*.out` files together into a CSV
   ```bash
   $ python3 combineOuts.py
   ```
   This script must be run from the directory where the only `*.out`
   files are those to be integrated together as it does not do any
   sort of filtering and attempts to read all `*.out` files.  This
   script will produce `receptorConc.csv` with
   `"x","y","concentrat","paf"` columns.  The concentrations are in
   micrograms per meter cubed.  The last column (paf) is population
   attribitable asthma fraction which varies between 0 and 1.  The
   source of the association between the average PM2.5 concentration
   and asthma can be found in a manuscript entitled [Traffic related air pollution and the burden of childhood asthma in the contiguous United States in 2000 and 2010](https://pubmed.ncbi.nlm.nih.gov/30954275/).
5. Restore receptor IDs
   ```bash
   $ python3 restoreIDs.py
   ```
   This script will overwrite `receptorConc.csv` and replace the
   receptor coordinates `"x","y"` with the `"receptorID"` column.  The
   receptors can be matched to those in `receptors.geojson` by
   `receptorID`.
