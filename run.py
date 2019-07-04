#!/usr/bin/env python

import os
import getpass
import argparse
import yaml
import sys
import subprocess
import json
import time

DIR                  = 'dir'
PANTHEON             = 'pantheon'
LEFT_QUEUE           = '_left-queue'
RIGHT_QUEUE          = '_right-queue'
DEFAULT_LAYOUT_PATH  = 'layout.yml'
LAYOUT_PATH          = 'layout-path'
SORTED_LAYOUT        = 'sorted-layout'
BASE                 = '_base'
DELTA                = '_delta'
STEP                 = '_step'
JITTER               = '_jitter'
RATE                 = '_rate'
MAX_DELAY            = '_max-delay'
SEED                 = '_seed'
BUFFER               = '_buffer'
PANTHEON_CONFIG_PATH = 'src/config.yml'
SCHEMES              = 'schemes'
FLOWS                = 'flows'
ALL_FLOWS            = '_all-flows'
RUNTIME              = '_runtime'
METADATA_NAME        = 'metadata.json'
SCHEME               = 'scheme'
START                = 'start'
DIRECTION            = 'direction'
LEFTWARD             = '<-'
RIGHTWARD            = '->'
LEFT_RATE            = 'left-rate'
RIGHT_RATE           = 'right-rate'
LEFT_DELAY           = 'left-delay'
RIGHT_DELAY          = 'right-delay'
SENDER               = 'sender'
RECEIVER             = 'receiver'
WRAPPERS_PATH        = 'src/wrappers'
RUNS_FIRST           = 'runs-first'
DEFAULT_QUEUE_SIZE   = 1000
KIB_IN_MIB           = 1024


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
        raise ValueError('Invalid time "%s". Time should be less than %d us.' %
                        (timeString, maxDelayUs))

    return time


#
# Function saves default layout yaml-file.
# param [in] layoutPath - path of the layout yaml-file
# param [in] runtime    - runtime of testing in seconds
# param [in] rate       - rate in Mbps of the central link of the dumbbell topology
#
def save_default_layout(layoutPath, runtime, rate):
    layout = [{ SCHEME      : 'cubic',
                FLOWS       : 1,
                START       : 0,
                DIRECTION   : LEFTWARD,
                LEFT_RATE   : None,
                RIGHT_RATE  : None,
                LEFT_DELAY  : None,
                RIGHT_DELAY : None },

              { SCHEME      : 'vegas',
                FLOWS       : 2,
                START       : runtime / 2,
                DIRECTION   : RIGHTWARD,
                LEFT_RATE   : rate,
                RIGHT_RATE  : int(rate),
                LEFT_DELAY  : '0us',
                RIGHT_DELAY : '5ms' },

              { SCHEME      : 'cubic',
                FLOWS       : 1,
                START       : 0,
                DIRECTION   : RIGHTWARD
              }]

    with open(layoutPath, 'w') as yamlFile:
        yamlFile.write("# Delays/rates are optional: if lacking or null, they are set to 0us/0.0\n"
                       "# and for netem, to set delay/rate to zero is same as to leave it unset.\n")

        yaml.dump(layout, yamlFile, default_flow_style=False)


#
# Function adds arguments specifying sizes of transmit queues of the two routers in the dumbbell
# topology to argparse argument parser.
# param [in, out] parser - argparse argument parser
#
def add_queue_arguemnts(parser):
    parser.add_argument('-q1', '--left-queue', type=int, metavar='SIZE',
    help='Size of transmit queue of the left router\'s interface at the end of the central link of '
         'the dumbbell topology, default is %d packets' % DEFAULT_QUEUE_SIZE)

    parser.add_argument('-q2', '--right-queue', type=int, metavar='SIZE',
    help='Size of transmit queue of the right router\'s interface at the end of the central link '
         'of the dumbbell topology, default is %d packets' % DEFAULT_QUEUE_SIZE)

    parser.add_argument('-q', '--queues', type=int, metavar='SIZE',
    help='Common size of transmit queues of both the interfaces at the ends of the central link of '
         'the dumbbell topology, same as -q1 N -q2 N, default is %d packets' % DEFAULT_QUEUE_SIZE)

