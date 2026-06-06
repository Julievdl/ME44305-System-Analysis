import salabim as sim
from math import floor
import random
import numpy as np
import pandas as pd

# TVesselGenerator -- Permanent. Generates vessel arrivals.
class VesselGenerator(sim.Component):
    InterArrivalTime: sim.Exponential

    def setup(
                self, 
                VesselInterArrivalMean=None,
                ContainersPerVessel=None,
                MyVesselQueue=None,
                counters=None):
        
        self.InterArrivalTime       =  sim.Exponential(VesselInterArrivalMean)
        self.ContainersPerVessel    =  ContainersPerVessel
        self.MyVesselQueue          =  MyVesselQueue
        self.counters               =  counters
        
    def process(self):
        while True:
            self.hold(self.InterArrivalTime.sample())
            newVessel = Vessel()
            newVessel.ArrivalTime = self.env.now()
            #print("Vessel arrived at time ", newVessel.ArrivalTime)
            self.counters['ArrivedVessels'] += 1
            newVessel.ContainerCount = self.ContainersPerVessel
            newVessel.enter(self.MyVesselQueue)


# TVessel -- Temporary. Holds container count for one vessel arrival.
class Vessel(sim.Component):
    ContainerCount: int
    ArrivalTime:    float


# TCrane -- Permanent. Reactivated by TVesselGenerator.
#          Unloads containers one by one.
class Crane(sim.Component):
    CurrentVessel: Vessel
    
    def setup(self, 
                MyVesselQueue=None,
                MyJobQueueGlobal=None,
                CraneCycleTimeMin=None,
                CraneCycleTimeMax=None,
                AGVList=None,
                SoCThreshold=None,
                counters=None):
        
        self.MyVesselQueue       =  MyVesselQueue
        self.MyJobQueueGlobal    =  MyJobQueueGlobal
        self.CraneCycleTime      =  sim.Uniform(CraneCycleTimeMin, CraneCycleTimeMax)
        self.AGVList             =  AGVList
        self.SoCThreshold        =  SoCThreshold
        self.counters            =  counters
        
    def process(self):
        while True:
            while len(self.MyVesselQueue) ==0:
                self.standby()
            
            self.CurrentVessel = self.MyVesselQueue.pop()
            #print("Crane starts unloading vessel with ", self.CurrentVessel.ContainerCount, " containers at time ", self.env.now())  
            for container in range(self.CurrentVessel.ContainerCount):
                self.hold(self.CraneCycleTime.sample())
                newContainer = Container()
                newContainer.ArrivalTime = self.env.now()
                newContainer.enter(self.MyJobQueueGlobal)
                
                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)
            
            #print("Crane finished unloading vessel at time ", self.env.now())
            self.counters["CompletedVessels"] += 1 #Small added vessels counter for oversight

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

    def setup(self, 
              AGV_ID=None, 
              SoC=None,
              AGVSpeed=None,
              TravelDistanceQuayToYard=None,
              TravelDistanceYardToCharger=None,
              TravelDistanceChargerToQuay=None,
              PickupDuration=None,
              DropoffDuration=None,
              EnergyEmpty=None,
              EnergyLoaded=None,
              BatteryCapacity=None,
              MyChargingQueue=None,
              ChargingStationsList=None,
              MyJobQueueGlobal=None,
              AGVList=None,
              SoCThreshold=None,
              counters=None):
        
        self.AGV_ID                =  AGV_ID
        self.SoC                   =  SoC
        self.State                 =  sim.State(f"AGV_{AGV_ID}_state", "IDLE")
        self.State.set("IDLE")
        self.AGVSpeed              =  AGVSpeed
        
        self.TravelTimeQuayToYard         =  TravelDistanceQuayToYard / self.AGVSpeed
        self.TravelTimeYardToCharger      =  TravelDistanceYardToCharger / self.AGVSpeed
        self.TravelTimeChargerToQuay      =  TravelDistanceChargerToQuay / self.AGVSpeed

        self.PickupDuration        =  PickupDuration
        self.DropoffDuration       =  DropoffDuration
        self.EnergyEmpty           =  EnergyEmpty
        self.EnergyLoaded          =  EnergyLoaded
        self.BatteryCapacity       =  BatteryCapacity
        self.MyChargingQueue       =  MyChargingQueue
        self.ChargingStationsList  =  ChargingStationsList
        
        self.MyJobQueueGlobal      =  MyJobQueueGlobal
        self.AGVList               =  AGVList
        self.SoCThreshold          =  SoCThreshold
        self.counters              =  counters
        
    def process(self):
        while True:
            self.passivate()
            
            self.State.set("ACTIVE")
            
            self.hold(self.TravelTimeChargerToQuay)
            self.SoC = self.SoC - self.EnergyEmpty / self.BatteryCapacity
            
            self.hold(self.PickupDuration)
            
            self.CurrentContainer.AssignedAGV = self.AGV_ID 
            
            self.hold(self.TravelTimeQuayToYard)
            self.SoC = self.SoC - self.EnergyLoaded / self.BatteryCapacity
            
            self.hold(self.DropoffDuration)
            self.CurrentContainer.DepartTime = self.env.now()
            
            RecordDelivery(counters=self.counters)
            
            #Travel to charger/depot location
            self.hold(self.TravelTimeYardToCharger)
            
            if self.SoC <= self.SoCThreshold:
                self.State.set("TO_CHARGER")
                self.enter(self.MyChargingQueue)
                
                #Explicit activation of first available charging station bc standby apparently doesnt work in salabim??????
                for cs in self.ChargingStationsList:
                    if cs.ispassive(): 
                        cs.activate()
                        break
                
                self.passivate()
                
            else:
                self.State.set("IDLE")
                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)

