import salabim as sim
from math import floor
import random
import numpy as np

# Global parameters
TravelTimeToQuayside  =  166/2   # fixed travel time, empty AGV (seconds)
TravelTimeToYard      = 166    # fixed travel time, loaded AGV (seconds)
TravelTimeToCharger   =  166/2   # fixed travel time, AGV to charger (seconds)

PickupDuration        = 0.5*60   # time to pick up one container (seconds)
DropoffDuration       = 0.5*60    # time to drop off one container (seconds)
CraneCycleTime        =  1.5*60   # time to unload one container (seconds)

EnergyLoaded          = 2.5    # kWh consumed per loaded trip
EnergyEmpty           = 1.4   # kWh consumed per empty trip
BatteryCapacity       =  200   # usable battery capacity (kWh)

ChargeRate            =  50   # charge rate (kW)

SoCThreshold          =  0.7   # dispatch threshold for charging request
SubstationCapacity    =  100   # grid ceiling (kW) - sensitivity parameter

CarbonIntensity       =  np.ones(300) #This is a test  # time-indexed array, gCO2/kWh (ENTSO-E NL)
CurrentGridLoad       = 0   # tracked globally, updated at charge events
TotalCO2              = 0   # accumulator for primary KPI

#Added parameters
NrChargingStations    = 2   # number of charging stations
NrCranes              = 2   # number of quay cranes
FleetSize             = 10   # number of AGVs in fleet
WarmUpPeriod          = 24 * 3600  # seconds
ObservationPeriod     = 28 * 24 *3600  # seconds
ContainersPerVessel   = 294  # fixed container count per vessel arrival
CompletedContainers   = 0   # counter for throughput KPI
CompletedVessels      = 0   # counter for vessel throughput
CheckInterval         = 50 # time between grid ceiling checks when AGV is waiting to charge (seconds)

#Distribution values
VesselInterArrivalMean = 100  # mean inter-arrival time for vessels (seconds)

#Init details components & environment
SoCInit = 1.0   # initial state of charge for all AGVs
StateInit = "IDLE"   # initial state for all AGVs

env = sim.Environment(trace=False)

# TVesselGenerator -- Permanent. Generates vessel arrivals.
class VesselGenerator(sim.Component):
    InterArrivalTime: sim.Exponential

    def __init__(self):
        super().__init__()
        self.InterArrivalTime = sim.Exponential(VesselInterArrivalMean)
        
    def process(self):
        while True:
            self.hold(self.InterArrivalTime.sample())
            newVessel = Vessel()
            newVessel.ArrivalTime = env.now()
            newVessel.ContainerCount = ContainersPerVessel
            newVessel.enter(MyVesselQueue)


# TVessel -- Temporary. Holds container count for one vessel arrival.
class Vessel(sim.Component):
    ContainerCount: int
    ArrivalTime:    float


# TCrane -- Permanent. Reactivated by TVesselGenerator.
#          Unloads containers one by one.
class Crane(sim.Component):
    CurrentVessel: Vessel
    
    def process(self):
        while True:
            while len(MyVesselQueue) ==0:
                self.standby()
            
            self.CurrentVessel = MyVesselQueue.pop()
                
            for container in range(self.CurrentVessel.ContainerCount):
                self.hold(CraneCycleTime)
                newContainer = Container()
                newContainer.ArrivalTime = self.env.now()
                newContainer.enter(MyJobQueueGlobal)
                AssignAGV()
            
            global CompletedVessels
            CompletedVessels += 1 #Small added vessels counter for oversight

# TContainer -- Temporary. Flow entity.
class Container(sim.Component):
    ArrivalTime:  float
    DepartTime:   float
    AssignedAGV:  int #Chose to make it the AGV ID, but if extra insight is needed then should be AGV component reference instead

