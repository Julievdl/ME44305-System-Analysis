import salabim as sim
from math import floor
import random
import numpy as np
import pandas as pd
import datetime as dt

# TVesselGenerator -- Permanent. Generates vessel arrivals.
class VesselGenerator(sim.Component):
    InterArrivalTime: sim.Exponential
    Vessel_ID: int

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
            
            #print("Generating next vessel arrival...\n")
            sample = self.InterArrivalTime.sample()
            #print("Generated sample:", sample)
            
            #timeb4= self.env.now()
            #Wait for next vessel arrival.
            self.hold(sample)
            #timeafter = self.env.now()
            #duration = timeafter - timeb4

            #print("Waited for:", duration, "from", timeb4, "to", timeafter, "\n")
            
            self.counters["VesselArrivalTime"].append(self.env.now())
            
            #Create new vessel and assign arrival time and container count
            newVessel = Vessel(ContainerCount=self.ContainersPerVessel, 
                               ArrivalTime=self.env.now(), 
                               VesselID=self.counters["ArrivedVessels"])
            #print("newVessel\n","Vessel ID:", newVessel.Vessel_ID, "\nArrival Time:", newVessel.ArrivalTime, "\nContainer Count:", newVessel.ContainerCount)
            #Add vessel to global vessel queue
            newVessel.enter(self.MyVesselQueue)
            #print("Vessel Queue:", self.MyVesselQueue[-1])
            
            #print("Counters before:", self.counters['ArrivedVessels'])
            #Add vessel to counter
            self.counters['ArrivedVessels'] += 1
            #print("Counters after:", self.counters['ArrivedVessels'], "\n\n")


# TVessel -- Temporary. Holds container count for one vessel arrival.
class Vessel(sim.Component):
    ContainerCount: int
    ArrivalTime:    float
    VesselID:       int
    
    #Setup of the class, parameters are passed from the main function when component is created.
    def setup(self, ContainerCount=None, ArrivalTime=None, VesselID=None):
        self.ContainerCount = ContainerCount
        self.ArrivalTime = ArrivalTime
        self.Vessel_ID = VesselID


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
            while len(self.MyVesselQueue) == 0:
                self.standby()
            
            # print("\n\nCrane process activated. Checking vessel queue...\n")
            # print("\n\nCRANE COMPONENET\nFirst vessel in queue:", self.MyVesselQueue[0] if len(self.MyVesselQueue) > 0 else "No vessels in queue")
            # print(self.MyVesselQueue[i] for i in range(len(self.MyVesselQueue)))
            self.CurrentVessel = self.MyVesselQueue.pop()
            
            # print("Popped vessel from queue:",
            #       "Vessel ID:", self.CurrentVessel.Vessel_ID,
            #       "| Container Count:", self.CurrentVessel.ContainerCount,
            #       "| MyVesselQueue length after pop:", len(self.MyVesselQueue))
            # print("First vessel in queue after pop:", self.MyVesselQueue[0] if len(self.MyVesselQueue) > 0 else "No vessels in queue")
            
            for container in range(self.CurrentVessel.ContainerCount):

                sample = self.CraneCycleTime.sample()
                #time_before = self.env.now()
                self.hold(sample)
                #time_after = self.env.now()
                # print("CraneCycleTime hold:",
                #       "Generated sample:", sample,
                #       "| Waited for:", time_after - time_before,
                #       "| from", time_before, "to", time_after)

                newContainer = Container(ContainerID=self.counters["UnloadedContainers"], 
                                         VesselID=self.CurrentVessel.Vessel_ID, 
                                         ArrivalTime=self.env.now())
                # print("Container created:",
                #       "Container ID:", newContainer.ContainerID,
                #       "| Vessel ID:", newContainer.VesselID,
                #       "| Arrival Time:", newContainer.ArrivalTime)

                newContainer.enter(self.MyJobQueueGlobal)
                # print("Container added to MyJobQueueGlobal:",
                #       "MyJobQueueGlobal[-1]:", self.MyJobQueueGlobal[-1],
                #       "| Queue length:", len(self.MyJobQueueGlobal))

                #print("UnloadedContainers counter before:", self.counters["UnloadedContainers"])
                self.counters["UnloadedContainers"] += 1
                #print("UnloadedContainers counter after:", self.counters["UnloadedContainers"])

                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)
            
            #print("CompletedVessels counter before:", self.counters["CompletedVessels"])
            self.counters["VesselDepartureTime"].append(self.env.now())
            self.counters["CompletedVessels"] += 1
            #print("CompletedVessels counter after:", self.counters["CompletedVessels"], "\n\n")
            