#
# Function adds arguments specifying parameters of variable delay at the central link of the
# dumbbell topology to argparse argument parser.
# param [in, out] parser - argparse argument parser
#
def add_delay_arguments(parser):
    parser.add_argument('base', action="store",
    help='Initial delay set at both ends of the central link in the formats: N (milliseconds '
         'assumed), Nus, Nms, Ns')

    parser.add_argument('delta', action="store",
    help='The delay at both ends of the central link is changed each delta time, the formats for '
         'delta: N (milliseconds assumed), Nus, Nms, Ns. If you do not need variable delay and '
         'want the delay to be constant just set delta to a value greater than that of '
         '-t/--runtime.')

    parser.add_argument('step', action="store",
    help='Step by which the  delay at both ends of the central link is changed each delta time in '
         'these formats: N (milliseconds assumed), Nus, Nms, Ns. The delay will always lie in '
         'range [0us, --max-delay us].')

    parser.add_argument('jitter', action="store", nargs='?',
    help='Jitter affecting the delay at both ends of the central link in the formats: N '
         '(milliseconds assumed), Nus, Nms, Ns. The argument is optional.')


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
            raise LayoutError, LayoutError('%s "%s" in item #%d failed to be parsed:\n%s' %
                                          (itemKey, delay, index, error)), sys.exc_info()[2]
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
    schemePath = os.path.join(pantheonDir, WRAPPERS_PATH, "%s.py" % scheme)

    if not os.path.exists(schemePath):
        raise LayoutError('Path of scheme "%s" does not exist:\n%s' % (scheme, schemePath))

    runsFirst  = subprocess.check_output([schemePath, 'run_first']).strip()

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
        return yaml.load(open(layoutPath, 'r'))
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
            return yaml.load(pantheonConfig)[SCHEMES].keys()
    except Exception as error:
        raise LayoutError("Failed to load Pantheon configuration file:\n%s" % error)


#
# Function processes time argument.
# param [in] argName   - time argument name
# param [in] timeArg   - time argument value
# param [in] maxTimeUs - maximum possible input time value in microseconds
# throws ArgsError
# returns time in microseconds
#
def process_time_arg(argName, timeArg, maxTimeUs):
    try:
        return parse_time_str(timeArg, maxTimeUs)
    except ValueError as error:
        raise ArgsError, ArgsError('Processing of argument "%s" failed:\n%s' %
                                  (argName, error)), sys.exc_info()[2]


#
# Function returns path of layout yaml-file. If the file does not exist it creates a default one.
# param [in] layoutArg - parsed argument with the path of the layout yaml-file
# param [in] runtime   - runtime of testing in seconds
# param [in] rate      - rate in Mbps of the central link of the dumbbell topology
# throws ArgsError
# returns the path of the layout yaml-file
#
def process_layout_argument(layoutArg, runtime, rate):
    if layoutArg is not None:
        layoutPath = os.path.realpath(os.path.expanduser(args.layout))

        if not os.path.exists(layoutPath):
            raise ArgsError('Layout yaml-file %s does not exist' % layoutPath)
    else:
        layoutPath = os.path.realpath(os.path.expanduser(DEFAULT_LAYOUT_PATH))

        if not os.path.exists(layoutPath):
            save_default_layout(layoutPath, runtime, rate)

    return layoutPath


#
# Function returns the size of the transmit queue of a router depending on arguments passed by user.
# param [in] oneQueueArg   - parsed argument with the size of the queue of the router
# param [in] bothQueuesArg - parsed argument with the common size of the queues of both the routers
# throws ArgsError
# returns the size of the transmit queue of the router
#
def process_queue_argument(oneQueueArg,  bothQueuesArg):
    if bothQueuesArg is not None and oneQueueArg is not None:
        raise ArgsError('--queues cannot be used together with --left-queue or --right-queue')

    if oneQueueArg is not None:
        queueSize = oneQueueArg
    elif bothQueuesArg is not None:
        queueSize = bothQueuesArg
    else:
        queueSize = DEFAULT_QUEUE_SIZE

    return queueSize


#
# Function processes the operating system capture buffer size argument.
# param [in] bufferArg - parsed buffer size argument in MiB passed by user
# throws ArgsError
# returns the buffer size in KiB
#
def process_buffer_argument(bufferArg):
    if bufferArg <= 0:
        raise ArgsError('-b/--buffer must be positive')

    return bufferArg * KIB_IN_MIB


