#!/usr/bin/python 

import os
import getpass
import argparse
import yaml
import sys
import subprocess

CONFIG_PATH  = 'src/config.yml'
MAX_DELAY_US = int(1e8)

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
        return yaml.load(config)['schemes'].keys()


#        
# Function processes input arguments of the script
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(description=
    'The script runs tests and outputs pcap-files captured at senders and receivers to '
    'a specified directory.')

    parser.add_argument('--dir', default='data', help='output directory, default is "data"')

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

    args = parser.parse_args()

    args.dir = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(args.dir):
        os.makedirs(args.dir)

    args.pantheon = os.path.realpath(os.path.expanduser(args.pantheon))

    if not os.path.exists(args.pantheon):
        sys.exit('Pantheon directory %s does not exist' % args.pantheon)

    if args.runtime > 60 or args.runtime <= 0: # same values as in Pantheon testing
        sys.exit('Runtime cannot be non-positive or greater than 60 seconds')
 
    if not args.all and args.schemes is None:
        sys.exit('Must specify --all or --schemes')

    allSchemes = parse_config(args.pantheon)

    if args.all:
        args.schemes = allSchemes
    else:
        args.schemes = args.schemes.split()
        verify_schemes(args.schemes, allSchemes)

    args.base  = parse_time_str(args.base)
    args.delta = parse_time_str(args.delta)
    args.step  = parse_time_str(args.step)

    if args.delta == 0 or args.step == 0:
        sys.exit("Delta time and step cannot be zero.")

    return args


#
# Entry function
#
if __name__ == '__main__':
    args = parse_arguments()

    if os.geteuid()==0:
        sys.exit("Please, do not run as root. We need to learn your user name.")

    user = getpass.getuser()

    for scheme in args.schemes:
        subprocess.call('sudo mn -c --verbosity=output', shell=True)

        print("Testing %s..." % scheme)
        subprocess.call('sudo python test.py %s %s %s %s %s %s %s %s %s %s %s' %
           (user, scheme, args.dir,  args.pantheon, args.rate, args.runtime,
            MAX_DELAY_US, args.base, args.delta,    args.step, 'jitter'), shell=True)

    subprocess.call('sudo mn -c --verbosity=output', shell=True)
    print("Done.")