# TContainer -- Temporary. Flow entity.
class Container(sim.Component):
    ContainerID:  int
    VesselID:     int
    ArrivalTime:  float #Time when container is unloaded from vessel at quay
    PickupTime:   float #Time when container is picked up by AGV at quay
    DepartTime:   float #Time when container is dropped off at yard
    AssignedAGV:  int #Chose to make it the AGV ID, but if extra insight is needed then should be AGV component reference instead
    

    #Setup of the class, parameters are passed from the main function when component is created.
    def setup(self, ContainerID=None, VesselID=None, ArrivalTime=None):
        self.ContainerID  = ContainerID
        self.VesselID     = VesselID
        self.ArrivalTime  = ArrivalTime
        self.PickupTime   = None
        self.DepartTime   = None
        self.AssignedAGV  = None
        


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
              counters=None,
              delivery_records=None,
              charging_records=None):
        
        self.AGV_ID                =  AGV_ID
        self.SoC                   =  SoC
        self.State                 =  sim.State(f"AGV_{AGV_ID}_state", "IDLE")
        self.State.set("IDLE")
        self.AGVSpeed              =  AGVSpeed
        self.CurrentContainer      =  None
        
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
        self.delivery_records      =  delivery_records
        self.charging_records      =  charging_records
        
    #Body of the process, behaviour is defined in here.    
    def process(self):
        #while loop (infinite loop) to continuously check for jobs, perform transport and charge when needed.
        while True:
            #start in idle state, wait for job assignment
            self.passivate()
            
            # print("AGV STATE before", self.State.get())
            
            #change state to active when job is assigned
            self.State.set("ACTIVE")
            
            # print("AGV STATE after", self.State.get())
            
            
            
            # timeb4= self.env.now()
            
            #Hold for travel from charger/depot to quay, update SoC and hold for pickup duration
            self.hold(self.TravelTimeChargerToQuay)
            
            # timeafter = self.env.now()
            # duration = timeafter - timeb4
            # print("Waited for TravelTimeChargerToQuay:", duration, "from", timeb4, "to", timeafter, "\n")
            
            # print(f"AGV {self.AGV_ID} SoC before travel to quay: {self.SoC}")
            # print(f"AGV {self.AGV_ID} EnergyEmpty: {self.EnergyEmpty:.2f}, BatteryCapacity: {self.BatteryCapacity:.2f}")
            
            self.SoC = self.SoC - self.EnergyEmpty / self.BatteryCapacity
            
            # print(f"AGV {self.AGV_ID} SoC after travel to quay: {self.SoC}")
            
            # timeb4= self.env.now()
            
            self.hold(self.PickupDuration)
            
            # timeafter = self.env.now()
            # duration = timeafter - timeb4
            # print("Waited for PickupDuration:", duration, "from", timeb4, "to", timeafter, "\n")
            
            #Set AGV ID and pickup time in container for statistics and tracking
            # print("Container details before:", 
            #       "Container ID:", self.CurrentContainer.ContainerID, 
            #       "| Vessel ID:", self.CurrentContainer.VesselID, 
            #       "| Arrival Time:", self.CurrentContainer.ArrivalTime, 
            #       "| Pickup Time:", self.CurrentContainer.PickupTime, 
            #       "| Depart Time:", self.CurrentContainer.DepartTime, 
            #       "| Assigned AGV:", self.CurrentContainer.AssignedAGV)
            
            self.CurrentContainer.AssignedAGV = self.AGV_ID 
            self.CurrentContainer.PickupTime = self.env.now()
            
            # print("Container details after:", 
            #       "Container ID:", self.CurrentContainer.ContainerID, 
            #       "| Vessel ID:", self.CurrentContainer.VesselID, 
            #       "| Arrival Time:", self.CurrentContainer.ArrivalTime, 
            #       "| Pickup Time:", self.CurrentContainer.PickupTime, 
            #       "| Depart Time:", self.CurrentContainer.DepartTime, 
            #       "| Assigned AGV:", self.CurrentContainer.AssignedAGV)
            
            # timeb4= self.env.now()
            
            #Hold for travel from quay to yard, update SoC and hold for dropoff duration
            self.hold(self.TravelTimeQuayToYard)
            
            # timeafter = self.env.now()
            # duration = timeafter - timeb4
            # print("Waited for TravelTimeQuayToYard:", duration, "from", timeb4, "to", timeafter, "\n")
            # print(f"AGV {self.AGV_ID} SoC before travel to quay: {self.SoC}")
            # print(f"AGV {self.AGV_ID} EnergyLoaded: {self.EnergyLoaded:.2f}, BatteryCapacity: {self.BatteryCapacity:.2f}")
            
            self.SoC = self.SoC - self.EnergyLoaded / self.BatteryCapacity 
            
            # print(f"AGV {self.AGV_ID} SoC after travel to quay: {self.SoC}")
            # timeb4= self.env.now()
            
            self.hold(self.DropoffDuration)
            
            # timeafter = self.env.now()
            # duration = timeafter - timeb4
            # print("Waited for DropoffDuration:", duration, "from", timeb4, "to", timeafter, "\n")
            
            #Set container departure time for statistics and record delivery in counter
            self.CurrentContainer.DepartTime = self.env.now()
            
            # print("Container details after dropoff:", 
            #       "Container ID:", self.CurrentContainer.ContainerID, 
            #       "| Vessel ID:", self.CurrentContainer.VesselID, 
            #       "| Arrival Time:", self.CurrentContainer.ArrivalTime, 
            #       "| Pickup Time:", self.CurrentContainer.PickupTime, 
            #       "| Depart Time:", self.CurrentContainer.DepartTime, 
            #       "| Assigned AGV:", self.CurrentContainer.AssignedAGV)
            
            RecordDelivery(counters=self.counters, container=self.CurrentContainer, delivery_records=self.delivery_records)
            
            # timeb4= self.env.now()
            
            #Travel to charger/depot location
            self.hold(self.TravelTimeYardToCharger)
            
            # timeafter = self.env.now()
            # duration = timeafter - timeb4
            # print("Waited for TravelTimeYardToCharger:", duration, "from", timeb4, "to", timeafter, "\n")
            
            #print("CURRENT SOC IS: ",self.SoC, "FOR AGV ID:", self.AGV_ID)
            
            #check if SoC is below threshold, if yes go to charger, if no wait for next job assignment
            if self.SoC <= self.SoCThreshold:
                
                #print("IF STATEMENT ACTIVATED AT SOC: ", self.SoC, "FOR AGV ID:", self.AGV_ID,"\n")
                
                #Change state and enter charging queue
                self.State.set("TO_CHARGER")
                
                # print("Charging queue ", self.MyChargingQueue.length())
                # print("Last in charging queue ", self.MyChargingQueue[-1] if self.MyChargingQueue.length() > 0 else "No AGVs in queue")
                # print("AGV ID: ", self.AGV_ID)
                
                self.enter(self.MyChargingQueue)
                
                # print("Last in charging queue now: ", self.MyChargingQueue[-1] if self.MyChargingQueue.length() > 0 else "No AGVs in queue")
                # print("charging records input: \n", "CurrentTime:", self.env.now(),
                #                               "| AGVID:", self.AGV_ID,
                #                                 "| AGVSoC:", self.SoC,
                #                                 "| Action: EnterQueue",
                #                                 "| StartTime:", self.env.now(),
                #                                 "| EnergyAdded: None",
                #                                 "| CurrentGridLoad:", self.counters["CurrentGridLoad"],
                #                                 "| CurrentCO2:", self.counters["TotalCO2"])
                
                self.charging_records.append({"CurrentTime": self.env.now(), 
                                              "AGVID": self.AGV_ID, 
                                              "AGVSoC": self.SoC,
                                              "Action": "EnterQueue",
                                              "StartTime": self.env.now(), 
                                              "EnergyAdded": None, 
                                              "CurrentGridLoad": self.counters["CurrentGridLoad"], 
                                              "CurrentCO2": self.counters["TotalCO2"]})
                
                # print("Last records entry: \n", self.charging_records[-1])
                
                #Explicit activation of first available charging station (standby didnt work for some reason :/ )
                for cs in self.ChargingStationsList:
                    if cs.ispassive(): 
                        cs.activate()
                        break
                
                #passivate and wait to be activated by charging station after charging is done
                self.passivate()
                
            else:
                
                #print("ELSE STATEMENT ACTIVATED AT SOC: ", self.SoC, "FOR AGV ID:", self.AGV_ID, "\n")
                
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
              counters=None,
              charging_records=None):
        
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
        self.charging_records     =  charging_records
        
    def process(self):
        while True:
            
            #standby when no AGVs are waiting to charge (standby doesnt work so is activated by AGV when it enters charging queue)
            while len(self.MyChargingQueue) == 0:
                self.standby()
            
            # print("Current grid load before charging:", self.counters["CurrentGridLoad"], "kW, charge rate:", self.ChargeRate, "kW, substation capacity:", self.SubstationCapacity, "kW")
            
            #Check if grid capacity allows for charging, if not wait and check again after interval    
            if self.counters["CurrentGridLoad"] + self.ChargeRate <= self.SubstationCapacity:
                
                # print("ENTERING IF STATEMENT:Grid capacity sufficient for charging.")
                # print("\n\nCHARGINGSTATION COMPONENR\nFirst in charging queue before pop:", self.MyChargingQueue[0] if len(self.MyChargingQueue) > 0 else "No AGVs in queue")
                # print(self.MyChargingQueue[i] for i in range(len(self.MyChargingQueue)))
                #Remove AGV from charging queue and change its state to charging
                myAGV = self.MyChargingQueue.pop()
                
                # print("popped AGV from charging queue, AGV ID:", myAGV, "next in queue:", self.MyChargingQueue[0] if len(self.MyChargingQueue) > 0 else "No AGVs in queue")
                # print("AGV state before charging:", myAGV.State.get())
                
                myAGV.State.set("CHARGING")
                
                # print("AGV state after setting to CHARGING:", myAGV.State.get())
                # print("Current simulation time (s):", self.env.now(), "in hours:", self.env.now() / 3600)
                
                #Find the carbon intensity for the current time step by using current simulation time (which is in seconds)
                idx = floor(self.env.now() / 3600) % len(self.CarbonIntensity) #Loops around if sim runs longer than CarbonIntensity data length
                
                # print("Carbon intensity index:", idx)
                
                gamma = self.CarbonIntensity['carbon_intensity'][idx] 
                
                # print("Carbon intensity at current time:", gamma, "gCO2/kWh")
                
                #Calculate energy needed to fully charge
                EnergyNeeded = (1.0 - myAGV.SoC) * self.BatteryCapacity
                
                """
                Unless we use external grid load data, 
                current grid will never be exceeded unless we have too many chargers 
                (but that would make them obsolete)
                """
                
                # print("GridLoad before: ", self.counters["CurrentGridLoad"])
                
                #Update grid load counter and hold for charging duration based on energy needed and charge rate
                self.counters["CurrentGridLoad"] += self.ChargeRate
                
                # print("Gridload during: ", self.counters["CurrentGridLoad"])

                # print("charging records input: \n", "CurrentTime:", self.env.now(),
                #                               "| AGVID:", myAGV.AGV_ID,
                #                                 "| AGVSoC:", myAGV.SoC,
                #                                 "| Action: StartCharging",
                #                                 "| StartTime:", self.env.now(),
                #                                 "| EnergyAdded: None",
                #                                 "| CurrentGridLoad:", self.counters["CurrentGridLoad"],
                #                                 "| CurrentCO2:", self.counters["TotalCO2"])
                
                self.charging_records.append({"CurrentTime": self.env.now(), 
                                              "AGVID": myAGV.AGV_ID, 
                                              "AGVSoC": myAGV.SoC,
                                              "Action": "StartCharging",
                                              "StartTime": self.env.now(), 
                                              "EnergyAdded": None, 
                                              "CurrentGridLoad": self.counters["CurrentGridLoad"], 
                                              "CurrentCO2": self.counters["TotalCO2"]})
                
                # print("Most recent charging record: ", self.charging_records[-1])
                
                # before = self.env.now()
                # print("Hold duration for charging based on energy needed and charge rate: ", (EnergyNeeded / self.ChargeRate) * 3600, "seconds",
                #       "\n current time: ", before)
                
                self.hold((EnergyNeeded / self.ChargeRate) * 3600)
                
                # after = self.env.now()
                # print("Time after charging hold: ", after, "duration:", after - before)

                # Update total CO2 emissions based on energy needed and carbon intensity at the time of charging 
                # and update grid load counter
                self.counters["TotalCO2"] += EnergyNeeded * gamma
                self.counters["CurrentGridLoad"] -= self.ChargeRate
                
                # print("GridLoad after: ", self.counters["CurrentGridLoad"])
                
                self.charging_records.append({"CurrentTime": self.env.now(), 
                                              "AGVID": myAGV.AGV_ID, 
                                              "AGVSoC": myAGV.SoC,
                                              "Action": "EndCharging",
                                              "StartTime": self.env.now(), 
                                              "EnergyAdded": EnergyNeeded, 
                                              "CurrentGridLoad": self.counters["CurrentGridLoad"], 
                                              "CurrentCO2": self.counters["TotalCO2"]})
                
                #After charging is done, set AGV SoC to 100% and activate it to check for new job assignment
                myAGV.SoC = 1.0
                myAGV.activate() #(AGV is activated here to get out of the if else statement in its process)
                myAGV.State.set("IDLE")
                
                AssignAGV(AGVList=self.AGVList, 
                          SoCThreshold=self.SoCThreshold,
                          MyJobQueueGlobal=self.MyJobQueueGlobal)
            else:
                # print("ENTERING ELSE STATEMENT: Grid capacity insufficient for charging.")
                self.hold(self.CheckInterval)


