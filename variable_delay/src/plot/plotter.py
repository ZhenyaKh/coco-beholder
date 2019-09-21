#!/usr/bin/env python

import gc
import math

from variable_delay.src.metadata.metadata import load_metadata, MetadataError
from variable_delay.src.metadata.metadata_fields import ALL_FLOWS, SORTED_LAYOUT
from variable_delay.src.data.data import DataError
from variable_delay.src.plot.plotter_args import *
from variable_delay.src.plot.flow import Flow
from variable_delay.src.plot.average_rate import AverageRate
from variable_delay.src.plot.average_delay import AverageDelay
from variable_delay.src.plot.jain_index import JainIndex
from variable_delay.src.plot.loss import Loss
from variable_delay.src.plot.per_packet_delay import PerPacketDelay
from variable_delay.src.plot.stats_writer import StatsWriter, StatsWriterError


#
# Class the instance of which allows to make plots and stats over data extracted from pcap-files
#
class Plotter(object):
    #
    # Constructor
    # param [in] args - dictionary of the plotter arguments
    # throws MetadataError
    #
    def __init__(self, args):
        self.outDir          = args[OUT_DIR]           # full path of output folder for plots/stats
        self.plotType        = args[PLOT_TYPE]         # type of graphs and stats to make
        self.jainsIndexColor = args[JAINS_INDEX_COLOR] # color of Jain's Index curve
        self.colorCycle      = args[COLOR_CYCLE]       # color cycle for curves

        metadata = load_metadata(args[IN_DIR])

        flowsNumber = metadata[ALL_FLOWS]
        flows       = [ Flow(i) for i in range(flowsNumber) ]
        self.curves = self.plotType.get_curves(metadata[SORTED_LAYOUT], flows) # the curves to plot

        type(self.curves[0]).IN_DIR   = args[IN_DIR]
        type(self.curves[0]).SLOT_SEC = float(args[SLOT_SEC])


    #
    # Method generates plots and stats over data extracted from pcap-files
    # throws DataError, StatsWriterError
    #
    def generate(self):
        self.generate_average()

        gc.collect()

        self.generate_per_packet()


    #
    # Method generates average plots/stats: average rate, average Jain index, average one-way delay
    # throws DataError, StatsWriterError
    #
    def generate_average(self):
        print('Loading data of the curves to make average plots and stats...')
        self.compute_curves_average_data()

        print('Plotting average throughput...')
        averageRate  = AverageRate (self.outDir, self.plotType, self.curves, self.colorCycle)
        averageRate. plot()

        print('Plotting average one-way delay...')
        averageDelay = AverageDelay(self.outDir, self.plotType, self.curves, self.colorCycle)
        averageDelay.plot()

        print('Plotting average Jain\'s index...')
        jainIndex    = JainIndex   (self.outDir, self.plotType, averageRate, self.jainsIndexColor)
        jainIndex.   plot()

        print('Saving average statistics...')
        statsWriter = StatsWriter(self.outDir, self.plotType, self.curves)
        statsWriter.write_average(averageRate, averageDelay, jainIndex, Loss(self.curves))

        self.free_curves_data()


    #
    # Method generates per packet plots/stats: per packet one-way delay
    # throws DataError, StatsWriterError
    #
    def generate_per_packet(self):
        print('Plotting per packet one-way delay...')
        perPacketDelay = PerPacketDelay(self.outDir, self.plotType, self.curves, self.colorCycle)
        perPacketDelay.plot()

        print('Saving per-packet statistics...')
        statsWriter = StatsWriter(self.outDir, self.plotType, self.curves)
        statsWriter.append_per_packet(perPacketDelay)


    #
    # Method computes average data for each curve
    # throws DataError
    #
    def compute_curves_average_data(self):
        self.compute_curves_time_bounds()

        type(self.curves[0]).SLOTS_NUMBER = self.compute_slots_number()

        for curve in self.curves:
            curve.compute_average_data()

        self.free_flows_data()


    #
    # Methods computes start and end timestamps for each curve
    # throws DataError
    #
    def compute_curves_time_bounds(self):
        for curve in self.curves:
            curve.compute_time_bounds()


    #
    # Methods computes number of time slots for average graphs
    # returns slots number
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
            slotsNumber = int(0)
        else:
            slotsNumber = int(math.ceil(maxEnd / self.curves[0].SLOT_SEC))

        return slotsNumber


    #
    # Method frees the data of all the flows
    #
    def free_flows_data(self):
        for curve in self.curves:
            curve.free_flows_data()


    #
    # Method frees data of the curves
    #
    def free_curves_data(self):
        for curve in self.curves:
            curve.free_data()
