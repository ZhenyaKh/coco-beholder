#!/usr/bin/python

import os
import argparse
import json
import hashlib
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
from sys import stderr
import itertools

from dpkt.pcap import *
from dpkt.ethernet import *
from progress.bar import FillingSquaresBar as Bar

FLOWS         = 'flows'
SCHEMES       = 'schemes'
RUNTIME       = 'runtime'
METADATA_NAME = 'metadata.json'
SENDER        = 'sender'
RECEIVER      = 'receiver'
LABELS_IN_ROW = 5
FONT_SIZE     = 12


#
# Function gets IP of sender
# param [in] receiverDump - the full path of receiver's dump
# param [in] senderDump   - the full path of sender's dump
# returns IP of sender
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
# Function gets packets' timestamps of departures from sender and one-way delays using sender's dump
# param [in]      dumpPath - the full path of sender's dump
# param [in]      senderIP - IP of sender
# param [in]      baseTime - base time to subtract from packets' timestamps of departures
# param [in, out] arrivals - dictionary <packet hash, unix timestamp of packet arrival to receiver>
# returns packets' timestamps of departures from sender and one-way delays, number of lost packets
#
def analyse_sender_dump(dumpPath, senderIP, baseTime, arrivals):
    lost     = 0
    fileSize = os.stat(dumpPath).st_size
    progress = Bar('sender   dump:', max=fileSize, suffix='%(percent).1f%% in %(elapsed)ds')

    departures, delays      = [], []
    bytes,      packets     = 0,  0
    sentBytes,  sentPackets = 0,  0

    with open(dumpPath, 'rb') as dump:
        for timestamp, packet in Reader(dump):
            size = len(packet)
            ip   = Ethernet(packet).data

            if ip.src == senderIP:
                digest = hashlib.sha1(str(ip.data) + str(ip.id)).hexdigest()

                if digest in arrivals:
                    departures.append(timestamp - baseTime)
                    delays.append(arrivals[digest] - timestamp)
                    del arrivals[digest]
                else:
                    lost += 1

                sentBytes   += size
                sentPackets += 1

            bytes   += size
            packets += 1
            progress.goto(bytes)

    progress.goto(fileSize)
    progress.finish()

    print("Total: %d pkts/%d b. Sent by sender: %d pkts/%d b." % (packets,     bytes,
                                                                  sentPackets, sentBytes))
    return departures, delays, lost


#
# Function gets dictionary <packet hash, unix timestamp of packet arrival> from receiver's dump
# param [in] dumpPath - the full path of receiver's dump
# param [in] senderIP - IP of sender
# returns dictionary <packet hash, unix timestamp of packet arrival to receiver>
#
def analyse_receiver_dump(dumpPath, senderIP):
    arrivals = {}
    fileSize = os.stat(dumpPath).st_size
    progress = Bar('receiver dump:', max=fileSize, suffix='%(percent).1f%% in %(elapsed)ds')

    bytes,     packets     = 0, 0
    sentBytes, sentPackets = 0, 0

    with open(dumpPath, 'rb') as dump:
        for timestamp, packet in Reader(dump):
            size = len(packet)
            ip   = Ethernet(packet).data

            if ip.src == senderIP:
                digest = hashlib.sha1(str(ip.data) + str(ip.id)).hexdigest()

                if digest in arrivals:
                    stderr.write("ERROR: Duplicate sha1 digest of two packets was found!\n")
                    del arrivals[digest]
                else:
                    arrivals[digest] = timestamp

                sentBytes   += size
                sentPackets += 1

            bytes   += size
            packets += 1
            progress.goto(bytes)

    progress.goto(fileSize)
    progress.finish()

    print("Total: %d pkts/%d b. Sent by sender: %d pkts/%d b." % (packets,     bytes,
                                                                  sentPackets, sentBytes))
    return arrivals


#
# Function is used to make labels of flows have horizontal layout, rather than vertical (default)
# param [in] items - array of labels/handles should be supplied here
# param [in] ncol  - required number of labels per row
# returns labels/handles sorted in such a way that they will have horizontal layout
#
def flip(items, ncol):
    return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))