# Instantaneous methods (no simulated time consumed)
def AssignAGV(SoCThreshold=None, 
              MyJobQueueGlobal=None,
              AGVList=None):
    
    #Initialize list of available AGVs (idle and above SoC threshold)
    AGVAvailable = []

    #Check AGV list for idle AGVs above SoC threshold and add them to available list
    # print("\nChecking for available AGVs to assign to waiting jobs...\n")
    for AGV in AGVList:
        # print("Checking AGV ID:", AGV.AGV_ID, "State:", AGV.State.get(), "SoC:", AGV.SoC)
        if AGV.State.get() == "IDLE" and AGV.SoC > SoCThreshold:
            AGVAvailable.append(AGV)
    # print("Available AGVs:", AGVAvailable, "\n")
    #Sort available AGVs by SoC (highest first) to prioritize those with more charge for new jobs
    AGVAvailable.sort(key=lambda x: x.SoC)
    # print("Sorted available AGVs:", AGVAvailable, "\n")
    
    #If there are available AGVs and waiting jobs, assign AGV to job by popping from both lists and activating AGV process
    if len(MyJobQueueGlobal) > 0 and len(AGVAvailable) > 0:
        # print("\n\nASSIGNAGV\nMyJobQueueGlabal before: ", MyJobQueueGlobal[0] if len(MyJobQueueGlobal) > 0 else "No jobs in queue")
        # print(MyJobQueueGlobal[i] for i in range(len(MyJobQueueGlobal)))
        myContainer = MyJobQueueGlobal.pop()
        # print("Popped container: ", myContainer, " next first in queue: ", MyJobQueueGlobal[0] if len(MyJobQueueGlobal) > 0 else "No jobs in queue")
        
        # print("Top AGV: ", AGVAvailable[-1] if len(AGVAvailable) > 0 else "No AGVs available")
        myAGV = AGVAvailable.pop()
        # print("Popped AGV: ", myAGV)
        
        # print("Current container AGV: ", myAGV.CurrentContainer)
        myAGV.CurrentContainer = myContainer
        # print("New cotnainer: ", myAGV.CurrentContainer)
        
        myAGV.activate()


