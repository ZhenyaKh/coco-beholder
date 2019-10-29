#!/usr/bin/env python

import os
import subprocess

import yaml

from variable_delay.src.pantheon.pantheon_constants import *
from variable_delay.src.layout.layout_fields import *

LEFTWARD           = '<-'
RIGHTWARD          = '->'
UTF8               = "utf-8"
DEFAULT_QUEUE_SIZE = 1000


#
# Custom Exception class for errors connected to parsing of layout
#
class LayoutError(Exception):
    pass


#
# Function generates array of per flow values of a chosen field of the layout.
# param [in] field  - layout field
# param [in] layout - the layout
# returns array of per flow values of the field of the layout
#
def compute_per_flow(field, layout):
    perFlowValues = []

    for entry in layout:
        perFlowValues.extend([entry[field]] * entry[FLOWS])

    return perFlowValues


#
# Function creates default layout.
# param [in] runtime - runtime of testing in seconds
# param [in] rate    - rate in Mbps of the central link of the dumbbell topology
# returns default layout
#
def create_default_layout(runtime, rate):
    layout = [{ SCHEME       : 'cubic',
                FLOWS        : 1,
                START        : 0,
                DIRECTION    : LEFTWARD,
                LEFT_RATE    : None,
                RIGHT_RATE   : None,
                LEFT_DELAY   : None,
                RIGHT_DELAY  : None,
                LEFT_QUEUES  : None,
                RIGHT_QUEUES : None },

              { SCHEME       : 'vegas',
                FLOWS        : 2,
                START        : int(runtime / 2),
                DIRECTION    : RIGHTWARD,
                LEFT_RATE    : rate,
                RIGHT_RATE   : int(rate),
                LEFT_DELAY   : '0us',
                LEFT_QUEUES  : DEFAULT_QUEUE_SIZE * 2,
                RIGHT_QUEUES : DEFAULT_QUEUE_SIZE * 3,
                RIGHT_DELAY  : '5ms' },

              { SCHEME       : 'cubic',
                FLOWS        : 1,
                START        : 0,
                DIRECTION    : RIGHTWARD
              }]

    return layout


#
# Function saves default layout yaml-file.
# param [in] layoutPath - path of the layout yaml-file
# param [in] runtime    - runtime of testing in seconds
# param [in] rate       - rate in Mbps of the central link of the dumbbell topology
# throws LayoutError
#
def save_default_layout(layoutPath, runtime, rate):
    defaultLayout = create_default_layout(runtime, rate)

    try:
        with open(layoutPath, 'w') as yamlFile:
            yamlFile.write(
                "# Delays/rates are optional: if lacking or null, they are set to 0us/0.0\n"
                "# and for netem, to set delay/rate to zero is same as to leave it unset.\n"
                "# Sizes of queues are optional: if lacking or null, they are set to %d.\n"
                % DEFAULT_QUEUE_SIZE)

            yaml.dump(defaultLayout, yamlFile, default_flow_style=False)
    except Exception as error:
        raise LayoutError("Failed to create default layout yaml-file %s:\n%s" % (layoutPath, error))


#
# Function parses time string in the formats: N (milliseconds assumed), Nus, Nms, Ns.
# param [in] timeString - time string
# param [in] maxDelayUs - maximum possible delay in microseconds
# throws ValueError
# returns time in microseconds
#
def parse_time_str(timeString, maxDelayUs):
    timeString = timeString.strip()

    try:
        if timeString.endswith("us"):
            time = int(float(timeString[:-2]))
        elif timeString.endswith("ms"):
            time = int(float(timeString[:-2]) * 1e3)
        elif timeString.endswith("s"):
            time = int(float(timeString[:-1]) * 1e6)
        else:
            time = int(float(timeString) * 1e3)
    except ValueError:
        raise ValueError('Invalid time "%s".' % timeString)

    if time < 0:
        raise ValueError('Invalid time "%s". Time should be non-negative.' % timeString)

    if time > maxDelayUs:
        raise ValueError('Invalid time "%s". Time should not be greater than %d us.' %
                        (timeString, maxDelayUs))

    return time


