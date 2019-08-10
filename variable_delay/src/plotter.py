#!/usr/bin/env python

import gc
import math

from variable_delay.src.metadata import load_metadata, MetadataError
from variable_delay.src.metadata_fields import ALL_FLOWS, SORTED_LAYOUT
from variable_delay.src.data import DataError
from variable_delay.src.flow import Flow
from variable_delay.src.average_rate import AverageRate
from variable_delay.src.average_delay import AverageDelay
from variable_delay.src.jain_index import JainIndex
from variable_delay.src.loss import Loss
from variable_delay.src.per_packet_delay import PerPacketDelay
from variable_delay.src.stats_writer import StatsWriter, StatsWriterError


#
# Class the instance of which allows to make plots and stats over data extracted from pcap-files
#
class Plotter(object):
    #
    # Constructor
    # param [in] inDir    - full path of directory with input data-files
    # param [in] outDir   - full path of output directory for graphs and stats
    # param [in] interval - interval in seconds per which average graphs are averaged
    # param [in] plotType - type of graphs and stats to make
    # throws MetadataError
    #
    def __init__(self, inDir, outDir, interval, plotType):
        self.inDir   = inDir           # full path of directory with input data-files
        self.outDir  = outDir          # full path of output directory for graphs and stats
        self.slotSec = float(interval) # interval in seconds per which average graphs are averaged
        self.type    = plotType        # type of graphs and stats to make

        metadata = load_metadata(self.inDir)

        flowsNumber = metadata[ALL_FLOWS]
        self.flows  = [ Flow(i) for i in range(flowsNumber) ]                   # flows
        self.curves = self.type.get_curves(metadata[SORTED_LAYOUT], self.flows) # curves


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
        self.compute_curves_time_bounds()

        slotsNumber = self.compute_slots_number()

        print('Loading data of the curves to make average plots and stats...')
        self.compute_curves_average_data(slotsNumber)

        self.free_flows_data()

        print('Plotting average throughput...')
        averageRate  = AverageRate (self.outDir, self.type, self.curves, self.slotSec)
        averageRate. plot()

        print('Plotting average one-way delay...')
        averageDelay = AverageDelay(self.outDir, self.type, self.curves, self.slotSec)
        averageDelay.plot()

        print('Plotting average Jain\'s index...')
        jainIndex    = JainIndex   (self.outDir, self.type, self.curves, self.slotSec, averageRate)
        jainIndex.   plot()

        print('Saving average statistics...')
        statsWriter = StatsWriter(self.outDir, self.type, self.curves)
        statsWriter.write_average(averageRate, averageDelay, jainIndex, Loss(self.curves))

        self.free_curves_data()


    #
    # Method generates per packet plots/stats: per packet one-way delay
    # throws DataError, StatsWriterError
    #
    def generate_per_packet(self):
        print('Plotting per packet one-way delay...')
        perPacketDelay = PerPacketDelay(self.inDir, self.outDir, self.type, self.curves)
        perPacketDelay.plot()

        print('Saving per-packet statistics...')
        statsWriter = StatsWriter(self.outDir, self.type, self.curves)
        statsWriter.append_per_packet(perPacketDelay)


    #
    # Methods computes start and end timestamps for each curve
    # throws DataError
    #
    def compute_curves_time_bounds(self):
        for curve in self.curves:
            curve.compute_time_bounds(self.inDir)


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
            slotsNumber = int(math.ceil(maxEnd / self.slotSec))

        return slotsNumber


    #
    # Method computes average data for each curve
    # param [in] slotsNumber - number of slots
    # throws DataError
    #
    def compute_curves_average_data(self, slotsNumber):
        for curve in self.curves:
            curve.compute_average_data(self.inDir, slotsNumber, self.slotSec)


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
