#!/usr/bin/env python

import os
import math
import itertools
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

from variable_delay.src.metadata import load_metadata, MetadataError
from variable_delay.src.metadata_fields import ALL_FLOWS
from variable_delay.src.data import load_data, get_data_duration, DataError

BITS_IN_BYTE     = 8
BITS_IN_MBITS    = 1000000
AVERAGE_RATE     = 'avg-rate'
AVERAGE_FAIRNESS = 'avg-jain'
AVERAGE_DELAY    = 'avg-delay'
PER_PACKET_DELAY = 'ppt-delay'
STATISTICS       = 'stats'
PLOTS_EXTENSION  = 'png'
STATS_EXTENSION  = 'log'
LABELS_IN_ROW    = 4
FONT_SIZE        = 12


#
# Class the instance of which allows to make plots and stats over data extracted from pcap-files
#
class Plotter(object):
    #
    # Constructor
    # param[in] inDir    - full path of directory with input data-files
    # param[in] outDir   - full path of output directory for graphs and stats
    # param[in] interval - interval in seconds per which average graphs are averaged
    # param[in] type     - type of graphs and stats to make
    # throws MetadataError
    #
    def __init__(self, inDir, outDir, interval, type):
        self.inDir   = inDir           # full path of directory with input data-files
        self.outDir  = outDir          # full path of output directory for graphs and stats
        self.slotSec = float(interval) # interval in seconds per which average graphs are averaged
        self.type    = type            # type of graphs and stats to make
        self.curves  = None            # list of lists of flows merged into a curve
        self.labels  = None            # list of names of the curves

        metadata = load_metadata(self.inDir)

        self.curves, self.labels = self.type.get_curves(metadata)

        self.flows       = metadata[ALL_FLOWS] # total number of flows
        self.starts      = [None] *self.flows  # per flow timestamps of first arrivals
        self.ends        = [None] *self.flows  # per flow timestamps of last arrivals
        self.slotsNumber = None                # number of slots

        # TODO: empty flows!

        self.flowSlottedPkts    = None # per flow number of packets divided into slots
        self.flowSlottedDelays  = None # per flow sum of delays of all the packets in the slot
        self.flowSlottedBytes   = None # per flow number of packets' bytes divided into slots
        #self.curveSlottedPkts   = None # per curve number of packets divided into slots
        #self.curveSlottedDelays = None # per curve sum of delays of all the packets in the slot
        self.curveSlottedBytes  = None # per curve number of packets' bytes divided into slots
        self.curveAvgRate       = None

        # full paths of output graphs and stats
        self.avgRatePath  = self.get_output_file_name(AVERAGE_RATE,     PLOTS_EXTENSION)
        self.avgJainPath  = self.get_output_file_name(AVERAGE_FAIRNESS, PLOTS_EXTENSION)
        self.avgDelayPath = self.get_output_file_name(AVERAGE_DELAY,    PLOTS_EXTENSION)
        self.pptDelayPath = self.get_output_file_name(PER_PACKET_DELAY, PLOTS_EXTENSION)
        self.statsPath    = self.get_output_file_name(STATISTICS,       STATS_EXTENSION)



    #
    # Method generates plots and stats over data extracted from pcap-files.
    # throws MetadataError
    #
    def generate(self):
        self.plot_average()


    #
    #
    #
    def get_output_file_name(self, filenameRoot, extension):
        filename = '{}-{}.{}'.format(self.type.get_filename_prefix(), filenameRoot, extension)

        fullPath = os.path.join(self.outDir, filename)

        return fullPath


    #
    #
    #
    def plot_average(self):
        self.get_flows_durations()

        self.compute_slots_number()

        self.compute_slotted_flow_data()

        self.compute_slotted_curve_data()

        del self.flowSlottedPkts  [:]
        del self.flowSlottedDelays[:]
        del self.flowSlottedBytes [:]

        self.compute_curve_stats()

        self.plot_average_rate()




    #
    # Methods gets start and end timestamps for each flow
    #
    def get_flows_durations(self):
        for flow in range(0, self.flows):
            self.starts[flow], self.ends[flow] = get_data_duration(self.inDir, flow)


    #
    # Methods computes number of slots
    #
    def compute_slots_number(self):
        maxEnd = None

        for end in self.ends:
            if end is not None:
                if maxEnd is None:
                    maxEnd = end
                else:
                    maxEnd = max(end, maxEnd)

        if maxEnd is None:
            self.slotsNumber = int(0)
        else:
            self.slotsNumber = int(math.ceil(max(self.ends) / self.slotSec))


    #
    # Method computes slotted data for each flow
    #
    def compute_slotted_flow_data(self):
        self.flowSlottedPkts   = [None] * self.flows
        self.flowSlottedDelays = [None] * self.flows
        self.flowSlottedBytes  = [None] * self.flows

        for flow in range(0, self.flows):
            arrivals, delays, sizes = load_data(self.inDir, flow)

            self.compute_slotted_packets(arrivals, flow)
            del arrivals[:]

            self.compute_slotted_delays(delays, flow)
            del delays[:]

            self.compute_slotted_bytes(sizes, flow)
            del sizes[:]


    #
    # Method computes slotted data for each curve
    #
    def compute_slotted_curve_data(self):
        #self.curveSlottedPkts   = [None] * len(self.curves)
        #self.curveSlottedDelays = [None] * len(self.curves)
        self.curveSlottedBytes  = [None] * len(self.curves)

        for index, curve in enumerate(self.curves):
            self.curveSlottedBytes[index] = self.merge_slotted_data(curve, self.flowSlottedBytes)



    #
    #
    #
    def compute_curve_stats(self):
        self.curveAvgRate = [None] * len(self.curves)

        for curveId in range(0, len(self.curves)):
            sumCurveBytes = sum(self.curveSlottedBytes[curveId])
            curveDuration = self.compute_curve_duration(self.curves[curveId])

            if curveDuration is not None and curveDuration != 0.0:
                avgRate = (sumCurveBytes * BITS_IN_BYTE) / (curveDuration * BITS_IN_MBITS)
                self.curveAvgRate[curveId] = avgRate


        print('!', self.curveAvgRate)


    #
    #
    #
    def plot_average_rate(self):
        figure, ax = plt.subplots(figsize=(16, 9))
        lineMarker = self.get_line_plot_marker()

        for index, curve in enumerate(self.curves):
            xData, yData = self.get_rate_curve_data(index)
            ax.plot(xData, yData, marker=lineMarker, label=self.make_curve_avg_rate_label(index))

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.set_xlim(self.get_x_limit())
        ax.set_xlabel('Time (s), interval %gs' % self.slotSec, fontsize=FONT_SIZE)
        ax.set_ylabel('Throughput (Mbit/s)',                   fontsize=FONT_SIZE)
        ax.grid()

        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(Plotter.flip(handles, LABELS_IN_ROW),
                           Plotter.flip(labels,  LABELS_IN_ROW), ncol=LABELS_IN_ROW,
                           bbox_to_anchor=(0.5, -0.1), loc='upper center', fontsize=FONT_SIZE)

        figure.savefig(self.avgRatePath,    bbox_extra_artists=(legend,),
                       bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Methods divides packets of a flow into time slots
    # param [in] arrivals - timestamps of packets' arrivals
    # param [in] flow     - flow index
    #
    def compute_slotted_packets(self, arrivals, flow):
        flowSlottedPkts = [0] * self.slotsNumber

        for arrival in arrivals:
            slotId = int(arrival / self.slotSec)

            flowSlottedPkts[slotId] += 1

        self.flowSlottedPkts[flow] = flowSlottedPkts


    #
    # Methods computed sums of delays of packets placed in one slot
    # param [in] delays - packets' delays
    # param [in] flow   - flow index
    #
    def compute_slotted_delays(self, delays, flow):
        flowSlottedDelays = [0] * self.slotsNumber

        firstPacket = 0

        for slotId, packets in enumerate(self.flowSlottedPkts[flow]):
            delaySum = 0.0

            for packet in range(firstPacket, firstPacket + packets):
                delaySum += delays[packet]

            firstPacket += packets

            flowSlottedDelays[slotId] = delaySum

        self.flowSlottedDelays[flow] = flowSlottedDelays


    #
    # Methods computed sums of bytes of packets placed in one slot
    # param [in] sizes - packets' sizes in bytes
    # param [in] flow  - flow index
    #
    def compute_slotted_bytes(self, sizes, flow):
        flowSlottedBytes = [0] * self.slotsNumber

        firstPacket = 0

        for slotId, packets in enumerate(self.flowSlottedPkts[flow]):
            bytesSum = 0

            for packet in range(firstPacket, firstPacket + packets):
                bytesSum += sizes[packet]

            firstPacket += packets

            flowSlottedBytes[slotId] = bytesSum

        self.flowSlottedBytes[flow] = flowSlottedBytes


    #
    #
    #
    def merge_slotted_data(self, curve, perFlowData):
        mergedData = [0] * self.slotsNumber

        for slotId in range(0, self.slotsNumber):
            for flow in curve:
                mergedData[slotId] += perFlowData[flow][slotId]

        return mergedData


    #
    #
    #
    def compute_curve_duration(self, curve):
        minStart = None
        maxEnd   = None

        for flow in curve:
            if self.starts[flow] is not None:
                if minStart is None:
                    minStart = self.starts[flow]
                else:
                    minStart = min(minStart, self.starts[flow])

            if self.ends[flow] is not None:
                if maxEnd is None:
                    maxEnd = self.ends[flow]
                else:
                    maxEnd = max(maxEnd, self.ends[flow])

        if minStart is None:
            assert maxEnd is None
            duration = None
        else:
            duration = maxEnd - minStart

        return duration


    #
    #
    #
    def get_rate_curve_data(self, curveId):
        xData = []
        yData = []

        for slotId in range(0, self.slotsNumber):
            yValue = self.curveSlottedBytes[curveId][slotId] * BITS_IN_BYTE
            yValue = yValue / (self.slotSec * BITS_IN_MBITS)

            if yValue == 0.0 and len(yData) == 0:
                continue # cut off front slots with zeroes

            yData.append(yValue)
            xData.append(self.slotSec * slotId)

        print("ydata", yData)
        return xData, yData


    #
    #
    #
    def make_curve_avg_rate_label(self, curveId):
        if self.curveAvgRate[curveId] is None:
            valueStr = 'no packets'
        else:
            valueStr = '{:.2f} Mbps'.format(self.curveAvgRate[curveId])

        return '{} ({})'.format(self.labels[curveId], valueStr)




    #
    #
    #
    def get_x_limit(self):
        if self.slotsNumber == 0 or self.slotsNumber == 1:
            minLimit = -1
            maxLimit = 1
        else:
            minLimit = 0
            maxLimit = int(math.ceil((self.slotsNumber - 1) * self.slotSec))

        print('max-limit', self.slotsNumber, self.slotsNumber * self.slotSec, maxLimit)

        return minLimit, maxLimit


    #
    #
    #
    def get_line_plot_marker(self):
        if self.slotsNumber <= 1:
            marker='o'
        else:
            marker = None

        return marker


    #
    # Method is used to make plot labels have horizontal layout, rather than vertical (default)
    # param [in] items - array of labels/handles should be supplied here
    # param [in] ncol  - required number of labels per row
    # returns labels/handles sorted in such a way that they will have horizontal layout
    #
    @staticmethod
    def flip(items, ncol):
        return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))
