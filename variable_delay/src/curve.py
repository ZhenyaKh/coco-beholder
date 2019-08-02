MIN_DURATION_SEC  = 0.005 # same value as in Wireshark
BITS_IN_BYTE      = 8
BITS_IN_MBITS     = 1000000
MS_IN_SEC         = 1000
PERCENTS          = 100.0


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
        self.flows         = flows # flows of the curve
        self.name          = name  # name of the curve

        self.start         = None  # curve's duration start time
        self.end           = None  # curve's duration end time

        self.slottedPkts   = None  # curve's slotted packets
        self.slottedDelays = None  # curve's slotted delays
        self.slottedBytes  = None  # curve's slotted bytes
        self.slottedRates  = None  # curve's slotted rates

        self.curveAvgRate  = None  # curve's average rate stats
        self.curveAvgDelay = None  # curve's average delay stats
        self.curveLoss     = None  # curve's loss percentage

        # to ensure that compute_time_bounds is called before any other methods
        del self.start
        del self.end


    #
    # Method computes the curve's data first and last arrivals.
    # param [in] directory - input directory containing the log files
    # throws DataError
    #
    def compute_time_bounds(self, directory):
        minStart = None
        maxEnd   = None

        for flow in self.flows:
            flow.compute_time_bounds(directory)

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
    # param [in] directory   - input directory containing the log files
    # param [in] slotsNumber - number of slots
    # param [in] slotSec     - float slot size in seconds
    # throws DataError
    #
    def compute_average_data(self, directory, slotsNumber, slotSec):
        for flow in self.flows:
            flow.compute_average_data(directory, slotsNumber, slotSec)

        self.slottedPkts   = [0] * len(self.flows[0].slottedPkts)
        self.slottedDelays = [0] * len(self.slottedPkts)
        self.slottedBytes  = [0] * len(self.slottedPkts)

        for slotId in range(0, len(self.slottedPkts)):
            for flow in self.flows:
                self.slottedPkts[slotId]   += flow.slottedPkts[slotId]
                self.slottedDelays[slotId] += flow.slottedDelays[slotId]
                self.slottedBytes[slotId]  += flow.slottedBytes[slotId]

        self.compute_stats()


    #
    # Method frees the data of the flows belonging to the curve
    #
    def free_flows_data(self):
        for flow in self.flows:
            flow.free_data()


    #
    # Method computes x-axis and y-axis data to plot average rate of the curve
    # param [in] slotSec - float slot size in seconds
    # returns x-data and y-data
    #
    def get_avg_rate_data(self, slotSec):
        xData = []
        yData = []

        self.slottedRates = [None] * len(self.slottedBytes)

        if self.start is not None:
            startSlotId = int(self.start / slotSec)
            endSlotId   = int(self.end   / slotSec)

            for slotId in range(startSlotId, endSlotId + 1):
                yValue = self.slottedBytes[slotId] * BITS_IN_BYTE / (slotSec * BITS_IN_MBITS)

                yData.append(yValue)
                xData.append(slotSec * slotId)

                self.slottedRates[slotId] = yValue

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
        valueStr = None

        if self.curveAvgRate is None:
            if self.start is None:
                valueStr = 'no packets'
            else:
                duration = float(self.end - self.start)

                if duration < MIN_DURATION_SEC:
                    valueStr = '<{:g}ms duration'.format(MIN_DURATION_SEC * MS_IN_SEC)
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
    # Method finds the label notation for averaged rate graph
    # param [in] graphType - type of graph
    # returns the label notation
    #
    @staticmethod
    def avg_rate_label_notation(graphType):
        return '{} (<average throughput>)'.format(graphType.get_label_notation_prefix())


    #
    # Method finds the label notation for averaged delay graph
    # param [in] graphType - type of graph
    # returns the label notation
    #
    @staticmethod
    def avg_delay_label_notation(graphType):
        return '{} (<average delay>)'.format(graphType.get_label_notation_prefix())


    #
    # Method frees the data of the curve itself
    #
    def free_data(self):
        del self.slottedPkts  [:]
        del self.slottedDelays[:]
        del self.slottedBytes [:]
        del self.slottedRates [:]

        del self.slottedPkts
        del self.slottedDelays
        del self.slottedBytes
        del self.slottedRates

        del self.curveAvgRate
        del self.curveAvgDelay
        del self.curveLoss


    #
    # Method gets the statistics string of the average rate
    # returns the statistics string
    #
    def get_avg_rate_stats_string(self):
        valueStr = None

        if self.curveAvgRate is None:
            if self.start is None:
                valueStr = 'N/A as the curve has no packets'
            else:
                duration = float(self.end - self.start)

                if duration < MIN_DURATION_SEC:
                    valueStr = 'N/A as the curve\'s duration is less than {:g}ms'.\
                        format(MIN_DURATION_SEC * MS_IN_SEC)
        else:
            valueStr = '{:f} Mbps'.format(self.curveAvgRate)

        return 'Average throughput    : {}'.format(valueStr)


    #
    # Method gets the statistics string of the average delay
    # returns the statistics string
    #
    def get_avg_delay_stats_string(self):
        if self.curveAvgDelay is None:
            valueStr = 'N/A as the curve has no packets'
        else:
            valueStr = '{:f} ms'.format(self.curveAvgDelay)

        return 'Average one-way delay : {}'.format(valueStr)


    #
    # Method gets the statistics string of the loss
    # returns the statistics string
    #
    def get_loss_stats_string(self):
        if self.curveLoss is None:
            valueStr = 'N/A as no bytes were sent by the curve\'s senders'
        else:
            valueStr = '{:f} %'.format(self.curveLoss)

        return 'Loss                  : {}'.format(valueStr)


    #
    # Method computes statistics values for the curve
    #
    def compute_stats(self):
        self.compute_average_rate()

        self.compute_average_delay()

        self.compute_loss()


    #
    # Method computes the curve's average throughput stats
    #
    def compute_average_rate(self):
        sumBytes = sum(self.slottedBytes)

        if self.start is not None:
            duration = float(self.end - self.start)

            if duration >= MIN_DURATION_SEC:
                self.curveAvgRate = (sumBytes * BITS_IN_BYTE) / (duration * BITS_IN_MBITS)


    #
    # Method computes the curve's average one-way delay stats
    #
    def compute_average_delay(self):
        sumDelays  = sum(self.slottedDelays)
        sumPackets = sum(self.slottedPkts)

        if sumPackets != 0:
            self.curveAvgDelay = float(sumDelays) / sumPackets


    #
    # Method computes the curve's loss rate stats
    #
    def compute_loss(self):
        lostSentBytes = 0
        allSentBytes  = 0

        for flow in self.flows:
            lostSentBytes += flow.lostSentBytes
            allSentBytes  += flow.allSentBytes

        if allSentBytes != 0:
            self.curveLoss = float(lostSentBytes) / allSentBytes * PERCENTS
