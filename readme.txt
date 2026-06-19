### README.txt ###
This project folder is the implementation of the simulation model.
We decided to separate parts with different functions for readability and oversight.

### FILES ###
AGV_experiment.py                -- Running this file will run the experiments and print results.

AGV_sim.py                       -- This file contains the simulation upper structure, initializing classes and the environment, 
                                    as well as containing the base input parameters list.

simulation_classes.py            -- This file contains the implementation of all the classes and functions used in the simulation

data_analysis_plots.py           -- Contains the code behind the data analysis

carbon_intensity_seasonal.csv    -- Contains the csv carbon intensity data used as input to the simulation.

queue_plotting.py                -- Contains code for plotting queue development over simulation runtime

Verification files folder        -- Contains files named in a similar manner to the main folder, 
                                    but these files were used for verification and contain all the print statements,
                                    separated for readability and oversight