#
# Function gets values to plot: packets' timestamps of departures from sender and one-way delays
# param [in] scheme    - name of the scheme
# param [in] flow      - flow id
# param [in] directory - directory with dumps
# param [in] baseTime  - base time
# returns packets' timestamps (base time subtracted) of departures from sender and one-way delays
#
def get_delays(scheme, flow, directory, baseTime):
    receiverDump = os.path.join(directory, '%s-receiver-%d.pcap' % (scheme, flow))
    senderDump   = os.path.join(directory, '%s-sender-%d.pcap'   % (scheme, flow))

    senderIP = get_sender_ip(receiverDump, senderDump)

    arrivals = analyse_receiver_dump(receiverDump, senderIP)

    departures, delays, lost = analyse_sender_dump(senderDump, senderIP, baseTime, arrivals)

    phantoms = len(arrivals)

    if phantoms != 0:
        stderr.write("WARNING: %d packets sent by sender are not recorded at sender\n" % phantoms)
        del arrivals

    if lost != 0:
        stderr.write("WARNING: %d packets sent by sender are not recorded at receiver\n" % lost)

    return departures, delays


#
# Function gets the minimum of timestamps of the first packets of all dumps to serve as base time
# param [in] scheme    - name of the scheme
# param [in] flows     - number of flows
# param [in] directory - directory with dumps
# returns base time
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
# Function generates png plot of per-packer one-way delay of traffic sent from senders to receivers
# param [in] scheme          - name of the scheme
# param [in] flows           - number of flows
# param [in] runtime         - runtime of testing in seconds
# param [in] directory       - directory with dumps
# param [in] outputDirectory - output directory for plots
#
def plot_delay(scheme, flows, runtime, directory, outputDirectory):
    baseTime = get_base_time(scheme, flows, directory)

    figure, ax = plt.subplots(figsize=(16, 9))

    for flow in range(1, flows + 1):
        print("%s scheme, flow %d:" % (scheme, flow))

        departures, delays = get_delays(scheme, flow, directory, baseTime)

        label = ('Flow %s (no packets)' % flow) if len(departures) == 0 else ('Flow %s' % flow)
        ax.scatter(departures, [i * 1000 for i in delays], s=1, marker='.', label=label)

    ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation for both axes

    locator = plticker.MultipleLocator(base=1) # enforce tick for each second on x axis
    ax.xaxis.set_major_locator(locator)

    ax.set_xlim(0, runtime)
    ax.set_xlabel('Time (s)', fontsize=FONT_SIZE)
    ax.set_ylabel('Per-packet one-way delay (ms)', fontsize=FONT_SIZE)
    ax.grid()

    handles, labels = ax.get_legend_handles_labels()
    legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels, LABELS_IN_ROW),
                       ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                       fontsize=FONT_SIZE, scatterpoints=1, markerscale=10, handletextpad=0)

    delayPlotPath = os.path.join(outputDirectory, "%s-delay.png" % scheme)
    figure.savefig(delayPlotPath, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)
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
    'The script generates graphs and stats for pcap-files captured during testing.')

    parser.add_argument('-d', '--dir', default='dumps',
                        help='directory with input pcap-files, default is "dumps"')

    parser.add_argument('-o', '--output-dir', default='graphs',
                        help='directory with output files, default is "graphs"')

    args = parser.parse_args()

    args.dir = os.path.realpath(os.path.expanduser(args.dir))

    if not os.path.exists(args.dir):
        sys.exit('Directory %s does not exist' % args.dir)

    args.output_dir = os.path.realpath(os.path.expanduser(args.output_dir))

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    return args


#
# Entry function
#
if __name__ == '__main__':
    args = parse_arguments()

    meta = load_metadata(args.dir)

    for scheme in meta[SCHEMES]:
        print("~~~%s~~~" % ('~' * len(scheme)))
        print("|  %s  |" % scheme.upper())
        print("~~~%s~~~" % ('~' * len(scheme)))

        plot_delay(scheme, meta[FLOWS], meta[RUNTIME], args.dir, args.output_dir)
