#!/usr/bin/python 

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
LEFT_QUEUE           = 'left-queue'
RIGHT_QUEUE          = 'right-queue'
DEFAULT_LAYOUT_PATH  = 'layout.yml'
LAYOUT_PATH          = 'layout-path'
LAYOUT               = 'layout'
BASE                 = 'base'
DELTA                = 'delta'
STEP                 = 'step'
JITTER               = 'jitter'
RATE                 = 'rate'
MAX_DELAY            = 'max-delay'
SEED                 = 'seed'
PANTHEON_CONFIG_PATH = 'src/config.yml'
SCHEMES              = 'schemes'
FLOWS                = 'flows'
RUNTIME              = 'runtime'
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


#
# Function saves default layout yaml-file
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
                LEFT_DELAY  : '0ms',
                RIGHT_DELAY : '0ms' },

              { SCHEME      : 'vegas',
                FLOWS       : 1,
                START       : runtime / 2,
                DIRECTION   : RIGHTWARD,
                LEFT_RATE   : rate,
                RIGHT_RATE  : rate,
                LEFT_DELAY  : '0ms',
                RIGHT_DELAY : '5000us' },

              { SCHEME      : 'cubic',
                FLOWS       : 1,
                START       : 0,
                DIRECTION   : RIGHTWARD,
                LEFT_DELAY  : '0ms',
                RIGHT_DELAY : '0ms' }]

    with open(layoutPath, 'w') as yamlFile:
        yaml.dump(layout, yamlFile, default_flow_style=False)


#
# Function parses delay of the left/right half of the dumbbell topology for the flows of the item.
# In case of error throws an exception.
# param [in] item    - layout item
# param [in] index   - index of the layout item
# param [in] itemKey - key name of the item: "left-delay" or "right-delay"
# returns delay of the left/right half of the dumbbell topology for the flows of the item
#
def parse_flows_delay(item, index, maxDelay, itemKey):
    delay = item.get(itemKey)

    if delay is not None:
        try:
            delay = parse_time_str(str(delay), maxDelay)
        except Exception as error:
            raise Exception('%s in item #%d is "%s" but its possible formats are ' \
                            'N (milliseconds assumed), Nus, Nms, Ns.\n%s' %
                            (itemKey, index, delay, error))
    return delay


#
# Function parses rate of the left/right half of the dumbbell topology for the flows of the item.
# In case of error throws an exception.
# param [in] item    - layout item
# param [in] index   - index of the layout item
# param [in] itemKey - key name of the item: "left-rate" or "right-rate"
# returns rate of the left/right half of the dumbbell topology for the flows of the item
#
def parse_flows_rate(item, index, itemKey):
    rate = item.get(itemKey)

    if rate is not None:
        if not isinstance(rate, (int, float)):
            raise Exception('%s in item #%d is "%s" but if present it should be ' \
                            'float or integer (unit is Mbps)' % (itemKey, index, rate))
        rate = float(rate)

    return rate


#
# Function parses direction of flows of the layout item.
# In case of error throws an exception.
# param [in] item  - layout item
# param [in] index - index of the layout item
# returns processed direction of flows of the layout item
#
def parse_flows_direction(item, index):
    direction = item.get(DIRECTION)

    if direction not in [LEFTWARD, RIGHTWARD]:
        raise Exception('Direction in item #%d is "%s" but it should either "%s" or "%s"' %
                        (index, direction, LEFTWARD, RIGHTWARD))

    return direction


#
# Function parses second on which flows of the layout item should be started.
# In case of error throws an exception.
# param [in] item    - layout item
# param [in] index   - index of the layout item
# param [in] runtime - runtime of testing in seconds
# returns processed start of flows of the layout item
#
def parse_item_flows_start(item, index, runtime):
    start = item.get(START)

    if not isinstance(start, int) or start < 0 or start >= runtime:
        raise Exception('Start in item #%d is "%s" but it should be integer from 0 to %d' %
                        (index, start, runtime - 1))

    return start