# TAGV -- Permanent. Cycles between transport jobs and charging.
class AGV(sim.Component):
    AGV_ID:           int
    SoC:              float
    State:            sim.State       #{"IDLE", "ACTIVE", "CHARGING","TO_CHARGER"}
    CurrentContainer: Container
 
    def setup(self, AGV_ID=None, SoC=None):
        self.AGV_ID = AGV_ID
        self.SoC = SoC
        self.State = sim.State(f"AGV_{AGV_ID}_state", "IDLE")
        self.State.set("IDLE")
        
    def process(self):
        while True:
            self.passivate()
            
            self.State.set("ACTIVE")
            
            self.hold(TravelTimeToQuayside)
            self.SoC = self.SoC - EnergyEmpty / BatteryCapacity
            
            self.hold(PickupDuration)
            
            self.CurrentContainer.AssignedAGV = self.AGV_ID 
            
            self.hold(TravelTimeToYard)
            self.SoC = self.SoC - EnergyLoaded / BatteryCapacity
            
            self.hold(DropoffDuration)
            self.CurrentContainer.DepartTime = self.env.now()
            
            RecordDelivery()
            
            if self.SoC <= SoCThreshold:
                self.State.set("TO_CHARGER")
                self.hold(TravelTimeToCharger)
                self.enter(MyChargingQueue)
                
                #Explicit activation of first available charging station bc standby apparently doesnt work in salabim??????
                for cs in ChargingStationsList:
                    if cs.ispassive(): 
                        cs.activate()
                        break
                
                self.passivate()
                
            else:
                self.State.set("IDLE")
                AssignAGV()

# TChargingStation -- Permanent. Services AGVs from charging queue.
#                    Checks grid ceiling before each charging event.
class ChargingStation(sim.Component):
    ChargeRate:      float
    
    def __init__(self):
        super().__init__()
        self.ChargeRate = ChargeRate
    
    def process(self):
        global CurrentGridLoad, TotalCO2
        while True:
            
            #Unfortunately the standby doesnt seem to work, so activate component is added in AGV charging section
            while len(MyChargingQueue) == 0:
                self.standby()
                
            if CurrentGridLoad + ChargeRate <= SubstationCapacity:
                myAGV = MyChargingQueue.pop()
                
                myAGV.State.set("CHARGING")
                
                idx = floor(env.now() / 3600) % len(CarbonIntensity) #Loops around if sim runs longer than CarbonIntensity data length
                gamma = CarbonIntensity[idx] 
                
                EnergyNeeded = (1.0 - myAGV.SoC) * BatteryCapacity
                CurrentGridLoad += ChargeRate #Unless we use external grid load data, current grid will never be exceeded unless we have too many chargers
                
                self.hold((EnergyNeeded / ChargeRate) * 3600)

                TotalCO2 += EnergyNeeded * gamma
                
                myAGV.SoC = 1.0

                CurrentGridLoad -= ChargeRate

                myAGV.activate()
                myAGV.State.set("IDLE")
                
                AssignAGV()
            else:
                self.hold(CheckInterval)


# Instantaneous methods (no simulated time consumed)

def AssignAGV():
    
    AGVAvailable = []
    
    for AGV in AGVList:
        if AGV.State.get() == "IDLE" and AGV.SoC > SoCThreshold:
            AGVAvailable.append(AGV)
    
    AGVAvailable.sort(key=lambda x: x.SoC)
        
    if len(MyJobQueueGlobal) > 0 and len(AGVAvailable) > 0:
        myContainer = MyJobQueueGlobal.pop()
        myAGV = AGVAvailable.pop()

        myAGV.CurrentContainer = myContainer
        myAGV.activate()


def RecordDelivery():
    global CompletedContainers
    CompletedContainers += 1
    
    # update throughput statistics -- not implemented yet


# Initialization
    #Load CarbonIntensity from ENTSO-E Netherlands hourly data file -- not implemented yet


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
    cs = ChargingStation()
    ChargingStationsList.append(cs)

for j in range(NrCranes):
    crane = Crane()
    CranesList.append(crane)

for k in range(FleetSize):
    agv = AGV(AGV_ID=k, SoC=SoCInit)
    AGVList.append(agv)

VesselGenerator()



# Wait WarmUpPeriod -- not implemented yet
# ResetKPICounters -- not implemented yet

# Wait ObservationPeriod -- not implemented yet
# RecordResults -- not implemented yet

RunTime = 7 #days
env.run(till= RunTime * 24 * 3600)

MyJobQueueGlobal.print_statistics()
MyVesselQueue.print_statistics()
MyChargingQueue.print_statistics()
print("Total CO2 emissions: ", TotalCO2) 
print("Completed containers: ", CompletedContainers)
print("Completed vessels: ", CompletedVessels)
print("CarbonIntensity: ", CarbonIntensity)
