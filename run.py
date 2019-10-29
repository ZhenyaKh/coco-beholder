#!/usr/bin/env python

import sys
import time
import os
import argparse
import pwd

from variable_delay.src.argparse.help_formatter import BlankLinesHelpFormatter
from variable_delay.src.test.test import test
from variable_delay.src.metadata.metadata import compute_metadata, save_metadata, MetadataError
from variable_delay.src.layout.layout import parse_layout, save_default_layout, parse_time_str
from variable_delay.src.layout.layout import LayoutError
from variable_delay.src.processed_args.args_names import *

KIB_IN_MIB          = 1024
SUDO_USER           = 'SUDO_USER'
WORKING_DIR         = os.path.dirname(os.path.realpath(__file__))
DEFAULT_DIR_NAME    = 'dumps'
DEFAULT_DIR_PATH    = os.path.join(WORKING_DIR, DEFAULT_DIR_NAME)
DEFAULT_LAYOUT_NAME = 'layout.yml'
DEFAULT_LAYOUT_PATH = os.path.join(WORKING_DIR, DEFAULT_LAYOUT_NAME)
DEFAULT_QUEUE_SIZE  = 1000


#
# Custom Exception class for errors connected to processing of arguments
#
class ArgsError(Exception):
    pass


#
# Function adds arguments specifying sizes of transmit queues of the two routers in the dumbbell
# topology to argparse argument parser.
# param [in, out] parser - argparse argument parser
#
def add_queue_arguments(parser):
    parser.add_argument('-q1', '--first-queue', type=int, metavar='SIZE',
    help='Size of transmit queue of the left router\'s interface at the first end of the central '
         'link of the dumbbell topology, default is %d packets' % DEFAULT_QUEUE_SIZE)

    parser.add_argument('-q2', '--second-queue', type=int, metavar='SIZE',
    help='Size of transmit queue of the right router\'s interface at the second end of the central '
         'link of the dumbbell topology, default is %d packets' % DEFAULT_QUEUE_SIZE)

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
        raise ArgsError('Processing of argument "%s" failed:\n%s' % (argName, error))


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
            try:
                save_default_layout(layoutPath, runtime, rate)
            except LayoutError as error:
                raise ArgsError(error)

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
        raise ArgsError('--queues cannot be used together with --first-queue or --second-queue')

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

    parser.add_argument('-d', '--dir', default=DEFAULT_DIR_PATH, metavar='DIR',
    help='Output directory, default is "%s". Service file metadata.json containing parameters '
         'with which testing is actually performed is written there. For each flow, pcap-files, '
         'recorded at interfaces of the two hosts between which the flow runs, are written there '
         'named "<flow\'s starting #>-<scheme>-<sender/receiver>.pcap"' % DEFAULT_DIR_NAME)

    parser.add_argument('-p', '--pantheon', required=True, metavar='DIR',
    help='Pantheon [pantheon.stanford.edu] directory where congestion control schemes are searched')

    parser.add_argument('-l', '--layout', metavar='FILE',
    help='Input yaml-file defining groups of flows run in the dumbbell topology. Default is "%s" '
         'and during the first run of the script this file is created with example settings.'
         % DEFAULT_LAYOUT_NAME)

    parser.add_argument('-r', '--rate', default=100.0, type=float, metavar='MBITPS',
    help='Rate of the central link in Mbit/s, type is float, default value is 100.0. If you do not '
         'want to limit the rate just set it to zero: for qdisc netem, setting rate/delay of an '
         'interface to zero means the same as you leave the parameter unset.')

    parser.add_argument('-t', '--runtime', default=30, type=int, metavar='SEC',
    help='Runtime of testing in seconds (default 30)')

    parser.add_argument('-m', '--max-delay', default=int(1e8), type=int, metavar='USEC',
    help='Max delay and jitter fed to netem in microseconds (default is 100000000, i.e. 100 sec)')

    parser.add_argument('-s', '--seed', default=time.time(), type=float,
    help='Randomization seed to define if the delay at the central link is increased or decreased '
         'by step after  a subsequent delta time, if not specified is set to current Unix time. '
         'The parameter is useful if one wants to reproduce results of testing in which delay '
         'variability feature was used.')

    parser.add_argument('-b', '--buffer', default=2, type=int, metavar='MiB',
    help='Set the operating system capture buffer size to chosen number of MiB (1024 KiB), '
         'default is 2 MiB. The value is set as -B option for tcpdump recordings on all hosts.')

    add_queue_arguments(parser)


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

    output[RATE        ] = args.rate
    output[MAX_DELAY   ] = args.max_delay
    output[SEED        ] = args.seed
    output[BUFFER      ] = process_buffer_argument(args.buffer)
    output[FIRST_QUEUE ] = process_queue_argument (args.first_queue,  args.queues)
    output[SECOND_QUEUE] = process_queue_argument (args.second_queue, args.queues)
    output[LAYOUT_PATH ] = process_layout_argument(args.layout,       output[RUNTIME], output[RATE])

    output[BASE  ] = process_time_arg(BASE,   args.base,   output[MAX_DELAY])
    output[DELTA ] = process_time_arg(DELTA,  args.delta,  float('inf'))
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
    'flows: left-to-right or right-to-left, rate/delay/queue-size of the links belonging to '
    'the flows in the left half of the topology, rate/delay/queue-size of the links '
    'belonging to the flows in the right half of the topology. For the central link, user can '
    'define its rate, constant or VARIABLE DELAY with optional jitter, individual queue-size for '
    'each end of the central link. Qdisc netem is applied to interfaces of links to '
    'set rates, delays and queue-sizes of the links. For each link, the specified '
    'rate/delay/queue-size parameters are always installed at both ends of the link.')

    add_arguments(parser)

    args = parser.parse_args()

    return args


#
# Entry function
#
if __name__ == '__main__':
    args = parse_arguments()

    if os.geteuid() != 0:
        print("Script not started as root. Running sudo...")
        scriptArgs = ['sudo', sys.executable] + sys.argv + [os.environ]
        os.execlpe('sudo', *scriptArgs)

    user = os.getenv(SUDO_USER)
    os.seteuid(pwd.getpwnam(user).pw_uid) # drop root privileges

    try:
        args     = process_arguments(args)
        layout   = parse_layout(args[LAYOUT_PATH], args[RUNTIME], args[PANTHEON], args[MAX_DELAY])
        metadata = compute_metadata(args, layout)
        save_metadata(args[DIR], metadata)
    except ArgsError as error:
        print("Arguments processing ERROR:\n%s" % error)
        sys.exit(1)
    except LayoutError as error:
        print("Layout parsing ERROR:\n%s" % error)
        sys.exit(1)
    except MetadataError as error:
        print("Metadata ERROR:\n%s" % error)
        sys.exit(1)

    os.seteuid(0) # regain root privileges

    print("Testing:")
    test(user, args[DIR], args[PANTHEON])
    print("Done.")
