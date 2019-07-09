#!/usr/bin/env python

import argparse
import sys
import os

SENDER              = 'sender'
RECEIVER            = 'receiver'
PCAP                = '.pcap'
JSON                = '.json'
PNG                 = '.png'
LOG                 = '.log'
WORKING_DIR         = os.path.dirname(os.path.realpath(__file__))
DEFAULT_DUMPS_PATH  = os.path.join(WORKING_DIR, 'dumps')
DEFAULT_GRAPHS_PATH = os.path.join(WORKING_DIR, 'graphs')


parser = argparse.ArgumentParser(description=
'The script cleans two directories with data. The script deletes only pcap/json/png/log files and '
'does not touch any subdirectories. If any of chosen data directories gets completely empty '
'the script also deletes the directory.')

parser.add_argument('-a', '--all', action='store_true',
                    help='delete all files in both directories, same as -dg')

parser.add_argument('-d', '--dump', '--dumps', action='store_true',
                    help='delete all files in directory with dumps')

parser.add_argument('-g', '--graph', '--graphs', action='store_true',
                    help='delete all files in directory with graphs')

parser.add_argument('-s', '--senders', '--sender', action='store_true',
                    help='among chosen files, delete files belonging exclusively to senders')

parser.add_argument('-r', '--receivers', '--receiver', action='store_true',
                    help='among chosen files, delete files belonging exclusively to receivers')

parser.add_argument('-m', '--mutual', action='store_true',
                    help='among chosen files, delete files common for senders and receivers')

parser.add_argument('-f1', '--folder1', default=DEFAULT_DUMPS_PATH,
                    help='directory with dumps to clean, default is "dumps"')

parser.add_argument('-f2', '--folder2', default=DEFAULT_GRAPHS_PATH,
                    help='directory with graphs to clean, default is "graphs"')

args = parser.parse_args()

if args.all and (args.dump or args.graph):
    sys.exit('Error: argument -a is mutually exclusive with argumnets -d, -g')

if not args.all and not args.dump and not args.graph:
    sys.exit('Error: argument -a or at least one of arguments -d, -g should be chosen')

directories = []

if args.all or args.dump:
    dumpsDirPath = os.path.realpath(os.path.expanduser(args.folder1))
    if os.path.exists(dumpsDirPath):
        directories.append(dumpsDirPath)
    else:
        sys.stderr.write('\nWARNING: Directory does not exist: %s\n\n' % dumpsDirPath)

if args.all or args.graph:
    graphsDirPath = os.path.realpath(os.path.expanduser(args.folder2))
    if os.path.exists(graphsDirPath):
        directories.append(graphsDirPath)
    else:
        sys.stderr.write('\nWARNING: Directory does not exist: %s\n\n' % graphsDirPath)

filesToDelete = []

for directory in directories:
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    for file in files:
        if not file.endswith(PCAP) and not file.endswith(JSON) and not file.endswith(PNG)\
                                                               and not file.endswith(LOG):
            continue

        if SENDER in file:
            if args.senders:
                filesToDelete.append(os.path.join(directory, file))
        elif RECEIVER in file:
            if args.receivers:
                filesToDelete.append(os.path.join(directory, file))
        else:
            if args.mutual:
                filesToDelete.append(os.path.join(directory, file))

        if not args.senders and not args.receivers and not args.mutual:
            filesToDelete.append(os.path.join(directory, file))

for file in filesToDelete:
    os.remove(file)

print("The following files have been deleted:")
print("======================================")
print("\n".join(filesToDelete))
print("======================================")

for directory in directories:
    if len(os.listdir(directory)) == 0:
        os.rmdir(directory)
        print("Directory has been deleted as completely empty: %s" % directory)