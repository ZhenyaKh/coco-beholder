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
# param [in] loss      - list: [the flows's lost bytes number, the flow's total sent bytes number]
# throws DataError
#
def save_data(directory, flow, arrivals, delays, sizes, loss):
    filePath = os.path.join(directory, "{}-{:d}.{}".format(DATA, flow + 1, LOG))

    duration = [None, None] if len(arrivals) == 0 else [arrivals[0], arrivals[-1]]

    try:
        # file.write(json.dumps(data)) requires extra memory but is about two times faster than
        # json.dump(data, file). So, here, speed is chosen over memory consumption.
        with open(filePath, 'w') as file:
            file.write(json.dumps(duration))
            file.write('\n')
            file.write(json.dumps(loss))
            file.write('\n')
            file.write(json.dumps(arrivals))
            file.write('\n')
            file.write(json.dumps(delays))
            file.write('\n')
            file.write(json.dumps(sizes))
            file.write('\n')
    except IOError as error:
        raise DataError('Failed to write flow\'s data to the file %s:\n%s' % (filePath, error))


#
# Function reads flow's data first and last arrivals.
# param [in] directory - input directory containing the log file
# param [in] flow      - flow index
# returns timestamps of flow's data first and last arrivals
# throws DataError
#
def get_duration(directory, flow):
    filePath = os.path.join(directory, "{}-{:d}.{}".format(DATA, flow, LOG))

    try:
        with open(filePath, 'r') as file:
            duration = json.loads(next(file))

            return duration

    except IOError as error:
        raise DataError('Failed to get flow\'s data duration from file %s:\n%s' % (filePath, error))


#
# Function reads flow's data from the data log file.
# param [in] directory - input directory containing the log file
# param [in] flow      - flow index
# returns timestamps of arrivals of the flow's packets, one-way delays of the flow's packets,
# sizes in bytes of the flow's packets, the flows's lost bytes number and total sent bytes number
# throws DataError
#
def load_data(directory, flow):
    filePath = os.path.join(directory, "{}-{:d}.{}".format(DATA, flow, LOG))

    try:
        with open(filePath, 'r') as file:
            _        = json.loads(next(file))
            loss     = json.loads(next(file))
            arrivals = json.loads(next(file))
            delays   = json.loads(next(file))
            sizes    = json.loads(next(file))

            return arrivals, delays, sizes, loss

    except IOError as error:
        raise DataError('Failed to read flow\'s data from the file %s:\n%s' % (filePath, error))


#
# Function reads arrival timestamps and delays of the flow's packets from the data log file.
# param [in] directory - input directory containing the log file
# param [in] flow      - flow index
# returns timestamps of arrivals of the flow's packets, one-way delays of the flow's packets
# throws DataError
#
def load_delays(directory, flow):
    filePath = os.path.join(directory, "{}-{:d}.{}".format(DATA, flow, LOG))

    try:
        with open(filePath, 'r') as file:
            _        = json.loads(next(file))
            _        = json.loads(next(file))
            arrivals = json.loads(next(file))
            delays   = json.loads(next(file))

            return arrivals, delays

    except IOError as error:
        raise DataError('Failed to read flow\'s delays from the file %s:\n%s' % (filePath, error))
