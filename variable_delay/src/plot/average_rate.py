#!/usr/bin/env python

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

from variable_delay.src.plot.plot_utils import get_x_limit, get_marker, flip

AVERAGE_RATE     = 'avg-rate'
PLOTS_EXTENSION  = 'png'
LABELS_IN_ROW    = 4
FONT_SIZE        = 12
MIN_DURATION_SEC = 0.005 # same value as in Wireshark
MS_IN_SEC        = 1000
BITS_IN_BYTE     = 8
BITS_IN_MBITS    = 1000000


#
# Class the instance of which allows to make average rate graph and stats
#
class AverageRate(object):
    #
    # Constructor
    # param [in] outDir     - full path of output directory for graphs and stats
    # param [in] plotType   - type of graphs and stats to make
    # param [in] curves     - list of curves to plot
    # param [in] colorCycle - color cycle for curves
    #
    def __init__(self, outDir, plotType, curves, colorCycle):
        self.curves        = curves                               # curves to plot
        self.slotSec       = curves[0].SLOT_SEC                   # float slot size in seconds
        self.slotsNumber   = curves[0].SLOTS_NUMBER               # number of slots
        self.colorCycle    = colorCycle                           # color cycle for curves
        self.labelNotation = plotType.get_label_notation_prefix() # label notation's prefix
        self.statsRates    = { }                                  # per curve: average rate stats
        self.slottedRates  = { }                                  # per curve: slotted rates

        filename = '{}-{}.{}'.format(plotType.get_filename_prefix(), AVERAGE_RATE, PLOTS_EXTENSION)

        self.path = os.path.join(outDir, filename)                # full path of output graph

        self.compute_rates()
        self.compute_stats()


    #
    # Method plots average rate of curves
    #
    def plot(self):
        figure, ax = plt.subplots(figsize=(16, 9))
        ax.set_prop_cycle(self.colorCycle)

        for curve in self.curves:
            xData, yData = self.get_data(curve)
            ax.plot(xData, yData, marker=get_marker(xData), label=self.get_label(curve))

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.set_xlim  (get_x_limit(self.slotsNumber, self.slotSec))
        ax.set_xlabel('Time (s), aggregation interval %gs' % self.slotSec, fontsize=FONT_SIZE)
        ax.set_ylabel('Throughput (Mbit/s)',                               fontsize=FONT_SIZE)
        ax.set_title (self.get_title(), loc='right',                       fontsize=FONT_SIZE)
        ax.grid()

        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels,  LABELS_IN_ROW),
                           ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                           fontsize=FONT_SIZE)

        figure.savefig(self.path, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method gets the curves
    # returns the curves
    #
    def get_curves(self):
        return self.curves


    #
    # Method gets the slotted rates of the curves
    # returns the slotted rates of the curves
    #
    def get_slotted_rates(self):
        return self.slottedRates


    #
    # Method gets the average rate stats of the curve
    # param [in] curve - the curve whose average rate stats is queried
    # returns the average rate stats of the curve
    #
    def get_stats(self, curve):
        return self.statsRates[curve]


    #
    # Method gets the statistics string of the average rate of the curve
    # param [in] curve - the curve whose average rate stats string is queried
    # returns the statistics string
    #
    def get_stats_string(self, curve):
        valueStr  = None
        statsRate = self.statsRates[curve]

        if statsRate is None:
            if curve.start is None:
                valueStr = 'N/A as the curve has no packets'
            else:
                duration = float(curve.end - curve.start)

                if duration < MIN_DURATION_SEC:
                    valueStr = 'N/A as the curve\'s duration is less than {:g}ms'.\
                        format(MIN_DURATION_SEC * MS_IN_SEC)
        else:
            valueStr = '{:f} Mbps'.format(statsRate)

        return 'Average throughput    : {}'.format(valueStr)


    #
    # Method computes x-axis and y-axis data to plot average rate of the curve
    # param [in] curve - the curve to plot
    # returns x-data and y-data of the curve
    #
    def get_data(self, curve):
        xData = []
        yData = []

        if curve.start is not None:
            startSlotId = int(curve.start / self.slotSec)
            endSlotId   = int(curve.end   / self.slotSec)

            for slotId in range(startSlotId, endSlotId + 1):
                yData.append(self.slottedRates[curve][slotId])
                xData.append(self.slotSec * slotId)

        return xData, yData


    #
    # Method generates the label of the curve in the average rate graph
    # returns the label of the curve
    #
    def get_label(self, curve):
        valueStr  = None
        statsRate = self.statsRates[curve]

        if statsRate is None:
            if curve.start is None:
                valueStr = 'no packets'
            else:
                duration = float(curve.end - curve.start)

                if duration < MIN_DURATION_SEC:
                    valueStr = '<{:g}ms duration'.format(MIN_DURATION_SEC * MS_IN_SEC)
        else:
            valueStr = '{:.2f} Mbps'.format(statsRate)

        return '{} ({})'.format(curve.name, valueStr)


    #
    # Method gets the title of the average rate graph
    #
    def get_title(self):
        return '{} {}'.format(self.labelNotation, '(<average throughput>)')


    #
    # Method computes slotted rates of the curves
    #
    def compute_rates(self):
        for curve in self.curves:
            curveSlottedRates = [None] * len(curve.slottedBytes)

            if curve.start is not None:
                startSlotId = int(curve.start / self.slotSec)
                endSlotId   = int(curve.end   / self.slotSec)

                for slotId in range(startSlotId, endSlotId + 1):
                    curveSlottedRates[slotId]  = curve.slottedBytes[slotId] * BITS_IN_BYTE
                    curveSlottedRates[slotId] /= self.slotSec * BITS_IN_MBITS

            self.slottedRates[curve] = curveSlottedRates


    #
    # Method computes average rate stats of the curves
    #
    def compute_stats(self):
        for curve in self.curves:
            statsRate = None
            sumBytes  = sum(curve.slottedBytes)

            if curve.start is not None:
                duration = float(curve.end - curve.start)

                if duration >= MIN_DURATION_SEC:
                    statsRate = (sumBytes * BITS_IN_BYTE) / (duration * BITS_IN_MBITS)

            self.statsRates[curve] = statsRate
