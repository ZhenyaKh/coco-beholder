#!/usr/bin/env python

from variable_delay.src.data.data import get_duration, load_data, load_delays, DataError

#
# Class the instance of which is a flow with data to plot
#
class Flow(object):
    #
    # Constructor
    # param [in] id - flow index
    #
    def __init__(self, id):
        self.id            = id   # flow index
        self.start         = None # flow start
        self.end           = None # flow end
        self.slottedPkts   = None # flow slotted packets
        self.slottedDelays = None # flow slotted delays
        self.slottedBytes  = None # flow slotted bytes
        self.lostSentBytes = None # flow lost bytes
        self.allSentBytes  = None # flow sent bytes


    #
    # Method computes the flow's data first and last arrivals.
    # param [in] directory - input directory containing the log file
    # throws DataError
    #
    def compute_time_bounds(self, directory):
        self.start, self.end = get_duration(directory, self.id + 1)


    #
    # Method computes average data for the flow
    # param [in] directory   - input directory containing the log file
    # param [in] slotsNumber - number of slots
    # param [in] slotSec     - float slot size in seconds
    # throws DataError
    #
    def compute_average_data(self, directory, slotsNumber, slotSec):
        arrivals, delays, sizes, loss = load_data(directory, self.id + 1)

        self.lostSentBytes, self.allSentBytes = loss

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

        del self.slottedPkts
        del self.slottedDelays
        del self.slottedBytes

        del self.lostSentBytes
        del self.allSentBytes


    #
    # Method gets arrays of arrival timestamps and of delays of all the packets of the flow
    # param [in] directory - input directory containing the log data-file of the flow
    # returns arrival timestamps and delays of the packets of the flow
    # throws DataError
    #
    def get_delays(self, directory):
        return load_delays(directory, self.id + 1)


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
