#!/usr/bin/env python

import os
import gc
import math
import itertools
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

from variable_delay.src.metadata import load_metadata, MetadataError
from variable_delay.src.metadata_fields import ALL_FLOWS, SORTED_LAYOUT
from variable_delay.src.data import DataError
from variable_delay.src.flow import Flow
from variable_delay.src.jain_index import JainIndex
from variable_delay.src.stats_writer import StatsWriter, StatsWriterError

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

        metadata = load_metadata(self.inDir)

        flowsNumber      = metadata[ALL_FLOWS]
        self.flows       = [ Flow(i) for i in range(flowsNumber) ] # flows
        self.slotsNumber = None                                    # number of slots
        self.jainIndex   = None                                    # average Jain index
        self.statsWriter = StatsWriter()                           # statistics writer

        self.curves = self.type.get_curves(metadata[SORTED_LAYOUT], self.flows) # curves

        # full paths of output graphs and stats
        self.avgRatePath  = self.get_output_file_name(AVERAGE_RATE,     PLOTS_EXTENSION)
        self.avgJainPath  = self.get_output_file_name(AVERAGE_FAIRNESS, PLOTS_EXTENSION)
        self.avgDelayPath = self.get_output_file_name(AVERAGE_DELAY,    PLOTS_EXTENSION)
        self.pptDelayPath = self.get_output_file_name(PER_PACKET_DELAY, PLOTS_EXTENSION)
        self.statsPath    = self.get_output_file_name(STATISTICS,       STATS_EXTENSION)


    #
    # Method generates plots and stats over data extracted from pcap-files
    # throws DataError, StatsWriterError
    #
    def generate(self):
        self.generate_average()

        gc.collect()


    #
    # Method computes the full paths of the graphs
    #
    def get_output_file_name(self, filenameRoot, extension):
        filename = '{}-{}.{}'.format(self.type.get_filename_prefix(), filenameRoot, extension)

        fullPath = os.path.join(self.outDir, filename)

        return fullPath


    #
    # Method generates average plots/stats: average rate, average Jain index, average one-way delay
    # throws DataError, StatsWriterError
    #
    def generate_average(self):
        self.compute_curves_time_bounds()

        self.compute_slots_number()

        print('Loading data of the curves...')
        self.compute_curves_average_data()

        self.free_flows_data()

        print('Plotting average throughput...')
        self.plot_average_rate()

        print('Plotting average one-way delay...')
        self.plot_average_delay()

        self.jainIndex = JainIndex(self.curves)

        print('Plotting average Jain\'s index...')
        self.plot_average_jain_index()

        print('Saving average statistics...')
        self.statsWriter.write_average(self.statsPath, self.curves, self.jainIndex)

        self.free_curves_data()


    #
    # Methods computes start and end timestamps for each curve
    # throws DataError
    #
    def compute_curves_time_bounds(self):
        for curve in self.curves:
            curve.compute_time_bounds(self.inDir)


    #
    # Methods computes number of slots
    #
    def compute_slots_number(self):
        maxEnd = None

        for curve in self.curves:
            if curve.end is not None:
                if maxEnd is None:
                    maxEnd = curve.end
                else:
                    maxEnd = max(curve.end, maxEnd)

        if maxEnd is None:
            self.slotsNumber = int(0)
        else:
            self.slotsNumber = int(math.ceil(maxEnd / self.slotSec))


    #
    # Method computes average data for each curve
    # throws DataError
    #
    def compute_curves_average_data(self):
        for curve in self.curves:
            curve.compute_average_data(self.inDir, self.slotsNumber, self.slotSec)


    #
    # Method frees the data of all the flows
    #
    def free_flows_data(self):
        for curve in self.curves:
            curve.free_flows_data()


    #
    # Method plots average rate of curves
    #
    def plot_average_rate(self):
        figure, ax = plt.subplots(figsize=(16, 9))

        for curve in self.curves:
            xData, yData = curve.get_avg_rate_data(self.slotSec)
            ax.plot(xData, yData, marker=Plotter.get_marker(xData), label=curve.avg_rate_label())

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.grid()
        ax.set_xlim(self.get_slotted_graph_x_limit())
        ax.set_xlabel('Time (s), interval %gs' % self.slotSec,           fontsize=FONT_SIZE)
        ax.set_ylabel('Throughput (Mbit/s)',                             fontsize=FONT_SIZE)
        ax.set_title ('In ( ): the curve\'s overall average throughput', fontsize=FONT_SIZE,
                                                                         loc='right')
        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(Plotter.flip(handles, LABELS_IN_ROW),
                           Plotter.flip(labels,  LABELS_IN_ROW), ncol=LABELS_IN_ROW,
                           bbox_to_anchor=(0.5, -0.1), loc='upper center', fontsize=FONT_SIZE)

        figure.savefig(self.avgRatePath,    bbox_extra_artists=(legend,),
                       bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method plots average delay of curves
    #
    def plot_average_delay(self):
        figure, ax = plt.subplots(figsize=(16, 9))

        for curve in self.curves:
            xData, yData = curve.get_avg_delay_data(self.slotSec)
            ax.plot(xData, yData, marker=Plotter.get_marker(xData), label=curve.avg_delay_label())

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.set_xlim(self.get_slotted_graph_x_limit())
        ax.set_xlabel('Time (s), interval %gs' % self.slotSec,                   fontsize=FONT_SIZE)
        ax.set_ylabel('One-way delay (ms)',                                      fontsize=FONT_SIZE)
        ax.set_title ('In ( ): the curve\'s overall average delay', loc='right', fontsize=FONT_SIZE)
        ax.grid()

        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(Plotter.flip(handles, LABELS_IN_ROW),
                           Plotter.flip(labels,  LABELS_IN_ROW), ncol=LABELS_IN_ROW,
                           bbox_to_anchor=(0.5, -0.1), loc='upper center', fontsize=FONT_SIZE)

        figure.savefig(self.avgDelayPath,   bbox_extra_artists=(legend,),
                       bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method plots average Jain index of curves
    #
    def plot_average_jain_index(self):
        figure, ax = plt.subplots(figsize=(16, 9))

        xData, yData = self.jainIndex.get_data(self.slotsNumber, self.slotSec)

        ax.plot(xData, yData, marker=Plotter.get_marker(xData), label=self.jainIndex.get_label())

        ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation
        locator = plticker.MultipleLocator(base=1)          # enforce tick for each second on x axis
        ax.xaxis.set_major_locator(locator)

        ax.grid()
        ax.set_xlim(self.get_slotted_graph_x_limit())
        ax.set_xlabel('Time (s), interval %gs' % self.slotSec,                   fontsize=FONT_SIZE)
        ax.set_ylabel('Jain\'s index',                                           fontsize=FONT_SIZE)
        ax.set_title ('In ( ): index over curves\' overall average throughputs', fontsize=FONT_SIZE,
                                                                                 loc='right')
        handles, labels = ax.get_legend_handles_labels()

        legend = ax.legend(Plotter.flip(handles, LABELS_IN_ROW),
                           Plotter.flip(labels,  LABELS_IN_ROW), ncol=LABELS_IN_ROW,
                           bbox_to_anchor=(0.5, -0.1), loc='upper center', fontsize=FONT_SIZE)

        figure.savefig(self.avgJainPath,   bbox_extra_artists=(legend,),
                       bbox_inches='tight', pad_inches=0.2)

        plt.close(figure)


    #
    # Method frees data of the curves
    #
    def free_curves_data(self):
        for curve in self.curves:
            curve.free_data()


    #
    # Method finds x limit for the graphs of the slotted data
    #
    def get_slotted_graph_x_limit(self):
        if self.slotsNumber == 0 or self.slotsNumber == 1:
            minLimit = -1
            maxLimit = 1
        else:
            minLimit = 0
            maxLimit = int(math.ceil((self.slotsNumber - 1) * self.slotSec))

        return minLimit, maxLimit


    #
    # Method finds marker for line graphs
    # param [in] data - data to plot
    # returns the marker
    #
    @staticmethod
    def get_marker(data):
        if len(data) == 1:
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
