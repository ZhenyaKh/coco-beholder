#!/usr/bin/python 

import os
import getpass
import argparse
import yaml
import sys
import subprocess
import json
import time

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
DEFAULT_LAYOUT_PATH  = 'layout.yml'
SENDER               = 'sender'
RECEIVER             = 'receiver'
WRAPPERS_PATH        = 'src/wrappers'
RUNS_FIRST           = 'runs-first'
DEFAULT_QUEUE_SIZE   = 1000


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
# Function validates and adjusts positional arguments parsed by argparse argument parser
# param [in, out] args - arguments parsed by argparse argument parser
#
def process_positional_arguments(args):
    args.base   = parse_time_str(args.base,   args.max_delay)
    args.delta  = parse_time_str(args.delta,  args.max_delay)
    args.step   = parse_time_str(args.step,   args.max_delay)
    args.jitter = parse_time_str(args.jitter, args.max_delay) if args.jitter else 0

    if args.delta < 10000:
        raise Exception('Delta time less than 10ms makes no sense, as tc qdisc change takes ~4ms.')


#
# Function validates and adjusts optional arguments parsed by argparse argument parser
# param [in, out] args - arguments parsed by argparse argument parser
#
def process_optional_arguments(args):
    args.dir = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(args.dir):
        os.makedirs(args.dir)

    args.pantheon = os.path.realpath(os.path.expanduser(args.pantheon))

    if not os.path.exists(args.pantheon):
        raise Exception('Pantheon directory %s does not exist' % args.pantheon)

    if args.runtime > 60 or args.runtime <= 0:
        raise Exception('Runtime cannot be non-positive or greater than 60 seconds')

    if args.queues is not None and (args.left_queue is not None or args.right_queue is not None):
        raise Exception('--queues cannot be used together with --left-queue or --right-queue')

    if args.left_queue  is None: args.left_queue  = DEFAULT_QUEUE_SIZE
    if args.right_queue is None: args.right_queue = DEFAULT_QUEUE_SIZE

    if args.queues is not None:
        args.left_queue  = args.queues
        args.right_queue = args.queues

    if args.layout:
        args.layout = os.path.realpath(os.path.expanduser(args.layout))

        if not os.path.exists(args.layout):
            raise Exception('Layout yaml-file %s does not exist' % args.layout)
    else:
        args.layout = os.path.realpath(os.path.expanduser(DEFAULT_LAYOUT_PATH))

        if not os.path.exists(args.layout):
            save_default_layout(args.layout, args.runtime, args.rate)


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
                             ', default is 1000 packets')

    parser.add_argument('-q2', '--right-queue', type=int, metavar='SIZE',
                        help='Size of transmit queue of the right router of the dumbbell topology'\
                             ', default is 1000 packets')

    parser.add_argument('-q', '--queues', type=int, metavar='SIZE',
                        help='Size of transmit queues of both the routers of the dumbbell topology'\
                             ', same as -q1 N -q2 N, default is 1000 packets')


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
# Function saves metadata of the testing
# param [in] args - arguments with which the testing should be launched
#
def save_metadata(args):
    meta = {}

    meta[SCHEMES ] = args.schemes
    meta[FLOWS   ] = args.flows
    meta[RUNTIME ] = args.runtime
    meta[INTERVAL] = args.interval

    metadataPath = os.path.join(args.dir, METADATA_NAME)

    with open(metadataPath, 'w') as metadataFile:
        json.dump(meta, metadataFile, sort_keys=True, indent=4, separators=(',', ': '))


#
# Function parses layout yaml-file. In case of parsing errors the function throws exception.
# param [in] layoutPath  - path of the layout yaml-file
# param [in] allSchemes  - list of names of all the schemes present in Pantheon collection
# param [in] runtime     - runtime of testing in seconds
# param [in] pantheonDir - path of Pantheon directory
# param [in] maxDelay    - maximum possible delay
# returns processed layout
#
def parse_layout(layoutPath, allSchemes, runtime, pantheonDir, maxDelay):
    layout     = []
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
# Function processes Pantheon config file with schemes listed
# param [in] pantheonDir - Pantheon directory path
# returns list of schemes
#
def parse_pantheon_config(pantheonDir):
    with open(os.path.join(pantheonDir, PANTHEON_CONFIG_PATH)) as config:
        return yaml.load(config)[SCHEMES].keys()


#
# Function processes input arguments of the script
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script runs testing for congestion control schemes and outputs pcap-files '
    'captured at senders and receivers of the schemes to a specified directory.')

    add_optional_arguments(parser)

    add_positional_arguments(parser)

    args = parser.parse_args()

    process_optional_arguments(args)

    process_positional_arguments(args)

    return args


#
# Entry function
#
if __name__ == '__main__':
    if os.geteuid() == 0:
        sys.exit("Please, do not run as root. We need to learn your user name.")

    user = getpass.getuser()

    #try:
    args = parse_arguments()
    #except Exception as error:
    #    print("Arguments parsing failed:\n%s" % error)
    #    sys.exit(1)

    allSchemes = parse_pantheon_config(args.pantheon)

    try:
        layout = parse_layout(args.layout, allSchemes, args.runtime, args.pantheon, args.max_delay)
    except Exception as error:
        print("Layout parsing failed:\n%s" % error)
        sys.exit(1)

    print("LAYOUT\n")
    print(layout)

    sys.exit(1)
    #save_metadata(args)
    args.schemes = ['vegas']
    for scheme in args.schemes:
        subprocess.call('sudo mn -c --verbosity=output', shell=True)

        print("Testing %s..." % scheme)
        subprocess.call('sudo python test.py %s %s %s %s %s %s %s %s %s %s %s 1 0' %
           (user, scheme, args.dir,   args.pantheon, args.rate, args.runtime, args.max_delay,
                          args.base,  args.delta,    args.step, args.jitter,
                          ), shell=True)

    subprocess.call('sudo mn -c --verbosity=output', shell=True)
    print("Done.")
