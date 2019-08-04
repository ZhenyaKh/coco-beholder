#!/usr/bin/env python

import os

WRITE_MODE      = 'w'
APPEND_MODE     = 'a'
STATISTICS      = 'stats'
STATS_EXTENSION = 'log'


#
# Custom Exception class for errors connected to writing of statistics to the statistics file
#
class StatsWriterError(Exception):
    pass


#
# Class the instance of which writes statistics to the statistics file
#
class StatsWriter(object):
    #
    # Constructor
    # param [in] outDir   - full path of output directory for graphs and stats
    # param [in] plotType - type of graphs and stats to make
    # param [in] curves   - the curves whose stats to write
    #
    def __init__(self, outDir, plotType, curves):
        filename = '{}-{}.{}'.format(plotType.get_filename_prefix(), STATISTICS, STATS_EXTENSION)

        self.path   = os.path.join(outDir, filename) # full path of output stats file
        self.curves = curves                         # the curves whose stats to write
        self.mode   = None                           # writing mode


    #
    # Method writes average stats to the stats file
    # param [in] averageRate  - average rate whose stats should be saved
    # param [in] averageDelay - average delay whose stats should be saved
    # param [in] jainIndex    - average Jain's index whose stats should be saved
    # param [in] loss         - loss whose stats should be saved
    # throws StatsWriterError
    #
    def write_average(self, averageRate, averageDelay, jainIndex, loss):
        self.mode = WRITE_MODE

        self.save_average(averageRate, averageDelay, jainIndex, loss)


    #
    # Method appends average stats to the stats file
    # param [in] averageRate  - average rate whose stats should be saved
    # param [in] averageDelay - average delay whose stats should be saved
    # param [in] jainIndex    - average Jain's index whose stats should be saved
    # param [in] loss         - loss whose stats should be saved
    # throws StatsWriterError
    #
    def append_average(self, averageRate, averageDelay, jainIndex, loss):
        self.mode = APPEND_MODE

        self.save_average(averageRate, averageDelay, jainIndex, loss)


    #
    # Method saves average stats to the stats file in the chosen writing mode
    # param [in] averageRate  - average rate whose stats should be saved
    # param [in] averageDelay - average delay whose stats should be saved
    # param [in] jainIndex    - average Jain's index whose stats should be saved
    # param [in] loss         - loss whose stats should be saved
    # throws StatsWriterError
    #
    def save_average(self, averageRate, averageDelay, jainIndex, loss):
        output = ''

        output += '{}\n\n'.format(jainIndex.get_stats_string())

        for curve in self.curves:
            output += '-- Curve "{}":\n'.format(curve.name)
            output += '{}\n'          .format(averageRate .get_stats_string(curve))
            output += '{}\n'          .format(averageDelay.get_stats_string(curve))
            output += '{}\n\n'        .format(loss        .get_stats_string(curve))
        try:
            with open(self.path, self.mode) as file:
                file.write(output)
        except IOError as error:
            raise StatsWriterError(
                'Failed to save average statistics to the file %s:\n%s' % (self.path, error))
