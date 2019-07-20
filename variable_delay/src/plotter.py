#!/usr/bin/env python

from variable_delay.src.metadata import load_metadata, MetadataError

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
        self.inDir  = inDir    # full path of directory with input data-files
        self.outDir = outDir   # full path of output directory for graphs and stats
        self.slot   = interval # interval in seconds per which average graphs are averaged
        self.type   = type     # type of graphs and stats to make


    #
    # Method generates plots and stats over data extracted from pcap-files.
    # thtows MetadataError
    #
    def generate(self):
        metadata = load_metadata(self.inDir)

        print(self.type.get_curves(metadata))