#
# Function adds arguments to argparse argument parser.
# param [in, out] parser - argparse argument parser
#
def add_arguments(parser):
    add_delay_arguments(parser)

    parser.add_argument('-d', '--dir', default='dumps', metavar='DIR',
    help='Output directory, default is "dumps". Service file metadata.json containing parameters '
         'with which testing is actually performed is written there. For each flow, pcap-files, '
         'recorded at interfaces of the two hosts between which the flow runs, are written there '
         'named "<flow\'s starting #>-<scheme>-<sender/receiver>.pcap"')

    parser.add_argument('-p', '--pantheon', required=True, metavar='DIR',
    help='Pantheon [pantheon.stanford.edu] directory where congestion control schemes are searched')

    parser.add_argument('-l', '--layout', metavar='FILE',
    help='Input yaml-file defining groups of flows run in the dumbbell topology. Default is "%s" '
         'and during the first run of the script this file is created with example settings.'
         % DEFAULT_LAYOUT_PATH)

    parser.add_argument('-r', '--rate', default=100.0, type=float, metavar='MBITPS',
    help='Rate of the central link in Mbit/s, type is float, default value is 100.0. If you do not '
         'want to limit the rate just set it to zero: for qdisc netem, setting rate/delay of an '
         'interface to zero means the same as you leave the parameter unset.')

    parser.add_argument('-t', '--runtime', default=30, type=int, metavar='SEC',
    help='Runtime of testing in seconds (default 30)')

    parser.add_argument('-m', '--max-delay', default=int(1e8), type=int, metavar='USEC',
    help='Maximum delay for any interface in microseconds (default is 100000000, that is 100 sec)')

    parser.add_argument('-s', '--seed', default=time.time(), type=float,
    help='Randomization seed to define if the delay at the central link is increased or decreased '
         'by step after  a subsequent delta time, if not specified is set to current Unix time. '
         'The parameter is useful if one wants to reproduce results of testing in which delay '
         'variability feature was used.')

    parser.add_argument('-b', '--buffer', default=2, type=int, metavar='MiB',
    help='Set the operating system capture buffer size to chosen number of MiB (1024 KiB), '
         'default is 2 MiB. The value is set as -B option for tcpdump recordings on all hosts.')

    add_queue_arguemnts(parser)


#
# Custom HelpFormatter class for argparse.ArgumentParser
#
class BlankLinesHelpFormatter (argparse.HelpFormatter):
    #
    # Function insert blank lines between entries of the help message of the program
    # param [in] self  - class instance
    # param [in] text  - text of an entry of the help message
    # param [in] width - width of the help message
    # returns array of lines of an entry of the help message ending with the blank line
    #
    def _split_lines(self, text, width):
        return super(BlankLinesHelpFormatter, self)._split_lines(text, width) + ['']


#
# Function generates metadata using processed arguments and parsed layout and saves it to json-file.
# param [in] processedArgs - processed arguments
# param [in] parsedLayout  - parsed layout
#
def save_metadata(processedArgs, parsedLayout):
    metadata =\
    {
        RATE          : processedArgs[RATE       ],
        RUNTIME       : processedArgs[RUNTIME    ],
        MAX_DELAY     : processedArgs[MAX_DELAY  ],
        SEED          : processedArgs[SEED       ],
        BUFFER        : processedArgs[BUFFER     ],
        LEFT_QUEUE    : processedArgs[LEFT_QUEUE ],
        RIGHT_QUEUE   : processedArgs[RIGHT_QUEUE],
        BASE          : processedArgs[BASE       ],
        DELTA         : processedArgs[DELTA      ],
        STEP          : processedArgs[STEP       ],
        JITTER        : processedArgs[JITTER     ],
        SORTED_LAYOUT : sorted(parsedLayout, key=lambda flow: flow[START]),
        ALL_FLOWS     : sum(entry[FLOWS] for entry in parsedLayout)
    }

    metadataPath = os.path.join(processedArgs[DIR], METADATA_NAME)

    with open(metadataPath, 'w') as metadataFile:
        json.dump(metadata, metadataFile, sort_keys=True, indent=4, separators=(',', ': '))


#
# Custom Exception class for errors connected to parsing of layout
#
class LayoutError(Exception):
    pass


#
# Custom Exception class for errors connected to processing of arguments
#
class ArgsError(Exception):
    pass


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

        entry[SCHEME     ] = parse_item_scheme      (item, index, allSchemes)

        entry[RUNS_FIRST ] = who_runs_first         (entry[SCHEME], pantheonDir)

        entry[FLOWS      ] = parse_item_flows_number(item, index)

        entry[START      ] = parse_item_flows_start (item, index, runtime)

        entry[DIRECTION  ] = parse_flows_direction  (item, index)

        entry[LEFT_RATE  ] = parse_flows_rate       (item, index, LEFT_RATE)

        entry[RIGHT_RATE ] = parse_flows_rate       (item, index, RIGHT_RATE)

        entry[LEFT_DELAY ] = parse_flows_delay      (item, index, maxDelay, LEFT_DELAY)

        entry[RIGHT_DELAY] = parse_flows_delay      (item, index, maxDelay, RIGHT_DELAY)

        layout.append(entry)

    return layout


