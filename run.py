#!/usr/bin/python 

import os
import getpass
import argparse
import yaml
import sys
import subprocess

CONFIG_PATH = 'src/config.yml'

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
        subprocess.call('sudo python test.py %s %s %s %s %s %s' % 
           (user, scheme, args.dir, args.pantheon, args.rate, args.runtime),
           shell=True)

    subprocess.call('sudo mn -c --verbosity=output', shell=True)
    print("Done.")


