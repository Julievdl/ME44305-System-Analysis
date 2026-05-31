import salabim as sim
from math import floor
import random
import numpy as np
import pandas as pd

#Import the main classes from the simulation_classes file
#To keep this file more organized
from simulation_classes import AGV, Crane, ChargingStation, VesselGenerator

#Standard/example dict of inputs. Can be modified for sensitivity analysis and experimentation with different scenarios.
INPUT_PARAMETERS = dict(
    TravelTimeToQuayside  =  166/2,   # fixed travel time, empty AGV (seconds)
    TravelTimeToYard      = 166,    # fixed travel time, loaded AGV (seconds)
    TravelTimeToCharger   =  166/2,   # fixed travel time, AGV to charger (seconds)

    PickupDuration        = 0.5*60,   # time to pick up one container (seconds)
    DropoffDuration       = 0.5*60,    # time to drop off one container (seconds)
    CraneCycleTime        =  1.5*60,   # time to unload one container (seconds)

    EnergyLoaded          = 2.5,    # kWh consumed per loaded trip
    EnergyEmpty           = 1.4,   # kWh consumed per empty trip
    BatteryCapacity       =  200,   # usable battery capacity (kWh)

    ChargeRate            =  50,   # charge rate (kW)

    SoCThreshold          =  0.7,   # dispatch threshold for charging request
    SubstationCapacity    =  100,   # grid ceiling (kW) - sensitivity parameter

    CurrentGridLoad       = 0,   # tracked globally, updated at charge events
    TotalCO2              = 0,   # accumulator for primary KPI

    NrChargingStations    = 2,   # number of charging stations
    NrCranes              = 2,   # number of quay cranes
    
    FleetSize             = 5,   # number of AGVs in fleet
    WarmUpPeriod          = 24 * 3600,  # seconds
    ObservationPeriod     = 28 * 24 *3600,  # seconds
    
    ContainersPerVessel   = 294,  # fixed container count per vessel arrival
    
    CheckInterval         = 50, # time between grid ceiling checks when AGV is waiting to charge (seconds)

    VesselInterArrivalMean = 100,  # mean inter-arrival time for vessels (seconds)

    SoCInit = 1.0,   # initial state of charge for all AGVs
    StateInit = "IDLE"   # initial state for all AGVs
       
)

#Load carbon intensity data
CARBON_INTENSITY = pd.read_csv("carbon_intensity_seasonal.csv", parse_dates=['hour'])
  
#Main simulation run function. Use in a loop for sensitivity and design of experiments.
def run_simulation(input_parameters=INPUT_PARAMETERS, 
                   carbon_intensity=CARBON_INTENSITY,
                   RunTime=7*24): 

    """
    Main simulation function. Initializes environment, creates components, and runs the simulation.
    Inputs:
        input_parameters: dict of all model parameters (travel times, energy use, fleet size, etc.)
        carbon_intensity: DataFrame with hourly carbon intensity values for the year
        RunTime: simulation run time in hours (default 7 days)
    """
    
    #Initialize parameters from input dictionary
    TravelTimeToQuayside  =  input_parameters["TravelTimeToQuayside"]
    TravelTimeToYard      =  input_parameters["TravelTimeToYard"]
    TravelTimeToCharger   =  input_parameters["TravelTimeToCharger"]
    
    PickupDuration        =  input_parameters["PickupDuration"]
    DropoffDuration       =  input_parameters["DropoffDuration"]
    CraneCycleTime        =  input_parameters["CraneCycleTime"]
    
    EnergyLoaded          =  input_parameters["EnergyLoaded"]
    EnergyEmpty           =  input_parameters["EnergyEmpty"]
    BatteryCapacity       =  input_parameters["BatteryCapacity"]
    ChargeRate            =  input_parameters["ChargeRate"]
    SoCThreshold          =  input_parameters["SoCThreshold"]
    
    SubstationCapacity    =  input_parameters["SubstationCapacity"]
    CurrentGridLoad       =  input_parameters["CurrentGridLoad"]   
    TotalCO2              =  input_parameters["TotalCO2"]   
    
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
    
    #Create counter for KPI and state tracking (list type for mutability)
    counters = {
        "TotalCO2": 0,
        "CompletedContainers": 0,
        "CompletedVessels": 0,
        "CurrentGridLoad": 0
    }

    #Initialize environment
    env = sim.Environment(trace=False)

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
                CraneCycleTime=CraneCycleTime,
                AGVList=AGVList,
                SoCThreshold=SoCThreshold,
                counters=counters)
        
        CranesList.append(crane)

    for k in range(FleetSize):
        agv = AGV(AGV_ID=k, 
                SoC=SoCInit,
                TravelTimeToQuayside=TravelTimeToQuayside,
                TravelTimeToYard=TravelTimeToYard,
                TravelTimeToCharger=TravelTimeToCharger,
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
                    MyVesselQueue=MyVesselQueue)



    # Wait WarmUpPeriod -- not implemented yet
    # ResetKPICounters -- not implemented yet

    # Wait ObservationPeriod -- not implemented yet
    # RecordResults -- not implemented yet

    #Run simulation until specified time limit
    
    env.run(till= RunTime * 3600)

    MyJobQueueGlobal.print_statistics()
    MyVesselQueue.print_statistics()
    MyChargingQueue.print_statistics()
    
    print("Total CO2 emissions: ", counters["TotalCO2"]) 
    print("Completed containers: ", counters["CompletedContainers"])
    print("Completed vessels: ", counters["CompletedVessels"])
    print("CarbonIntensity: ", carbon_intensity['carbon_intensity'])

run_simulation()

