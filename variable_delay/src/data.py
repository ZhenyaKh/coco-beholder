#!/usr/bin/env python

import os
import json

DATA = 'data'
LOG  = 'log'


#
# Custom Exception class for errors connected to reading and writing of flow data
#
class DataError(Exception):
    pass


#
# Function writes flow data to a log file.
# param [in] directory - output directory to which the data should be saved
# param [in] flow      - flow index
# param [in] arrivals  - timestamps of arrivals of the flow's packets
# param [in] delays    - one-way delays of the flow's packets
# param [in] sizes     - sizes in bytes of the flow's packets
# throws DataError
#
def save_data(directory, flow, arrivals, delays, sizes):
    filePath = os.path.join(directory, "{}-{:d}.{}".format(DATA, flow + 1, LOG))

    try:
        # file.write(json.dumps(data)) requires extra memory but is about two times faster than
        # json.dump(data, file). So, here, speed is chosen over memory consumption.
        with open(filePath, 'w') as file:
            file.write(json.dumps(arrivals))
            file.write('\n')
            file.write(json.dumps(delays))
            file.write('\n')
            file.write(json.dumps(sizes))
            file.write('\n')
    except IOError:
        raise DataError('Failed to write flow\'s data to the file %s' % filePath)
