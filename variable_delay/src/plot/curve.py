#!/usr/bin/env python

import itertools

#
# Class the instance of which is a curve to plot
#
class Curve(object):
    #
    # float time interval in seconds -- slot -- per which average graphs are averaged
    #
    SLOT_SEC = None


    #
    # number of slots
    #
    SLOTS_NUMBER = None


    #
    # full path of directory with input data-files
    #
    IN_DIR = None


    #
    # Constructor
    # param [in] flows - flows constituting the curve
    # param [in] name  - the name of the curve
    #
    def __init__(self, flows, name):
        self.flows         = flows # flows of the curve
        self.name          = name  # name of the curve

        self.start         = None  # curve's duration start time
        self.end           = None  # curve's duration end time

        self.slottedPkts   = None  # curve's slotted packets
        self.slottedDelays = None  # curve's slotted delays
        self.slottedBytes  = None  # curve's slotted bytes

        self.lostSentBytes = 0     # curve's lost bytes
        self.allSentBytes  = 0     # curve's sent bytes

        # to ensure that compute_time_bounds is called before any other methods
        del self.start
        del self.end


    #
    # Method computes the curve's data first and last arrivals
    # throws DataError
    #
    def compute_time_bounds(self):
        minStart = None
        maxEnd   = None

        for flow in self.flows:
            flow.compute_time_bounds(Curve.IN_DIR)

            if flow.start is not None:
                if minStart is None:
                    minStart = flow.start
                else:
                    minStart = min(minStart, flow.start)

            if flow.end is not None:
                if maxEnd is None:
                    maxEnd = flow.end
                else:
                    maxEnd = max(maxEnd, flow.end)

        if minStart is None:
            assert maxEnd is None
            self.start = None
            self.end   = None
        else:
            assert maxEnd is not None
            self.start = minStart
            self.end   = maxEnd


    #
    # Method computes average data for the curve
    # throws DataError
    #
    def compute_average_data(self):
        for flow in self.flows:
            flow.compute_average_data(Curve.IN_DIR, Curve.SLOTS_NUMBER, Curve.SLOT_SEC)
            self.lostSentBytes += flow.lostSentBytes
            self.allSentBytes  += flow.allSentBytes

        self.slottedPkts   = [0] * Curve.SLOTS_NUMBER
        self.slottedDelays = [0] * Curve.SLOTS_NUMBER
        self.slottedBytes  = [0] * Curve.SLOTS_NUMBER

        for slotId in range(Curve.SLOTS_NUMBER):
            for flow in self.flows:
                self.slottedPkts[slotId]   += flow.slottedPkts[slotId]
                self.slottedDelays[slotId] += flow.slottedDelays[slotId]
                self.slottedBytes[slotId]  += flow.slottedBytes[slotId]


    #
    # Method frees the data of the flows belonging to the curve
    #
    def free_flows_data(self):
        for flow in self.flows:
            flow.free_data()


    #
    # Method frees the data of the curve itself
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
    # Method gets arrays of arrival timestamps and of delays of all the packets of the curve
    # returns arrival timestamps and delays of the packets of the curve
    # throws DataError
    #
    def get_delays(self):
        curveArrivals = []
        curveDelays   = []

        for flow in self.flows:
            flowArrivals, flowDelays = flow.get_delays(Curve.IN_DIR)

            curveArrivals.append(flowArrivals)
            curveDelays  .append(flowDelays)

        return list(itertools.chain(*curveArrivals)), list(itertools.chain(*curveDelays))