#
# Function parses number of flows of layout item.
# In case of error throws an exception.
# param [in] item  - layout item
# param [in] index - index of the layout item
# returns processed number of flows of the layout item
#
def parse_item_flows_number(item, index):
    flows = item.get(FLOWS)

    if not isinstance(flows, int) or flows <= 0:
        raise Exception('Flows in item #%d is "%s" but it should be positive integer' %
                       (index, flows))

    return flows


#
# Function determines who runs first: the sender or the receiver of the scheme.
# In case of error throws an exception.
# param [in] scheme      - scheme name
# param [in] pantheonDir - path of Pantheon directory
# returns who runs first: sender or receiver
#
def who_runs_first(scheme, pantheonDir):
    schemePath = os.path.join(pantheonDir, WRAPPERS_PATH, scheme + '.py')

    if not os.path.exists(schemePath):
        raise Exception('Path of scheme "%s" does not exist:\n%s' % (scheme, schemePath))

    runsFirst  = subprocess.check_output([schemePath, 'run_first']).strip()

    if runsFirst != RECEIVER and runsFirst != SENDER:
        raise Exception('Scheme "%s" does not tell if "receiver" or "sender" runs first' % scheme)

    return runsFirst


#
# Function parses scheme of layout item.
# In case of error throws an exception.
# param [in] item       - layout item
# param [in] index      - index of the layout item
# param [in] allSchemes - list of names of all the schemes present in Pantheon collection
# returns processed scheme of the layout item
#
def parse_item_scheme(item, index, allSchemes):
    scheme = item.get(SCHEME)

    if scheme not in allSchemes:
        raise Exception('Scheme "%s" in item #%d is not present in Pantheon collection' %
                        (scheme, index))

    return scheme


#
# Function processes Pantheon config file with schemes listed.
# In case of error throws an exception.
# param [in] pantheonDir - Pantheon directory path
# returns list of schemes
#
def parse_pantheon_config(pantheonDir):
    pantheonPath = os.path.join(pantheonDir, PANTHEON_CONFIG_PATH)

    if not os.path.exists(pantheonPath):
        raise Exception('Pantheon configuration file does not exist by path:\n%s' % pantheonPath)

    with open(pantheonPath) as pantheonConfig:
        return yaml.load(pantheonConfig)[SCHEMES].keys()


#
# Function parses time string in the formats: N (milliseconds assumed), Nus, Nms, Ns.
# In case of parsing errors the function throws exception.
# param [in] timeString - time string
# param [in] maxDelay   - maximum possible delay
# returns time in microseconds
#
def parse_time_str(timeString, maxDelay):
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
        raise Exception('Invalid time "%s".' % timeString)

    if time < 0:
        raise Exception('Invalid time "%s". Time should be non-negative.' % timeString)

    if time > maxDelay:
        raise Exception('Invalid time "%s". Time should be less than %d us.' %
                       (timeString, maxDelay))

    return time


#
# Function returns path of layout yaml-file. If the file does not exist it creates a default one.
# In case of processing errors the function throws exception.
# param [in] layoutArg - parsed argument with the path of the layout yaml-file
# param [in] runtime   - runtime of testing in seconds
# param [in] rate      - rate in Mbps of the central link of the dumbbell topology
# returns the path of the layout yaml-file
#
def process_layout_argument(layoutArg, runtime, rate):
    if layoutArg is not None:
        layoutPath = os.path.realpath(os.path.expanduser(args.layout))

        if not os.path.exists(layoutPath):
            raise Exception('Layout yaml-file %s does not exist' % layoutPath)
    else:
        layoutPath = os.path.realpath(os.path.expanduser(DEFAULT_LAYOUT_PATH))

        if not os.path.exists(layoutPath):
            save_default_layout(layoutPath, runtime, rate)

    return layoutPath


#
# Function returns the size of the transmit queue of a router depending on arguments passed by user.
# In case of processing errors the function throws exception.
# param [in] oneQueueArg   - parsed argument with the size of the queue of the router
# param [in] bothQueuesArg - parsed argument with the common size of the queues of both the routers
# returns the size of the transmit queue of the router
#
def process_queue_argument(oneQueueArg,  bothQueuesArg):
    if bothQueuesArg is not None and oneQueueArg is not None:
        raise Exception('--queues cannot be used together with --left-queue or --right-queue')

    if oneQueueArg is not None:
        queueSize = oneQueueArg
    elif bothQueuesArg is not None:
        queueSize = bothQueuesArg
    else:
        queueSize = DEFAULT_QUEUE_SIZE

    return queueSize


