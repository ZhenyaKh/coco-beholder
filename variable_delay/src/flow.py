#!/usr/bin/env python

from variable_delay.src.data import get_data_duration, load_data, DataError

#
# Class the instance of which is a flow with data to plot
#
class Flow(object):
    #
    # Constructor
    #
    def __init__(self):
        self.start         = None # flow start
        self.end           = None # flow end
        self.slottedPkts   = None # flow slotted packets
        self.slottedDelays = None # flow slotted delays
        self.slottedBytes  = None # flow slotted bytes


    #
    # Method computes the flow's data first and last arrivals.
    # param [in] directory - input directory containing the log file
    # param [in] flowId    - flow index
    # throws DataError
    #
    def compute_time_bounds(self, directory, flowId):
        self.start, self.end = get_data_duration(directory, flowId)


    #
    # Method computes slotted data for the flow
    # param [in] directory   - input directory containing the log file
    # param [in] flowId      - flow index
    # param [in] slotsNumber - number of slots
    # param [in] slotSec     - float slot size in seconds
    # throws DataError
    #
    def compute_slotted_data(self, directory, flowId, slotsNumber, slotSec):
        arrivals, delays, sizes = load_data(directory, flowId)

        self.compute_slotted_packets(arrivals, slotsNumber, slotSec)
        del arrivals[:]

        self.compute_slotted_delays(delays)
        del delays[:]

        self.compute_slotted_bytes(sizes)
        del sizes[:]


    #
    # Method frees the data of the flow
    #
    def free_data(self):
        del self.slottedPkts  [:]
        del self.slottedDelays[:]
        del self.slottedBytes [:]


    #
    # Methods divides packets of the flow into time slots
    # param [in] arrivals    - timestamps of packets' arrivals
    # param [in] slotsNumber - number of slots
    # param [in] slotSec     - float slot size in seconds
    #
    def compute_slotted_packets(self, arrivals, slotsNumber, slotSec):
        self.slottedPkts = [0] * slotsNumber

        for arrival in arrivals:
            slotId = int(arrival / slotSec)

            self.slottedPkts[slotId] += 1


    #
    # Methods computed sums of delays of packets placed in one slot for the flow
    # param [in] delays - packets' delays
    #
    def compute_slotted_delays(self, delays):
        self.slottedDelays = [0] * len(self.slottedPkts)

        firstPacket = 0

        for slotId, packets in enumerate(self.slottedPkts):
            delaySum = 0.0

            for packet in range(firstPacket, firstPacket + packets):
                delaySum += delays[packet]

            firstPacket += packets

            self.slottedDelays[slotId] = delaySum


    #
    # Methods computed sums of bytes of packets placed in one slot
    # param [in] sizes - packets' sizes in bytes
    #
    def compute_slotted_bytes(self, sizes):
        self.slottedBytes = [0] * len(self.slottedPkts)

        firstPacket = 0

        for slotId, packets in enumerate(self.slottedPkts):
            bytesSum = 0

            for packet in range(firstPacket, firstPacket + packets):
                bytesSum += sizes[packet]

            firstPacket += packets

            self.slottedBytes[slotId] = bytesSum
