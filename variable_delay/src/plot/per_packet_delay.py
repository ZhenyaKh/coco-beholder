#!/usr/bin/env python

import os
import numpy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

from variable_delay.src.plot.plot_utils import flip

PPT_DELAY        = 'ppt-delay'
PLOTS_EXTENSION  = 'png'
LABELS_IN_ROW    = 4
FONT_SIZE        = 12


#
# Class the instance of which allows to make per-packet delay graph and stats
#
class PerPacketDelay(object):
    #
    # Constructor
    # param [in] outDir     - full path of output directory for graphs and stats
    # param [in] plotType   - type of graphs and stats to make
    # param [in] curves     - list of curves to plot
    # param [in] colorCycle - color cycle for curves
    #
    def __init__(self, outDir, plotType, curves, colorCycle):
        self.curves        = curves                               # curves to plot
        self.colorCycle    = colorCycle                           # color cycle for curves
        self.labelNotation = plotType.get_label_notation_prefix() # label notation's prefix

        self.statsAverages      = { } # per curve: average per-packet delay stats
        self.statsMedians       = { } # per curve: median per-packet delay stats
        self.stats95Percentiles = { } # per curve: 95th percentile per-packet delay stats

        filename = '{}-{}.{}'.format(plotType.get_filename_prefix(), PPT_DELAY, PLOTS_EXTENSION)

        self.path = os.path.join(outDir, filename) # full path of output graph


    #
    # Method plots per-packet delay of the curves
    # throws DataError
    #
    def plot(self):
        figure, ax = plt.subplots(figsize=(16, 9))
        ax.set_prop_cycle(self.colorCycle)

        for curve in self.curves:
            xData, yData = self.get_data(curve)
            ax.plot(xData, yData, marker='.', ms=1, ls="", label=self.get_label(curve))

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.autoscale (enable=True, axis='x', tight=True )   # use new x axis limit
        ax.set_xlabel('Time (s)',                      fontsize=FONT_SIZE)
        ax.set_ylabel('Per-packet one-way delay (ms)', fontsize=FONT_SIZE)
        ax.set_title (self.get_title(), loc='right',   fontsize=FONT_SIZE)
        ax.grid()

        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels,  LABELS_IN_ROW),
                           ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                           fontsize=FONT_SIZE, scatterpoints=1, markerscale=10, handletextpad=0)

        figure.savefig(self.path, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method gets the statistics string of the average per-packet delay of the curve
    # param [in] curve - the curve whose average per-packet delay stats string is queried
    # returns the statistics string of the curve
    #
    def get_average_stats_string(self, curve):
        statsAverage = self.statsAverages[curve]

        if statsAverage is None:
            valueStr = 'N/A as the curve has no packets'
        else:
            valueStr = '{:f} ms'.format(statsAverage)

        return 'Average per-packet one-way delay         : {}'.format(valueStr)


    #
    # Method gets the statistics string of the median per-packet delay of the curve
    # param [in] curve - the curve whose median per-packet delay stats string is queried
    # returns the statistics string of the curve
    #
    def get_median_stats_string(self, curve):
        statsMedian = self.statsMedians[curve]

        if statsMedian is None:
            valueStr = 'N/A as the curve has no packets'
        else:
            valueStr = '{:f} ms'.format(statsMedian)

        return 'Median per-packet one-way delay          : {}'.format(valueStr)


    #
    # Method gets the statistics string of the 95th percentile per-packet delay of the curve
    # param [in] curve - the curve whose  95th percentile per-packet delay stats string is queried
    # returns the statistics string of the curve
    #
    def get_95percentile_stats_string(self, curve):
        stats95Percentile = self.stats95Percentiles[curve]

        if stats95Percentile is None:
            valueStr = 'N/A as the curve has no packets'
        else:
            valueStr = '{:f} ms'.format(stats95Percentile)

        return '95th percentile per-packet one-way delay : {}'.format(valueStr)


    #
    # Method computes x-axis and y-axis data to plot per-packet delay of the curve
    # param [in] curve - the curve to plot
    # returns x-data and y-data of the curve
    # throws DataError
    #
    def get_data(self, curve):
        arrivals, delays = curve.get_delays()

        self.statsAverages     [curve] = None
        self.statsMedians      [curve] = None
        self.stats95Percentiles[curve] = None

        if len(delays) != 0:
            self.statsAverages     [curve] = numpy.average(delays)
            self.statsMedians      [curve] = numpy.percentile(delays, 50, interpolation='nearest')
            self.stats95Percentiles[curve] = numpy.percentile(delays, 95, interpolation='nearest')

        return arrivals, delays


    #
    # Method generates the label of the curve in the per-packet delay graph
    # returns the label of the curve
    #
    def get_label(self, curve):
        statsMedian = self.statsMedians[curve]

        if statsMedian is None:
            valueStr = 'no packets'
        else:
            valueStr = '{:.2f} ms'.format(statsMedian)

        return '{} ({})'.format(curve.name, valueStr)


    #
    # Method gets the title of the per-packet delay graph
    #
    def get_title(self):
        return '{} {}'.format(self.labelNotation, '(<median per-packet delay>)')