def RecordDelivery(counters=None, container=None, delivery_records=None):
    # print("\n\nRECORDDELIVERY\n")
    # print("Completedcontainer counter before: ",counters["CompletedContainers"])
    counters["CompletedContainers"] += 1
    # print("Completedcontainer counter after: ",counters["CompletedContainers"])
    
    # print("delivery records input: \n", "CurrentTime : ", container.env.now(),
    #     " | ContainerID: ", container.ContainerID,
    #     " | VesselID: ", container.VesselID,
    #     " | ArrivalTime: ", container.ArrivalTime,
    #     " | PickupTime: ", container.PickupTime,
    #     " | DepartTime: ", container.DepartTime,
    #     " | AGVID: ", container.AssignedAGV,  # AGV ID will be set when the container is assigned to an AGV
    #     " | CurrentCO2: ", counters["TotalCO2"])
                
    delivery_records.append({
        "CurrentTime": container.env.now(),
        "ContainerID": container.ContainerID,
        "VesselID": container.VesselID,
        "ArrivalTime": container.ArrivalTime,
        "PickupTime": container.PickupTime,
        "DepartTime": container.DepartTime,
        "AGVID": container.AssignedAGV,  # AGV ID will be set when the container is assigned to an AGV
        "CurrentCO2": counters["TotalCO2"]})
    
    # print("Recent delivery record", delivery_records[-1])
