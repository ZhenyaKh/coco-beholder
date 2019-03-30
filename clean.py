#!/usr/bin/python

import argparse
import sys
import os.path
import os

parser = argparse.ArgumentParser(description='The script cleans data directory.')

parser.add_argument('-a', '--all', action='store_true',
                    help='delete pcap, graph and data files. Same as -gdp.')

parser.add_argument('-g', '--graph', '--graphs', action='store_true',
                    help='delete graph files')

parser.add_argument('-d', '--data', action='store_true',
                    help='delete statistics data files')

parser.add_argument('-p', '--pcap', '--pcaps', action='store_true',
                    help='delete pcap files')

parser.add_argument('-s', '--senders', '--sender', action='store_true',
                    help='among chosen files, delete only files of senders')

parser.add_argument('-r', '--receivers', '--receiver', action='store_true',
                    help='among chosed files, delete only files of receivers')

parser.add_argument('--dir', default='data',
                    help='directory with files to clean, default is "data"')

args = parser.parse_args()

if args.receivers and args.senders:
    sys.exit('Error: -s and -r arguments are mutually exclusive')

if args.all and (args.graph or args.data or args.pcap):
    sys.exit('Error: argument -a is mutually exclusive with argumnets -g, -d, -p')

if not args.all and not args.graph and not args.data and not args.pcap:
    sys.exit('Error: argument -a or at least one of arguments -g, -d, -p should be chosen')

dirAbsPath = os.path.realpath(os.path.expanduser(args.dir))
if not os.path.exists(dirAbsPath):
    sys.exit('Directory %s does not exist' % dirAbsPath)

files = [f for f in os.listdir(dirAbsPath) if os.path.isfile(os.path.join(dirAbsPath, f))]

if args.all:
    args.graph = True
    args.data  = True
    args.pcap  = True

filesToDelete = []

for file in files: 
    toDelete = False

    if   args.graph and file.endswith('.png') : toDelete = True 
    elif args.data  and file.endswith('.data'): toDelete = True
    elif args.pcap  and file.endswith('.pcap'): toDelete = True

    if args.senders and 'sender' not in file:
        toDelete = False

    if args.receivers and 'receiver' not in file:
        toDelete = False

    if toDelete:
        fileAbsPath = os.path.join(dirAbsPath, file)
        filesToDelete.append(fileAbsPath)
        os.remove(fileAbsPath)

print("The following files have been deleted:")
print("======================================")
print("\n".join(filesToDelete))
print("======================================")