#
# Function validates and adjusts arguments parsed by argparse parser.
# param [in] args - arguments parsed by argparse parser
# throws ArgsError
# returns processed arguments
#
def process_arguments(args):
    output = { }

    output[RUNTIME] = args.runtime

    if output[RUNTIME] > 60 or output[RUNTIME] <= 0:
        raise ArgsError('Runtime cannot be non-positive or greater than 60 seconds')

    output[DIR] = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(output[DIR]):
        os.makedirs(output[DIR])

    output[PANTHEON] = os.path.realpath(os.path.expanduser(args.pantheon))

    if not os.path.exists(output[PANTHEON]):
        raise ArgsError('Pantheon directory %s does not exist' % output[PANTHEON])

    output[RATE       ] = args.rate
    output[MAX_DELAY  ] = args.max_delay
    output[SEED       ] = args.seed
    output[BUFFER     ] = process_buffer_argument(args.buffer)
    output[LEFT_QUEUE ] = process_queue_argument (args.left_queue,  args.queues)
    output[RIGHT_QUEUE] = process_queue_argument (args.right_queue, args.queues)
    output[LAYOUT_PATH] = process_layout_argument(args.layout,      output[RUNTIME], output[RATE])

    output[BASE  ] = process_time_arg(BASE,   args.base,   output[MAX_DELAY])
    output[DELTA ] = process_time_arg(DELTA,  args.delta,  output[MAX_DELAY])
    output[STEP  ] = process_time_arg(STEP,   args.step,   output[MAX_DELAY])
    output[JITTER] = process_time_arg(JITTER, args.jitter, output[MAX_DELAY]) if args.jitter else 0

    if output[DELTA] < 10000:
        raise ArgsError('Delta time less than 10ms makes no sense, as tc qdisc change takes ~4ms.')

    return output


#
# Function parses input arguments of the program with argparse parser.
# returns arguments of the program parsed by argparse parser
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script tests congestion control schemes by running flows of different schemes in '
    'the dumbbell topology for runtime seconds. Each flow has a host in the left half '
    'and a host in the right half of the topology and the hosts exchange a scheme\'s '
    'traffic with one host being the sender and one being the receiver. There is the '
    'left router that interconnects all the hosts in the left half and the right router that '
    'interconnects all the hosts in the right half of the topology. All the flows share the common '
    'central link between the two routers. User can define how many flows of which schemes should '
    'be run by defining groups of flows. A group of flows is defined by a scheme name, number of '
    'flows, a second of runtime at which the group of flows should be started, direction of the '
    'flows: left-to-right or right-to-left, rate and delay of the links belonging to the flows in '
    'the left half of the topology, rate and delay or the links belonging to the flows in the '
    'right half of the topology. For the central link, user can define its rate, constant or '
    'VARIABLE DELAY with optional jitter, sizes of transmit queues of the routers at the ends of '
    'the central link. Qdisc netem is applied to interfaces of links to set rates, delays and '
    'queue sizes of the links. For each link, the specified rate/delay/queue parameters are always '
    'installed at both ends of the link.')

    add_arguments(parser)

    args = parser.parse_args()

    return args


#
# Entry function
#
if __name__ == '__main__':
    try:
        if os.geteuid() == 0:
            sys.exit("Please, do not run as root. We need to learn your user name.")

        user = getpass.getuser()
        args = parse_arguments()

        try:
            args   = process_arguments(args)
            layout = parse_layout(args[LAYOUT_PATH], args[RUNTIME], args[PANTHEON], args[MAX_DELAY])

        except ArgsError as error:
            print("Arguments processing failed:\n%s" % error)
            sys.exit(1)
        except LayoutError as error:
            print("Layout parsing failed:\n%s" % error)
            sys.exit(1)

        save_metadata(args, layout)

        subprocess.call(['sudo', 'mn', '-c', '--verbosity=output'])

        print("Testing:")

        subprocess.call(['sudo', 'python', 'test.py', user, args[DIR], args[PANTHEON]])

        subprocess.call(['sudo', 'mn', '-c', '--verbosity=output'])

        print("Done.")

    except KeyboardInterrupt:
        print("KeyboardInterrupt was caught")
