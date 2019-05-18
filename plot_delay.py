#!/usr/bin/python

import os
import argparse
import json
import hashlib
import matplotlib.pyplot as plt

from dpkt.pcap import *
from dpkt.ethernet import *

FLOWS         = 'flows'
SCHEMES       = 'schemes'
METADATA_NAME = 'metadata.json'
SENDER        = 'sender'
RECEIVER      = 'receiver'

#
#
#
def get_base_time(scheme, flows, directory):
    minBaseTime = float('inf')

    # In reality the first dump in the cycle (scheme-sender-1.pcap) always has the min base time
    # but we check all the files just to be sure, as it can be done quickly.
    for flow in range(1, flows + 1):
        for role in [SENDER, RECEIVER]:
            dumpPath = os.path.join(directory, '%s-%s-%d.pcap' % (scheme, role, flow))

            with open(dumpPath, 'rb') as dumpFile:
                reader = Reader(dumpFile)

                try:
                    baseTime    = iter(reader).next()[0]
                    minBaseTime = min(minBaseTime, baseTime)
                except StopIteration:
                    pass

    return minBaseTime


#
#
#
def get_sender_ip(receiverDump, senderDump):
    senderIP = None

    for dumpPath in [receiverDump, senderDump]:
        with open(dumpPath, 'rb') as dumpFile:
            reader = Reader(dumpFile)

            try:
                packet   = iter(reader).next()[1]
                ip       = Ethernet(packet).data
                senderIP = max(ip.src, ip.dst)

                if senderIP:
                    break

            except StopIteration:
                pass

    return senderIP


#
#
#
def analyse_sender_dump(dumpPath, senderIP, baseTime, arrivals):
    departures = []
    delays     = []
    lost       = 0

    with open(dumpPath, 'rb') as dump:
        for timestamp, packet in Reader(dump):
            ip = Ethernet(packet).data

            if ip.src == senderIP:
                digest = hashlib.sha1(str(ip.data) + str(ip.id)).hexdigest()

                if digest in arrivals:
                    departures.append(timestamp - baseTime)
                    delays.append(arrivals[digest] - timestamp)
                    del arrivals[digest]
                else:
                    lost += 1

    return departures, delays, lost


#
#
#
def analyse_receiver_dump(dumpPath, senderIP):
    arrivals = {}

    with open(dumpPath, 'rb') as dump:
        for timestamp, packet in Reader(dump):
            ip = Ethernet(packet).data

            if ip.src == senderIP:
                digest = hashlib.sha1(str(ip.data) + str(ip.id)).hexdigest()

                if digest in arrivals:
                    print("ERROR: Duplicate sha1 digest of two packets was found!")
                    del arrivals[digest]
                else:
                    arrivals[digest] = timestamp

    return arrivals


#
#
#
def get_delays(scheme, flow, directory, baseTime):
    receiverDump = os.path.join(directory, '%s-receiver-%d.pcap' % (scheme, flow))
    senderDump   = os.path.join(directory, '%s-sender-%d.pcap'   % (scheme, flow))

    senderIP = get_sender_ip(receiverDump, senderDump)

    arrivals = analyse_receiver_dump(receiverDump, senderIP)

    departures, delays, lost = analyse_sender_dump(senderDump, senderIP, baseTime, arrivals)

    phantoms = len(arrivals)

    if phantoms != 0:
        print("WARNING: %d packets present at receiver but not at sender" % phantoms)
        del arrivals

    if lost != 0:
        print("WARNING: %d packets lost" % lost)

    return departures, delays


#
#
#
def plot_delay(scheme, flows, directory):
    baseTime = get_base_time(scheme, flows, directory)

    figure, ax = plt.subplots(figsize=(16, 9))

    for flow in range(1, flows + 1):
        print("%s scheme, flow %d:" % (scheme, flow))

        departures, delays = get_delays(scheme, flow, directory, baseTime)
        ax.plot(departures, [delay * 1000 for delay in delays])

    ax.grid()
    ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation for both axes
    ax.set(xlabel='Time (s)', ylabel='One-Way-Delay (ms)')
    plt.tight_layout()

    delayGraphPath = os.path.join(directory, "%s-delay.png" % scheme)
    figure.savefig(delayGraphPath)
    plt.close(figure)







#
# Function loads metadata of the testing
# param [in] directoryPath - path of the directory in which the metadata file is kept
# returns dictionary with metadata
#
def load_metadata(directoryPath):
    metadataPath = os.path.join(directoryPath, METADATA_NAME)

    with open(metadataPath) as metadataFile:
        return json.load(metadataFile)


#
# Function processes input arguments of the script
# returns list of input arguments of the script
#
def parse_arguments():
    parser = argparse.ArgumentParser(description=
    'The script creates statistics files and plots graphs for all pcap-files in the directory.')

    parser.add_argument('--dir', default='data', help=
    'Directory with input pcap-files. Stats and graphs will be output to it. Default is "data".')

    args = parser.parse_args()

    args.dir = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(args.dir):
        sys.exit('Directory %s does not exist' % args.dir)

    return args


#
# Entry function
#
if __name__ == '__main__':
    args = parse_arguments()

    meta = load_metadata(args.dir)

    for scheme in meta[SCHEMES]:
        plot_delay(scheme, meta[FLOWS], args.dir)

