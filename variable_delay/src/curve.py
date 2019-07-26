BITS_IN_BYTE  = 8
BITS_IN_MBITS = 1000000


#
# Class the instance of which is a curve to plot
#
class Curve(object):
    #
    # Constructor
    # param [in] flows - flows constituting the curve
    # param [in] name  - the name of the curve
    #
    def __init__(self, flows, name):
        self.flows = flows        # flows of the curve
        self.name  = name         # name of the curve

        self.slottedPkts   = None # curve's slotted packets
        self.slottedDelays = None # curve's slotted delays
        self.slottedBytes  = None # curve's slotted bytes
        self.slottedRates  = None # curve's slotted rates

        self.duration = None      # duration of the curve

        self.curveAvgRate  = None # curve's average rate stats
        self.curveAvgDelay = None # curve's average delay stats


    #
    # Method computes per slot data of the curve
    #
    def merge_flows_slotted_data(self):
        self.slottedPkts   = [0] * len(self.flows[0].slottedPkts)
        self.slottedDelays = [0] * len(self.slottedPkts)
        self.slottedBytes  = [0] * len(self.slottedPkts)

        for slotId in range(0, len(self.slottedPkts)):
            for flow in self.flows:
                self.slottedPkts[slotId]   += flow.slottedPkts[slotId]
                self.slottedDelays[slotId] += flow.slottedDelays[slotId]
                self.slottedBytes[slotId]  += flow.slottedBytes[slotId]


    #
    # Method computes statistics values for the curve
    #
    def compute_stats(self):
        self.compute_duration()

        sumBytes = sum(self.slottedBytes)

        if self.duration is not None:
            # Curve duration is not zero because Flow duration is ensured not to be zero
            self.curveAvgRate = (sumBytes * BITS_IN_BYTE) / (float(self.duration) * BITS_IN_MBITS)

        sumDelays  = sum(self.slottedDelays)
        sumPackets = sum(self.slottedPkts)

        if sumPackets != 0:
            self.curveAvgDelay = float(sumDelays) / sumPackets


    #
    # Method computes x-axis and y-axis data to plot average rate of the curve
    # param [in] slotSec - slot size in seconds
    # returns x-data and y-data
    #
    def get_avg_rate_data(self, slotSec):
        xData = []
        yData = []

        self.slottedRates = []

        for slotId, bytes in enumerate(self.slottedBytes):
            yValue = bytes * BITS_IN_BYTE
            yValue = yValue / (slotSec * BITS_IN_MBITS)

            if yValue == 0.0 and len(yData) == 0:
                self.slottedRates.append(None)
                continue # cut off front slots with zeroes

            yData.append(yValue)
            xData.append(slotSec * slotId)

            self.slottedRates.append(yValue)

        return xData, yData


    #
    # Method computes x-axis and y-axis data to plot average delay of the curve
    # param [in] slotSec - slot size in seconds
    # returns x-data and y-data
    #
    def get_avg_delay_data(self, slotSec):
        xData = []
        yData = []

        for slotId, delays in enumerate(self.slottedDelays):
            if self.slottedPkts[slotId] != 0:
                yData.append(float(delays) / self.slottedPkts[slotId])
                xData.append(slotSec * slotId)

        return xData, yData


    #
    # Method generates the label of the curve for the graph of the averaged rate of the curve
    # returns the label
    #
    def avg_rate_label(self):
        if self.curveAvgRate is None:
            valueStr = 'no packets'
        else:
            valueStr = '{:.2f} Mbps'.format(self.curveAvgRate)

        return '{} ({})'.format(self.name, valueStr)


    #
    # Method generates the label of the curve for the graph of the averaged delay of the curve
    # returns the label
    #
    def avg_delay_label(self):
        if self.curveAvgDelay is None:
            valueStr = 'no packets'
        else:
            valueStr = '{:.2f} ms'.format(self.curveAvgDelay)

        return '{} ({})'.format(self.name, valueStr)


    #
    # Method computes duration of the curve
    #
    def compute_duration(self):
        minStart = None
        maxEnd   = None

        for flow in self.flows:
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
            self.duration = None
        else:
            self.duration = maxEnd - minStart
