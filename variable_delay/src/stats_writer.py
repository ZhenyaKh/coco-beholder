#!/usr/bin/env python

WRITE_MODE  = 'w'
APPEND_MODE = 'a'

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
    #
    def __init__(self):
        self.mode = None # writing mode


    #
    # Method writes average stats to the stats file
    # param [in] filePath  - the full path of the file where stats should be saved to
    # param [in] curves    - curves average stats of which should be saved
    # param [in] jainIndex - average jain index stats
    # throws StatsWriterError
    #
    def write_average(self, filePath, curves, jainIndex):
        self.mode = WRITE_MODE

        self.save_average(filePath, curves, jainIndex)


    #
    # Method appends average stats to the stats file
    # param [in] filePath  - the full path of the file where stats should be saved to
    # param [in] curves    - curves average stats of which should be saved
    # param [in] jainIndex - average jain index stats
    # throws StatsWriterError
    #
    def append_average(self, filePath, curves, jainIndex):
        self.mode = APPEND_MODE

        self.save_average(filePath, curves, jainIndex)


    #
    # Method saves average stats to the stats file in the chosen writing mode
    # param [in] filePath  - the full path of the file where stats should be saved to
    # param [in] curves    - curves average stats of which should be saved
    # param [in] jainIndex - average jain index stats
    # throws StatsWriterError
    #
    def save_average(self, filePath, curves, jainIndex):
        output = ''

        output += '{}\n\n'.format(jainIndex.get_stats_string())

        for curve in curves:
            output += '-- Curve "{}":\n'.format(curve.name)
            output += '{}\n'          .format(curve.get_avg_rate_stats_string())
            output += '{}\n\n'        .format(curve.get_avg_delay_stats_string())
        try:
            with open(filePath, self.mode) as file:
                file.write(output)
        except IOError as error:
            raise StatsWriterError(
                'Failed to save average statistics to the file %s:\n%s' % (filePath, error))
