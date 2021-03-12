# Platform to Assess Transportation, Health, and Sustainability (PATHS).

A set of scripts to process DynusT trajectories to compute tailpipe
emissions and the dispersion of PM2.5

### Directory structure (for more detailed instructions for using the scripts in each directory, please refer to the README.md in that directory)

1. `DynusTparser`: code to read DynusT `output_vehicle.dat` and
   `VehTrajectory.dat` toghether with a `links.csv` which defines the
   network and output VMT for every link in the network sliced by
   arbitrarty time intervals, vehicle type, and speed.
2. `EmissionsCalculator`: code to combine the link aggregated volume,
   on-road vehicle mix, and emission rates into the total emissions
   for each link in the network sliced by the MOVES source type, fuel
   type, and pollutant.
3. `TransformMovesMatrix`: code to transform the MOVES matrix
   emissions rates from being binned by operation mode to being binned
   by speed using the MOVES default operation mode distribution.