#
# Function adds positional arguments to argparse argument parser
# param [in, out] parser - argparse argument parser
#
def add_positional_arguments(parser):
    parser.add_argument('base', action="store",
                         help='Initial delay set both for sender and receiver in the formats: '\
                              'N (milliseconds assumed), Nus, Nms, Ns')

    parser.add_argument('delta', action="store",
                         help='Delay is changed each delta time, '\
                              'the formats for delta: N (milliseconds assumed), Nus, Nms, Ns')

    parser.add_argument('step', action="store",
                         help='Step by which delay is changed each delta time in these formats: '\
                              'N (milliseconds assumed), Nus, Nms, Ns. '\
                              'Delay will always lie in range [0us, --max-delay us].')

    parser.add_argument('jitter', action="store", nargs='?',
                        help='Jitter affecting the delay in the formats: ' \
                             'N (milliseconds assumed), Nus, Nms, Ns. ')


#
# Function adds optional arguments to argparse argument parser
# param [in, out] parser - argparse argument parser
#
def add_optional_arguments(parser):
    parser.add_argument('-d', '--dir', default='dumps', metavar='PATH',
                        help='output directory, default is "dumps"')

    parser.add_argument('-p', '--pantheon', required=True, metavar='PATH',
                        help='Pantheon directory where schemes will be searched')

    parser.add_argument('-l', '--layout', metavar='FILENAME',
                        help='yaml-file defining distribution of flows per schemes in the topology'\
                             ', default is "%s"' % DEFAULT_LAYOUT_PATH)

    parser.add_argument('-r', '--rate', default=100.0, type=float, metavar='MBITPS',
                        help='rate of the link in Mbit/s, type is float, default value is 100.0')

    parser.add_argument('-t', '--runtime', default=30, type=int, metavar='SEC',
                        help='runtime of testing in seconds (default 30)')

    parser.add_argument('-m', '--max-delay', default=int(1e8), type=int, metavar='USEC',
                        help='maximum per-link delay in us (default is 100000000, that is 100 sec)')

    parser.add_argument('-s', '--seed', default=time.time(), type=float,
                        help='randomization seed to define if delay is increased or decreased '\
                             'by step after a subsequent delta time, if  not specified is set '\
                             'to current Unix time')

    parser.add_argument('-q1', '--left-queue', type=int, metavar='SIZE',
                        help='Size of transmit queue of the left router of the dumbbell topology'\
                             ', default is %d packets' % DEFAULT_QUEUE_SIZE)

    parser.add_argument('-q2', '--right-queue', type=int, metavar='SIZE',
                        help='Size of transmit queue of the right router of the dumbbell topology'\
                             ', default is %d packets' % DEFAULT_QUEUE_SIZE)

    parser.add_argument('-q', '--queues', type=int, metavar='SIZE',
                        help='Size of transmit queues of both the routers of the dumbbell topology'\
                             ', same as -q1 N -q2 N, default is %d packets' % DEFAULT_QUEUE_SIZE)


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
# Function generates metadata using processed arguments and parsed layout and saves it to json-file
# param [in] processedArgs - processed arguments
# param [in] parsedLayout  - parsed layout
#
def save_metadata(processedArgs, parsedLayout):
    metadata =\
    {
        RATE        : processedArgs[RATE       ],
        RUNTIME     : processedArgs[RUNTIME    ],
        MAX_DELAY   : processedArgs[MAX_DELAY  ],
        SEED        : processedArgs[SEED       ],
        LEFT_QUEUE  : processedArgs[LEFT_QUEUE ],
        RIGHT_QUEUE : processedArgs[RIGHT_QUEUE],
        BASE        : processedArgs[BASE       ],
        DELTA       : processedArgs[DELTA      ],
        STEP        : processedArgs[STEP       ],
        JITTER      : processedArgs[JITTER     ],
        LAYOUT      : parsedLayout
    }

    metadataPath = os.path.join(processedArgs[DIR], METADATA_NAME)

    with open(metadataPath, 'w') as metadataFile:
        json.dump(metadata, metadataFile, sort_keys=True, indent=4, separators=(',', ': '))


