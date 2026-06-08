import salabim as sim
from math import floor
import random
import numpy as np
import pandas as pd

#Import the main classes from the simulation_classes.py file
#To keep this file more organized
from simulation_classes import AGV, Crane, ChargingStation, VesselGenerator

#Standard/example dict of inputs. Can be modified in a loop for sensitivity analysis and experimentation with different scenarios.
TravelDistanceQuayToYard = 500
ChargerLocation = 0.5

INPUT_PARAMETERS = dict(
    AGVSpeed                         = 4.5,  # m/s
    
    ChargerLocation                  = 0.5,              # relative location of charger between yard and quay (0-1)
    TravelDistanceQuayToYard         = TravelDistanceQuayToYard,              # fixed travel time, empty AGV (seconds)
    TravelDistanceYardToCharger      = TravelDistanceQuayToYard * ChargerLocation,        #TravelDistanceQuayToYard*ChargerLocation,         # fixed travel time, AGV to charger (seconds)
    TravelDistanceChargerToQuay      = TravelDistanceQuayToYard * (1 - ChargerLocation),  #TravelDistanceQuayToYard*(1 - ChargerLocation),   # fixed travel time, AGV to quay (seconds)

    PickupDuration                   = 30,   # time to pick up one container (seconds)
    DropoffDuration                  = 30,   # time to drop off one container (seconds)
    
    CraneCycleTimeMin                = 90,      # time to unload one container (seconds)
    CraneCycleTimeMax                = 144,     # time to unload one container (seconds)

    EnergyLoaded                     = 2.5,      # kWh consumed per loaded trip
    EnergyEmpty                      = 1.4,      # kWh consumed per empty trip
    BatteryCapacity                  = 200,     # usable battery capacity (kWh)

    ChargeRate                       = 300,      # charge rate (kW)

    SoCThreshold                     = 0.7,     # dispatch threshold for charging request
    SubstationCapacity               = 400,     # grid ceiling (kW) - sensitivity parameter

    NrChargingStations               = 2,        # number of charging stations
    NrCranes                         = 2,        # number of quay cranes
    
    FleetSize                        = 5,                # number of AGVs in fleet
    WarmUpPeriod                     = 24 * 3600,        # seconds
    ObservationPeriod                = 28 * 24 *3600,    # seconds
    
    ContainersPerVessel              = 294,      # fixed container count per vessel arrival
    
    CheckInterval                    = 50,       # time between grid ceiling checks when AGV is waiting to charge (seconds)

    VesselInterArrivalMean           = 12096,    # mean inter-arrival time for vessels (seconds)

    SoCInit                          = 1.0,      # initial state of charge for all AGVs
    StateInit                        = "IDLE"    # initial state for all AGVs
       
)

#Load carbon intensity data
CARBON_INTENSITY = pd.read_csv("carbon_intensity_seasonal.csv", parse_dates=['hour'])
  
