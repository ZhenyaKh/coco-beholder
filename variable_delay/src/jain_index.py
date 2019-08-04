#!/usr/bin/env python

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

from variable_delay.src.plot_utils import get_x_limit, get_marker, flip

AVERAGE_JAIN    = 'avg-jain'
PLOTS_EXTENSION = 'png'
LABELS_IN_ROW   = 4
FONT_SIZE       = 12
CURVE           = 'curve'
CURVES          = 'curves'


#
# Class the instance of which allows to make Jain's index plot and stats
#
class JainIndex(object):
    #
    # Constructor
    # param [in] outDir      - full path of output directory for graphs and stats
    # param [in] plotType    - type of graphs and stats to make
    # param [in] curves      - list of curves to plot
    # param [in] slotSec     - float slot size in seconds
    # param [in] averageRate - average rate data of the curves
    #
    def __init__(self, outDir, plotType, curves, slotSec, averageRate):
        self.curves      = curves                      # curves to plot
        self.slotSec     = float(slotSec)              # float slot size in seconds
        self.slotsNumber = len(curves[0].slottedPkts)  # number of slots
        self.averageRate = averageRate                 # average rate data of the curves
        self.jainStats   = None                        # average Jain's index stats

        filename = '{}-{}.{}'.format(plotType.get_filename_prefix(), AVERAGE_JAIN, PLOTS_EXTENSION)

        self.path = os.path.join(outDir, filename)     # full path of output graph

        self.compute_stats()


    #
    # Method plots average Jain's index of the curves
    #
    def plot(self):
        figure, ax = plt.subplots(figsize=(16, 9))

        xData, yData = self.get_data()

        ax.plot(xData, yData, marker=get_marker(xData), label=self.get_label())

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.set_xlim  (get_x_limit(self.slotsNumber, self.slotSec))
        ax.set_xlabel('Time (s), aggregation interval %gs' % self.slotSec, fontsize=FONT_SIZE)
        ax.set_ylabel('Jain\'s index',                                     fontsize=FONT_SIZE)
        ax.set_title (self.get_title(), loc='right',                       fontsize=FONT_SIZE)
        ax.grid()

        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels, LABELS_IN_ROW),
                           ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                           fontsize=FONT_SIZE)

        figure.savefig(self.path, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method computes slotted Jain's index data to plot
    # returns x-data and y-data
    #
    def get_data(self):
        xData        = []
        yData        = []
        slottedRates = self.averageRate.get_slotted_rates()

        for slotId in range(self.slotsNumber):
            curvesNumber  = 0
            sumRate       = 0.0
            sumSquareRate = 0.0

            for curve in self.curves:
                if slottedRates[curve][slotId] is not None:
                    curvesNumber  += 1
                    sumRate       += slottedRates[curve][slotId]
                    sumSquareRate += slottedRates[curve][slotId]**2

            if curvesNumber != 0 and sumSquareRate != 0.0:
                xData.append(self.slotSec * slotId)
                yData.append(sumRate**2 / (float(curvesNumber) * sumSquareRate))

        return xData, yData


    #
    # Method generates the label of the single curve in the average Jain's index graph
    # returns the label of the single Jain's index curve
    #
    def get_label(self):
        if self.jainStats is None:
            valueStr = 'no average throughputs'
        else:
            valueStr = '{:f}'.format(self.jainStats)

        curvesWord = CURVE if len(self.curves) == 1 else CURVES

        curvesName = 'All {:d} {}'.format(len(self.curves), curvesWord)

        return '{} ({})'.format(curvesName, valueStr)


    #
    # Method gets the title of the average Jain's index graph
    #
    @staticmethod
    def get_title():
        return 'Label notation: All <curves number> curves ' \
               '(Jain\'s index over average throughputs of the curves)'


    #
    # Method generates the statistics string for the average Jain's index stats
    # returns the statistics string
    #
    def get_stats_string(self):
        if self.jainStats is None:
            valueStr = 'N/A as none of the curves has average throughput to count the index over'
        else:
            valueStr = '{:f}'.format(self.jainStats)

        return 'Average Jain\'s index  : {}'.format(valueStr)


    #
    # Method computes average Jain's index stats
    #
    def compute_stats(self):
        curvesNumber  = 0
        sumRate       = 0.0
        sumSquareRate = 0.0

        for curve in self.curves:
            rateStats = self.averageRate.get_stats(curve)

            if rateStats is not None:
                curvesNumber  += 1
                sumRate       += rateStats
                sumSquareRate += rateStats**2

        if curvesNumber != 0 and sumSquareRate != 0.0:
            self.jainStats = sumRate**2 / (float(curvesNumber) * sumSquareRate)
