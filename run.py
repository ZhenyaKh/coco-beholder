#!/usr/bin/python 

import os
import getpass
import argparse
import yaml
import sys
import subprocess
import json

CONFIG_PATH   = 'src/config.yml'
MAX_DELAY_US  = int(1e8)
SCHEMES       = 'schemes'
FLOWS         = 'flows'
RUNTIME       = 'runtime'
INTERVAL      = 'interval'
METADATA_NAME = 'metadata.json'


#
# Function parses time string in the formats: N (milliseconds assumed), Nus, Nms, Ns
# param [in] timeString - time string
# returns time in microseconds
def parse_time_str(timeString):
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
        sys.exit('Invalid time %s.' % timeString)

    if time < 0:
        sys.exit('Invalid time %s. Time should be non-negative.' % timeString)

    if time > MAX_DELAY_US:
        sys.exit('Invalid time %s. Time should be less than %d us.' % (timeString, MAX_DELAY_US))

    return time


#        
# Function verifies that schemes queried by user are present in Pantheon config
# param [in] schemes    - schemes queried by user
# param [in] allSchemes - schemes present in Pantheon config
#
def verify_schemes(schemes, allSchemes):
    for scheme in schemes:
        if scheme not in allSchemes:
            sys.exit('%s is not a scheme included in Pantheon src/config.yml' % scheme)


#        
# Function processes Pantheon config file with schemes listed
# param [in] pantheonDir - Pantheon directory path
# returns list of schemes
#
def parse_config(pantheonDir):
    with open(os.path.join(pantheonDir, CONFIG_PATH)) as config:
        return yaml.load(config)[SCHEMES].keys()


#
# Custom HelpFormatter class
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
# Function processes input arguments of the script
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
    'The script runs tests and outputs pcap-files captured at sender and receiver to '
    'a specified directory.')

    parser.add_argument('-d', '--dir', default='data', help='output directory, default is "data"')

    parser.add_argument('-a', '--all', action='store_true',
                        help='test all schemes')

    parser.add_argument('-p', '--pantheon', required=True,
                        help='Pantheon directory where schemes will be searched')

    parser.add_argument('-s', '--schemes', metavar='"SCHEME1 SCHEME2..."',
                        help='test a space-separated list of schemes')

    parser.add_argument('-r', '--rate', default=100.0, type=float,
                        help='rate of the link in Mbit/s, type is float, default value is 100.0')

    parser.add_argument('-t', '--runtime', default=30, type=int,
                        help='runtime of each test in seconds (default 30)')

    parser.add_argument('-f', '--flows', type=int, default=1, help='number of flows (default 1)')

    parser.add_argument('-i', '--interval', type=int, default=0,
                        help='interval in seconds between two flows (default 0)')

    parser.add_argument('base', action="store",
                         help='Initial delay set both for sender and receiver in the formats: '\
                              'N (milliseconds assumed), Nus, Nms, Ns')

    parser.add_argument('delta', action="store",
                         help='Delay is changed each delta time, '\
                              'the formats for delta: N (milliseconds assumed), Nus, Nms, Ns')

    parser.add_argument('step', action="store",
                         help='Step by which delay is changed each delta time in these formats: '\
                              'N (milliseconds assumed), Nus, Nms, Ns. '\
                              'Delay will always lie in range [0us, %dus].' % MAX_DELAY_US)

    parser.add_argument('jitter', action="store", nargs='?',
                        help='Jitter affecting the delay in the formats: ' \
                             'N (milliseconds assumed), Nus, Nms, Ns. ')

    args = parser.parse_args()

    args.dir = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(args.dir):
        os.makedirs(args.dir)

    args.pantheon = os.path.realpath(os.path.expanduser(args.pantheon))

    if not os.path.exists(args.pantheon):
        sys.exit('Pantheon directory %s does not exist' % args.pantheon)

    if args.runtime > 60 or args.runtime <= 0:
        sys.exit('Runtime cannot be non-positive or greater than 60 seconds')

    if args.flows <= 0:
        sys.exit('The number of flows should be positive')

    if args.interval < 0:
        sys.exit('Interval cannot be negative')

    if (args.flows - 1) * args.interval >= args.runtime:
        sys.exit('Interval time between flows is too long to be fit in runtime')

    if not args.all and args.schemes is None:
        sys.exit('Must specify --all or --schemes')

    allSchemes = parse_config(args.pantheon)

    if args.all:
        args.schemes = allSchemes
    else:
        args.schemes = args.schemes.split()
        verify_schemes(args.schemes, allSchemes)

    args.base   = parse_time_str(args.base)
    args.delta  = parse_time_str(args.delta)
    args.step   = parse_time_str(args.step)
    args.jitter = parse_time_str(args.jitter) if args.jitter else 0

    if args.delta < 10000:
        sys.exit("Delta time less than 10ms makes no sense, as tc qdisc change takes around 4ms.")

    return args


#
# Entry function
#
if __name__ == '__main__':
    if os.geteuid() == 0:
        sys.exit("Please, do not run as root. We need to learn your user name.")

    user = getpass.getuser()
    args = parse_arguments()

    save_metadata(args)

    for scheme in args.schemes:
        subprocess.call('sudo mn -c --verbosity=output', shell=True)

        print("Testing %s..." % scheme)
        subprocess.call('sudo python test.py %s %s %s %s %s %s %s %s %s %s %s %s %s' %
           (user, scheme, args.dir,   args.pantheon, args.rate, args.runtime, MAX_DELAY_US,
                          args.base,  args.delta,    args.step, args.jitter,
                          args.flows, args.interval), shell=True)

    subprocess.call('sudo mn -c --verbosity=output', shell=True)
    print("Done.")