#
# Function parses queues-size of the left/right half of the dumbbell topology for flows of the item.
# param [in] item    - layout item
# param [in] index   - index of the layout item
# param [in] itemKey - key name of the item: "left-queues" or "right-queues"
# throws LayoutError
# returns queues-size in packets of the half of the dumbbell topology for the flows of the item
#
def parse_flows_queues(item, index, itemKey):
    queuesSize = item.get(itemKey)

    if queuesSize is None:
        queuesSize = DEFAULT_QUEUE_SIZE
    else:
        if not isinstance(queuesSize, int):
            raise LayoutError('%s in item #%d is "%s" but if present it should be integer, ' \
                              'measured in number of packets' % (itemKey, index, queuesSize))
        queuesSize = int(queuesSize)

    return queuesSize


#
# Function parses delay of the left/right half of the dumbbell topology for the flows of the item.
# param [in] item     - layout item
# param [in] index    - index of the layout item
# param [in] maxDelay - maximum possible delay in microseconds
# param [in] itemKey  - key name of the item: "left-delay" or "right-delay"
# throws LayoutError
# returns delay in microseconds of the half of the dumbbell topology for the flows of the item
#
def parse_flows_delay(item, index, maxDelay, itemKey):
    delay = item.get(itemKey)

    if delay is None:
        delay = 0
    else:
        try:
            delay = parse_time_str(str(delay), maxDelay)
        except ValueError as error:
            raise LayoutError('%s "%s" in item #%d failed to be parsed:\n%s' %
                             (itemKey, delay, index, error))
    return delay


#
# Function parses rate of the left/right half of the dumbbell topology for the flows of the item.
# param [in] item    - layout item
# param [in] index   - index of the layout item
# param [in] itemKey - key name of the item: "left-rate" or "right-rate"
# throws LayoutError
# returns rate in Mbps of the left/right half of the dumbbell topology for the flows of the item
#
def parse_flows_rate(item, index, itemKey):
    rate = item.get(itemKey)

    if rate is None:
        rate = float(0)
    else:
        if not isinstance(rate, (int, float)):
            raise LayoutError('%s in item #%d is "%s" but if present it should be ' \
                              'float or integer (unit is Mbps)' % (itemKey, index, rate))
        rate = float(rate)

    return rate


#
# Function parses direction of flows of the layout item.
# param [in] item  - layout item
# param [in] index - index of the layout item
# throws LayoutError
# returns processed direction of flows of the layout item
#
def parse_flows_direction(item, index):
    direction = item.get(DIRECTION)

    if direction not in [LEFTWARD, RIGHTWARD]:
        raise LayoutError('Direction in item #%d is "%s" but it should either "%s" or "%s"' %
                         (index, direction, LEFTWARD, RIGHTWARD))

    return direction


#
# Function parses second on which flows of the layout item should be started.
# param [in] item    - layout item
# param [in] index   - index of the layout item
# param [in] runtime - runtime of testing in seconds
# throws LayoutError
# returns second on which flows of the layout item should be started
#
def parse_item_flows_start(item, index, runtime):
    start = item.get(START)

    if not isinstance(start, int) or start < 0 or start >= runtime:
        raise LayoutError('Start in item #%d is "%s" but it should be integer from 0 to %d' %
                         (index, start, runtime - 1))

    return start


#
# Function parses number of flows of layout item.
# param [in] item  - layout item
# param [in] index - index of the layout item
# throws LayoutError
# returns processed number of flows of the layout item
#
def parse_item_flows_number(item, index):
    flows = item.get(FLOWS)

    if not isinstance(flows, int) or flows <= 0:
        raise LayoutError('Flows in item #%d is "%s" but it should be positive integer' %
                         (index, flows))

    return flows