#
# Function parses layout yaml-file.
# In case of parsing errors the function throws exception.
# param [in] layoutPath  - path of the layout yaml-file
# param [in] runtime     - runtime of testing in seconds
# param [in] pantheonDir - path of Pantheon directory
# param [in] maxDelay    - maximum possible delay
# returns parsed layout
#
def parse_layout(layoutPath, runtime, pantheonDir, maxDelay):
    layout     = []
    allSchemes = parse_pantheon_config(pantheonDir)
    itemsArray = yaml.load(open(layoutPath, 'r'))

    if not isinstance(itemsArray, list):
        raise Exception('Data in yaml-file is not array but it should be array of dictionaries')

    for index, item in enumerate(itemsArray, start=1):
        if not isinstance(item, dict):
            raise Exception('Item #%d of yaml-file is not dictionary but it should be' % index)

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
# In case of processing errors the function throws exception.
# param [in] args - arguments parsed by argparse parser
# returns processed arguments
#
def process_arguments(args):
    output = { }

    output[RUNTIME] = args.runtime

    if output[RUNTIME] > 60 or output[RUNTIME] <= 0:
        raise Exception('Runtime cannot be non-positive or greater than 60 seconds')

    output[DIR] = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(output[DIR]):
        os.makedirs(output[DIR])

    output[PANTHEON] = os.path.realpath(os.path.expanduser(args.pantheon))

    if not os.path.exists(output[PANTHEON]):
        raise Exception('Pantheon directory %s does not exist' % output[PANTHEON])

    output[RATE       ] = args.rate
    output[MAX_DELAY  ] = args.max_delay
    output[SEED       ] = args.seed
    output[LEFT_QUEUE ] = process_queue_argument (args.left_queue,  args.queues)
    output[RIGHT_QUEUE] = process_queue_argument (args.right_queue, args.queues)
    output[LAYOUT_PATH] = process_layout_argument(args.layout,      output[RUNTIME], output[RATE])

    output[BASE       ] = parse_time_str(args.base,   output[MAX_DELAY])
    output[DELTA      ] = parse_time_str(args.delta,  output[MAX_DELAY])
    output[STEP       ] = parse_time_str(args.step,   output[MAX_DELAY])
    output[JITTER     ] = parse_time_str(args.jitter, output[MAX_DELAY]) if args.jitter else 0

    if output[DELTA] < 10000:
        raise Exception('Delta time less than 10ms makes no sense, as tc qdisc change takes ~4ms.')

    return output


#
# Function parses input arguments of the program with argparse parser
# returns arguments of the program parsed by argparse parser
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script runs testing for congestion control schemes and outputs pcap-files '
    'captured at senders and receivers of the schemes to a specified directory.')

    add_optional_arguments(parser)

    add_positional_arguments(parser)

    args = parser.parse_args()

    return args


#
# Entry function
#
if __name__ == '__main__':
    if os.geteuid() == 0:
        sys.exit("Please, do not run as root. We need to learn your user name.")

    user = getpass.getuser()
    args = parse_arguments()

    try:
        args = process_arguments(args)
    except Exception as error:
        print("Arguments processing failed:\n%s" % error)
        sys.exit(1)

    try:
        layout = parse_layout(args[LAYOUT_PATH], args[RUNTIME], args[PANTHEON], args[MAX_DELAY])
    except Exception as error:
        print("Layout parsing failed:\n%s" % error)
        sys.exit(1)

    save_metadata(args, layout)

    subprocess.call(['sudo', 'mn', '-c', '--verbosity=output'])

    print("Testing...")

    subprocess.call(['sudo', 'python', 'test1.py', user, args[DIR], args[PANTHEON]])

    subprocess.call(['sudo', 'mn', '-c', '--verbosity=output'])

    print("Done.")
