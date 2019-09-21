#!/usr/bin/env python

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

from variable_delay.src.plot.plot_utils import get_x_limit, get_marker, flip

AVERAGE_DELAY   = 'avg-delay'
PLOTS_EXTENSION = 'png'
LABELS_IN_ROW   = 4
FONT_SIZE       = 12


#
# Class the instance of which allows to make average delay graph and stats
#
class AverageDelay(object):
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
        self.statsDelays   = { }                                  # per curve: average delays stats

        filename = '{}-{}.{}'.format(plotType.get_filename_prefix(), AVERAGE_DELAY, PLOTS_EXTENSION)

        self.path = os.path.join(outDir, filename)                # full path of output graph

        self.compute_stats()


    #
    # Method plots average delay of curves
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
        ax.set_ylabel('One-way delay (ms)',                                fontsize=FONT_SIZE)
        ax.set_title (self.get_title(), loc='right',                       fontsize=FONT_SIZE)
        ax.grid()

        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels,  LABELS_IN_ROW),
                           ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                           fontsize=FONT_SIZE)

        figure.savefig(self.path, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method gets the statistics string of the average delay of the curve
    # param [in] curve - the curve whose average delay stats string is queried
    # returns the statistics string of the curve
    #
    def get_stats_string(self, curve):
        statsDelay = self.statsDelays[curve]

        if statsDelay is None:
            valueStr = 'N/A as the curve has no packets'
        else:
            valueStr = '{:f} ms'.format(statsDelay)

        return 'Average one-way delay : {}'.format(valueStr)


    #
    # Method computes x-axis and y-axis data to plot average delay of the curve
    # param [in] curve - the curve to plot
    # returns x-data and y-data of the curve
    #
    def get_data(self, curve):
        xData = []
        yData = []

        for slotId, delays in enumerate(curve.slottedDelays):
            if curve.slottedPkts[slotId] != 0:
                yData.append(float(delays) / curve.slottedPkts[slotId])
                xData.append(self.slotSec * slotId)

        return xData, yData


    #
    # Method generates the label of the curve in the average delay graph
    # returns the label of the curve
    #
    def get_label(self, curve):
        statsDelay = self.statsDelays[curve]

        if statsDelay is None:
            valueStr = 'no packets'
        else:
            valueStr = '{:.2f} ms'.format(statsDelay)

        return '{} ({})'.format(curve.name, valueStr)


    #
    # Method gets the title of the average delay graph
    #
    def get_title(self):
        return '{} {}'.format(self.labelNotation, '(<average delay>)')


    #
    # Method computes average delay stats of the curves
    #
    def compute_stats(self):
        for curve in self.curves:
            statsDelay = None
            sumDelays  = sum(curve.slottedDelays)
            sumPackets = sum(curve.slottedPkts)

            if sumPackets != 0:
                statsDelay = float(sumDelays) / sumPackets

            self.statsDelays[curve] = statsDelay