#
# Function determines who runs first: the sender or the receiver of the scheme.
# param [in] scheme      - scheme name
# param [in] pantheonDir - path of Pantheon directory
# throws LayoutError
# returns who runs first: sender or receiver
#
def who_runs_first(scheme, pantheonDir):
    schemePath = os.path.join(pantheonDir, PANTHEON_WRAPPERS_PATH, "%s.py" % scheme)

    if not os.path.exists(schemePath):
        raise LayoutError('Path of scheme "%s" does not exist:\n%s' % (scheme, schemePath))

    runsFirst = subprocess.check_output([schemePath, PANTHEON_RUN_FIRST]).decode(UTF8).strip()

    if runsFirst != RECEIVER and runsFirst != SENDER:
        raise LayoutError('Scheme "%s" does not tell if "receiver" or "sender" runs first' % scheme)

    return runsFirst


#
# Function parses scheme of layout item.
# param [in] item       - layout item
# param [in] index      - index of the layout item
# param [in] allSchemes - list of names of all the schemes present in Pantheon collection
# throws LayoutError
# returns processed scheme of the layout item
#
def parse_item_scheme(item, index, allSchemes):
    scheme = item.get(SCHEME)

    if scheme not in allSchemes:
        raise LayoutError('Scheme "%s" in item #%d is not present in Pantheon collection' %
                         (scheme, index))

    return scheme


#
# Function loads layout yaml-file.
# param [in] layoutPath - path of the layout yaml-file
# throws LayoutError
# returns contents of the layout yaml-file
#
def load_layout_file(layoutPath):
    try:
        return yaml.safe_load(open(layoutPath, 'r'))
    except Exception as error:
        raise LayoutError("Failed to load layout yaml-file:\n%s" % error)


#
# Function loads Pantheon config file with schemes listed.
# param [in] pantheonDir - Pantheon directory path
# throws LayoutError
# returns list of schemes
#
def load_pantheon_config(pantheonDir):
    pantheonPath = os.path.join(pantheonDir, PANTHEON_CONFIG_PATH)

    try:
        with open(pantheonPath) as pantheonConfig:
            return yaml.safe_load(pantheonConfig)[PANTHEON_SCHEMES].keys()
    except Exception as error:
        raise LayoutError("Failed to load Pantheon configuration file:\n%s" % error)


#
# Function parses layout yaml-file.
# param [in] layoutPath  - path of the layout yaml-file
# param [in] runtime     - runtime of testing in seconds
# param [in] pantheonDir - path of Pantheon directory
# param [in] maxDelay    - maximum possible delay in microseconds
# throws LayoutError
# returns parsed layout
#
def parse_layout(layoutPath, runtime, pantheonDir, maxDelay):
    layout     = []
    allSchemes = load_pantheon_config(pantheonDir)
    itemsArray = load_layout_file    (layoutPath)

    if not isinstance(itemsArray, list) or len(itemsArray) == 0:
        raise LayoutError('Data in yaml-file should be non-empty array of dictionaries')

    for index, item in enumerate(itemsArray, start=1):
        if not isinstance(item, dict):
            raise LayoutError('Item #%d of yaml-file is not a dictionary but it must be' % index)

        entry = { }

        entry[SCHEME      ] = parse_item_scheme      (item, index, allSchemes)

        entry[RUNS_FIRST  ] = who_runs_first         (entry[SCHEME], pantheonDir)

        entry[FLOWS       ] = parse_item_flows_number(item, index)

        entry[START       ] = parse_item_flows_start (item, index, runtime)

        entry[DIRECTION   ] = parse_flows_direction  (item, index)

        entry[LEFT_RATE   ] = parse_flows_rate       (item, index, LEFT_RATE)
        entry[RIGHT_RATE  ] = parse_flows_rate       (item, index, RIGHT_RATE)

        entry[LEFT_DELAY  ] = parse_flows_delay      (item, index, maxDelay, LEFT_DELAY)
        entry[RIGHT_DELAY ] = parse_flows_delay      (item, index, maxDelay, RIGHT_DELAY)

        entry[LEFT_QUEUES ] = parse_flows_queues     (item, index, LEFT_QUEUES)
        entry[RIGHT_QUEUES] = parse_flows_queues     (item, index, RIGHT_QUEUES)

        layout.append(entry)

    return layout