#Main simulation run function. Use in a loop for sensitivity and design of experiments.
def run_simulation(input_parameters=INPUT_PARAMETERS, 
                   carbon_intensity=CARBON_INTENSITY,
                   seed=42): 

    """
    Main simulation function. Initializes environment, creates components, and runs the simulation.
    Inputs:
        input_parameters: dict of all model parameters (travel times, energy use, fleet size, etc.)
        carbon_intensity: DataFrame with hourly carbon intensity values for the year
        seed: random seed for reproducibility
    """
    
    #Initialize parameters from input dictionary
    AGVSpeed              = input_parameters["AGVSpeed"]
    
    TravelDistanceQuayToYard         =  input_parameters["TravelDistanceQuayToYard"]
    TravelDistanceYardToCharger      =  input_parameters["TravelDistanceYardToCharger"]
    TravelDistanceChargerToQuay      =  input_parameters["TravelDistanceChargerToQuay"]
    
    PickupDuration        =  input_parameters["PickupDuration"]
    DropoffDuration       =  input_parameters["DropoffDuration"]
    CraneCycleTimeMin        =  input_parameters["CraneCycleTimeMin"]
    CraneCycleTimeMax        =  input_parameters["CraneCycleTimeMax"]
    
    EnergyLoaded          =  input_parameters["EnergyLoaded"]
    EnergyEmpty           =  input_parameters["EnergyEmpty"]
    BatteryCapacity       =  input_parameters["BatteryCapacity"]
    ChargeRate            =  input_parameters["ChargeRate"]
    SoCThreshold          =  input_parameters["SoCThreshold"]
    
    SubstationCapacity    =  input_parameters["SubstationCapacity"]
    
    NrChargingStations    =  input_parameters["NrChargingStations"]  
    NrCranes              =  input_parameters["NrCranes"]   
    FleetSize             =  input_parameters["FleetSize"]  
    
    WarmUpPeriod          =  input_parameters["WarmUpPeriod"]  
    ObservationPeriod     =  input_parameters["ObservationPeriod"] 
     
    ContainersPerVessel   =  input_parameters["ContainersPerVessel"] 
     
    CheckInterval         =  input_parameters["CheckInterval"] 
    
    VesselInterArrivalMean =  input_parameters["VesselInterArrivalMean"] 

    SoCInit = input_parameters["SoCInit"]   
    StateInit = input_parameters["StateInit"]  

    
    #Create counter for KPI and state tracking (dict type for mutability)
    counters = {
        "TotalCO2": 0,
        "CompletedContainers": 0,
        "CompletedVessels": 0,
        "CurrentGridLoad": 0,
        "ArrivedVessels": 0
    }

    #Initialize environment
    env = sim.Environment(trace=False, random_seed=seed)

    #Create and store components for easier access
    AGVList = []
    ChargingStationsList = []
    CranesList = []

    #Global queues
    MyJobQueueGlobal = sim.Queue("MyJobQueueGlobal")
    MyChargingQueue = sim.Queue("MyChargingQueue")
    MyVesselQueue = sim.Queue("MyVesselQueue")

    #Create components and start generator
    for i in range(NrChargingStations):
        cs = ChargingStation(ChargeRate=ChargeRate,
                            MyChargingQueue=MyChargingQueue,
                            SubstationCapacity=SubstationCapacity,
                            BatteryCapacity=BatteryCapacity,
                            CheckInterval=CheckInterval,
                            AGVList=AGVList,
                            MyJobQueueGlobal=MyJobQueueGlobal,
                            SoCThreshold=SoCThreshold,
                            CarbonIntensity=carbon_intensity,
                            counters=counters)
        
        ChargingStationsList.append(cs)

    for j in range(NrCranes):
        crane = Crane(MyVesselQueue=MyVesselQueue,
                MyJobQueueGlobal=MyJobQueueGlobal,
                CraneCycleTimeMin=CraneCycleTimeMin,
                CraneCycleTimeMax=CraneCycleTimeMax,
                AGVList=AGVList,
                SoCThreshold=SoCThreshold,
                counters=counters)
        
        CranesList.append(crane)

    for k in range(FleetSize):
        agv = AGV(AGV_ID=k, 
                SoC=SoCInit,
                AGVSpeed=AGVSpeed,
                TravelDistanceQuayToYard=TravelDistanceQuayToYard,
                TravelDistanceYardToCharger=TravelDistanceYardToCharger,
                TravelDistanceChargerToQuay=TravelDistanceChargerToQuay,
                PickupDuration=PickupDuration,
                DropoffDuration=DropoffDuration,
                EnergyEmpty=EnergyEmpty,
                EnergyLoaded=EnergyLoaded,
                BatteryCapacity=BatteryCapacity,
                MyChargingQueue=MyChargingQueue,
                ChargingStationsList=ChargingStationsList,
                AGVList=AGVList,
                MyJobQueueGlobal=MyJobQueueGlobal,
                SoCThreshold=SoCThreshold,
                counters=counters)
        
        AGVList.append(agv)
        

    VesselGenerator(VesselInterArrivalMean=VesselInterArrivalMean,
                    ContainersPerVessel=ContainersPerVessel,
                    MyVesselQueue=MyVesselQueue,
                    counters=counters)



    # Wait WarmUpPeriod 
    env.run(till= WarmUpPeriod)
    
    # ResetKPICounters 
    for key in counters:
        counters[key] = 0

    # Wait ObservationPeriod -- not implemented yet
    env.run(till= ObservationPeriod)

    # RecordResults -- not implemented yet
    
    #Print statistics and KPIs
    MyJobQueueGlobal.print_statistics()
    MyVesselQueue.print_statistics()
    MyChargingQueue.print_statistics()
    
    
    print(counters)
    print("Total CO2 emissions: ", counters["TotalCO2"]) 
    print("Completed containers: ", counters["CompletedContainers"])
    print("Completed unloading of vessels: ", counters["CompletedVessels"])
    print("CarbonIntensity: ", carbon_intensity['carbon_intensity'])
    print("ArrivedVessels", counters['ArrivedVessels'])
    
    return counters
    
run_simulation() #Run the simulation with default parameters   
 
for i in range(3):
    # Use for loop to adjust parameters such as seed or 
    # input parameters for sensitivity analysis and design of experiments.
    run_simulation(seed=i)
    
for i in range(3):
    # Use for loop to adjust parameters such as seed or 
    # input parameters for sensitivity analysis and design of experiments.
    TEST_INPUT = INPUT_PARAMETERS.copy()
    TEST_INPUT["FleetSize"] = i
    run_simulation(seed=i, input_parameters=TEST_INPUT)

