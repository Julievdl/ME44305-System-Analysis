import salabim as sim
from math import floor
import random
import numpy as np
import pandas as pd

# TVesselGenerator -- Permanent. Generates vessel arrivals.
class VesselGenerator(sim.Component):
    InterArrivalTime: sim.Exponential

    #Setup of the class, parameters are passed from the main function when component is created.
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
    
    #Body of the process, behaviour is defined in here.    
    def process(self):
        
        #while loop (infinite loop) to continuously generate vessels.
        while True:
            
            #Wait for next vessel arrival.
            self.hold(self.InterArrivalTime.sample())
            
            #Create new vessel and assign arrival time and container count
            newVessel = Vessel()
            newVessel.ArrivalTime = self.env.now()
            newVessel.ContainerCount = self.ContainersPerVessel
            
            #Add vessel to global vessel queue
            newVessel.enter(self.MyVesselQueue)
            
            #Add vessel to counter
            self.counters['ArrivedVessels'] += 1


# TVessel -- Temporary. Holds container count for one vessel arrival.
class Vessel(sim.Component):
    ContainerCount: int
    ArrivalTime:    float


# TCrane -- Permanent. Reactivated by TVesselGenerator.
#          Unloads containers one by one.
class Crane(sim.Component):
    CurrentVessel: Vessel
    
    #Setup of the class, parameters are passed from the main function when component is created.
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
    
    #Body of the process, behaviour is defined in here.    
    def process(self):
        #while loop (infinite loop) to continuously check for vessels and unload them.
        while True:
            #standby when vessel queue is empty
            while len(self.MyVesselQueue) ==0:
                self.standby()
            
            #When vessel arrives, remove it from queue
            self.CurrentVessel = self.MyVesselQueue.pop()
            
            #Unload containers from vessel one by one, add to global job queue and assign AGV if available.  
            for container in range(self.CurrentVessel.ContainerCount):
                self.hold(self.CraneCycleTime.sample())
                
                newContainer = Container()
                newContainer.ArrivalTime = self.env.now()
                newContainer.enter(self.MyJobQueueGlobal)
                
                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)
            
            #Update vessel counter when vessel is fully unloaded
            self.counters["CompletedVessels"] += 1 

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

    #Setup of the class, parameters are passed from the main function when component is created.
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
    
    #Body of the process, behaviour is defined in here.    
    def process(self):
        #while loop (infinite loop) to continuously check for jobs, perform transport and charge when needed.
        while True:
            #start in idle state, wait for job assignment
            self.passivate()
            
            #change state to active when job is assigned
            self.State.set("ACTIVE")
            
            #Hold for travel from charger/depot to quay, update SoC and hold for pickup duration
            self.hold(self.TravelTimeChargerToQuay)
            self.SoC = self.SoC - self.EnergyEmpty / self.BatteryCapacity
            self.hold(self.PickupDuration)
            
            #Set AGV ID in container for statistics and tracking
            self.CurrentContainer.AssignedAGV = self.AGV_ID 
            
            #Hold for travel from quay to yard, update SoC and hold for dropoff duration
            self.hold(self.TravelTimeQuayToYard)
            self.SoC = self.SoC - self.EnergyLoaded / self.BatteryCapacity 
            self.hold(self.DropoffDuration)
            
            #Set container departure time for statistics and record delivery in counter
            self.CurrentContainer.DepartTime = self.env.now()
            RecordDelivery(counters=self.counters)
            
            #Travel to charger/depot location
            self.hold(self.TravelTimeYardToCharger)
            
            #check if SoC is below threshold, if yes go to charger, if no wait for next job assignment
            if self.SoC <= self.SoCThreshold:
                #Change state and enter charging queue
                self.State.set("TO_CHARGER")
                self.enter(self.MyChargingQueue)
                
                #Explicit activation of first available charging station (standby didnt work for some reason :/ )
                for cs in self.ChargingStationsList:
                    if cs.ispassive(): 
                        cs.activate()
                        break
                
                #passivate and wait to be activated by charging station after charging is done
                self.passivate()
                
            else:
                #Change state to idle and check for new job assignment
                self.State.set("IDLE")
                
                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)

# TChargingStation -- Permanent. Services AGVs from charging queue.
#                    Checks grid ceiling before each charging event.
class ChargingStation(sim.Component):
    ChargeRate:      float
    
    #Setup of the class, parameters are passed from the main function when component is created.
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
            
            #standby when no AGVs are waiting to charge (standby doesnt work so is activated by AGV when it enters charging queue)
            while len(self.MyChargingQueue) == 0:
                self.standby()
            
            #Check if grid capacity allows for charging, if not wait and check again after interval    
            if self.counters["CurrentGridLoad"] + self.ChargeRate <= self.SubstationCapacity:
                #Remove AGV from charging queue and change its state to charging
                myAGV = self.MyChargingQueue.pop()
                myAGV.State.set("CHARGING")
                
                #Find the carbon intensity for the current time step by using current simulation time (which is in seconds)
                idx = floor(self.env.now() / 3600) % len(self.CarbonIntensity) #Loops around if sim runs longer than CarbonIntensity data length
                gamma = self.CarbonIntensity['carbon_intensity'][idx] 
                
                #Calculate energy needed to fully charge
                EnergyNeeded = (1.0 - myAGV.SoC) * self.BatteryCapacity
                
                """
                Unless we use external grid load data, 
                current grid will never be exceeded unless we have too many chargers 
                (but that would make them obsolete)
                """
                #Update grid load counter and hold for charging duration based on energy needed and charge rate
                self.counters["CurrentGridLoad"] += self.ChargeRate 
                self.hold((EnergyNeeded / self.ChargeRate) * 3600)

                # Update total CO2 emissions based on energy needed and carbon intensity at the time of charging 
                # and update grid load counter
                self.counters["TotalCO2"] += EnergyNeeded * gamma
                self.counters["CurrentGridLoad"] -= self.ChargeRate
                
                #After charging is done, set AGV SoC to 100% and activate it to check for new job assignment
                myAGV.SoC = 1.0
                myAGV.activate() #(AGV is activated here to get out of the if else statement in its process)
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
    
    #Initialize list of available AGVs (idle and above SoC threshold)
    AGVAvailable = []

    #Check AGV list for idle AGVs above SoC threshold and add them to available list
    for AGV in AGVList:
        if AGV.State.get() == "IDLE" and AGV.SoC > SoCThreshold:
            AGVAvailable.append(AGV)
    
    #Sort available AGVs by SoC (highest first) to prioritize those with more charge for new jobs
    AGVAvailable.sort(key=lambda x: x.SoC)

    #If there are available AGVs and waiting jobs, assign AGV to job by popping from both lists and activating AGV process
    if len(MyJobQueueGlobal) > 0 and len(AGVAvailable) > 0:
        myContainer = MyJobQueueGlobal.pop()
        myAGV = AGVAvailable.pop()
        
        myAGV.CurrentContainer = myContainer
        myAGV.activate()


def RecordDelivery(counters=None):
    counters["CompletedContainers"] += 1
    # update throughput statistics -- not quite implemented yet (somewhat contained in the counters dict)
  