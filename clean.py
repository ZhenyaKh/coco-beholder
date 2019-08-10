#!/usr/bin/env python

import argparse
import sys
import os

from variable_delay.src.argparse.help_formatter import BlankLinesHelpFormatter

SENDER                  = 'sender'
RECEIVER                = 'receiver'
PCAP                    = '.pcap'
JSON                    = '.json'
PNG                     = '.png'
LOG                     = '.log'
WORKING_DIR             = os.path.dirname(os.path.realpath(__file__))
DEFAULT_PCAPS_DIR_NAME  = 'dumps'
DEFAULT_DATA_DIR_NAME   = os.path.join('graphs', 'data')
DEFAULT_GRAPHS_DIR_NAME = 'graphs'
DEFAULT_PCAPS_PATH      = os.path.join(WORKING_DIR, DEFAULT_PCAPS_DIR_NAME)
DEFAULT_DATA_PATH       = os.path.join(WORKING_DIR, DEFAULT_DATA_DIR_NAME)
DEFAULT_GRAPHS_PATH     = os.path.join(WORKING_DIR, DEFAULT_GRAPHS_DIR_NAME)


parser = argparse.ArgumentParser(formatter_class=BlankLinesHelpFormatter, description=
'The script cleans three output directories. The script deletes only pcap/json/png/log files and '
'does not touch any subdirectories. If any of the chosen directories gets completely empty the '
'script also deletes the directory.')

parser.add_argument('-a', '--all', action='store_true',
                    help='delete all files in the three directories, same as -pdg')

parser.add_argument('-p', '--pcap', '--pcaps', action='store_true',
                    help='delete all files in directory with pcap-files')

parser.add_argument('-d', '--data', action='store_true',
                    help='delete all files in directory with data-files')

parser.add_argument('-g', '--graph', '--graphs', action='store_true',
                    help='delete all files in directory with graphs')

parser.add_argument('-s', '--senders', '--sender', action='store_true',
                    help='among chosen files, delete files belonging exclusively to senders')

parser.add_argument('-r', '--receivers', '--receiver', action='store_true',
                    help='among chosen files, delete files belonging exclusively to receivers')

parser.add_argument('-m', '--mutual', action='store_true',
                    help='among chosen files, delete files common for senders and receivers')

parser.add_argument('-f1', '--folder1', default=DEFAULT_PCAPS_PATH,
                    help='directory with pcap-files to clean, default is "{}"'.
                    format(DEFAULT_PCAPS_DIR_NAME))

parser.add_argument('-f2', '--folder2', default=DEFAULT_DATA_PATH,
                    help='directory with data-files to clean, default is "{}"'.
                    format(DEFAULT_DATA_DIR_NAME))

parser.add_argument('-f3', '--folder3', default=DEFAULT_GRAPHS_PATH,
                    help='directory with graphs to clean, default is "{}"'.
                    format(DEFAULT_GRAPHS_DIR_NAME))

args = parser.parse_args()

if args.all and (args.pcap or args.data or args.graph):
    sys.exit('Error: argument -a is mutually exclusive with arguments -p, -d, -g')

if not args.all and not args.pcap and not args.data and not args.graph:
    sys.exit('Error: argument -a or at least one of arguments -p, -d, -g should be chosen')

directories = []

if args.all or args.pcap:
    pcapsDirPath = os.path.realpath(os.path.expanduser(args.folder1))
    if os.path.exists(pcapsDirPath):
        directories.append(pcapsDirPath)
    else:
        sys.stderr.write('\nWARNING: Directory does not exist: %s\n\n' % pcapsDirPath)

if args.all or args.data:
    dataDirPath = os.path.realpath(os.path.expanduser(args.folder2))
    if os.path.exists(dataDirPath):
        directories.append(dataDirPath)
    else:
        sys.stderr.write('\nWARNING: Directory does not exist: %s\n\n' % dataDirPath)

if args.all or args.graph:
    graphsDirPath = os.path.realpath(os.path.expanduser(args.folder3))
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