# TChargingStation -- Permanent. Services AGVs from charging queue.
#                    Checks grid ceiling before each charging event.
class ChargingStation(sim.Component):
    ChargeRate:      float
    
    def setup(self, 
              ChargeRate=None,
              MyChargingQueue=None,
              SubstationCapacity=None,
              BatteryCapacity=None,
              CheckInterval=None,
              AGVList=None,
              MyJobQueueGlobal=None,
              SoCThreshold=None,
              CarbonIntensity=None,
              counters=None):
        
        self.ChargeRate           =  ChargeRate
        self.MyChargingQueue      =  MyChargingQueue
        self.SubstationCapacity   =  SubstationCapacity
        self.BatteryCapacity      =  BatteryCapacity
        self.CheckInterval        =  CheckInterval
        self.AGVList              =  AGVList
        self.MyJobQueueGlobal     =  MyJobQueueGlobal
        self.SoCThreshold         =  SoCThreshold
        self.CarbonIntensity      =  CarbonIntensity
        self.counters             =  counters
        
    def process(self):
        while True:
            
            #Unfortunately the standby doesnt seem to work, so activate component is added in AGV charging section
            while len(self.MyChargingQueue) == 0:
                self.standby()
                
            if self.counters["CurrentGridLoad"] + self.ChargeRate <= self.SubstationCapacity:
                myAGV = self.MyChargingQueue.pop()
                
                myAGV.State.set("CHARGING")
                
                idx = floor(self.env.now() / 3600) % len(self.CarbonIntensity) #Loops around if sim runs longer than CarbonIntensity data length
                gamma = self.CarbonIntensity['carbon_intensity'][idx] 
                #print("gamma: ", gamma)
                EnergyNeeded = (1.0 - myAGV.SoC) * self.BatteryCapacity
                self.counters["CurrentGridLoad"] += self.ChargeRate #Unless we use external grid load data, current grid will never be exceeded unless we have too many chargers
                
                self.hold((EnergyNeeded / self.ChargeRate) * 3600)

                #print(self.counters['TotalCO2'], " ", EnergyNeeded, " ", gamma)
                self.counters["TotalCO2"] += EnergyNeeded * gamma
                
                myAGV.SoC = 1.0

                self.counters["CurrentGridLoad"] -= self.ChargeRate

                myAGV.activate()
                myAGV.State.set("IDLE")
                
                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)
            else:
                self.hold(self.CheckInterval)


# Instantaneous methods (no simulated time consumed)

def AssignAGV(SoCThreshold=None, 
              MyJobQueueGlobal=None,
              AGVList=None):
    
    AGVAvailable = []
    SoCs = []

    for AGV in AGVList:
        if AGV.State.get() == "IDLE" and AGV.SoC > SoCThreshold:
            AGVAvailable.append(AGV)
    
    AGVAvailable.sort(key=lambda x: x.SoC)

    
    
    
    if len(MyJobQueueGlobal) > 0 and len(AGVAvailable) > 0:
        myContainer = MyJobQueueGlobal.pop()
        myAGV = AGVAvailable.pop()
        
        myAGV.CurrentContainer = myContainer
        myAGV.activate()


def RecordDelivery(counters=None):
    counters["CompletedContainers"] += 1
    # update throughput statistics -- not implemented yet
  