#!/usr/bin/python

import os
import argparse
import json
import hashlib
import itertools
import numpy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker

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
UTF8          = 'utf-8'
DELAY_95TH    = 'delay-95th'
DELAY_50TH    = 'delay-50th'
DELAY_AVG     = 'delay-avg'
RATE_AVG      = 'rate-avg'
LOSS          = 'loss'


#
# Function gets packets' timestamps of departures from sender and one-way delays using sender's dump
# param [in] dumpPath            - the full path of sender's dump
# param [in] senderIP            - IP of sender
# param [in] baseTime            - base time to subtract from packets' timestamps of departures
# param [in, out] arrivals       - dictionary <packet hash, unix time of packet arrival to receiver>
# param [in] receiverSentBytes   - number of bytes sent from sender, recorded at receiver
# param [in] receiverSentPackets - number of packets sent from sender, recorded at receiver
# returns packets' timestamps of departures from sender, packets' one-way delays in ms,
# number of bytes/packets sent from sender, recorded at sender,
# number of bytes/packets sent from sender, recorded at receiver but not at sender
#
def analyse_sender_dump(dumpPath, senderIP, baseTime, arrivals, receiverSentBytes,
                                                                receiverSentPackets):
    fileSize = os.stat(dumpPath).st_size
    progress = Bar('sender   dump:', max=fileSize, suffix='%(percent).1f%% in %(elapsed)ds')

    departures,   delays         = [],                []
    bytes,        packets        = 0,                 0
    sentBytes,    sentPackets    = 0,                 0
    phantomBytes, phantomPackets = receiverSentBytes, receiverSentPackets

    with open(dumpPath, 'rb') as dump:
        for timestamp, packet in Reader(dump):
            size = len(packet)
            ip   = Ethernet(packet).data

            if ip.src == senderIP:
                digest = hashlib.sha1(str(ip.data) + str(ip.id)).hexdigest()

                if digest in arrivals:
                    departures.append(timestamp - baseTime)
                    delays.append((arrivals[digest] - timestamp) * 1000)

                    del arrivals[digest]
                    phantomBytes   -= size
                    phantomPackets -=1

                sentBytes   += size
                sentPackets += 1

            bytes   += size
            packets += 1
            progress.goto(bytes)

    progress.goto(fileSize)
    progress.finish()

    print("Total: %d pkts/%d bytes, from sender: %d pkts/%d bytes\n" % (packets,     bytes,
                                                                        sentPackets, sentBytes))

    return departures, delays, sentBytes, sentPackets, phantomBytes, phantomPackets


#
# Function gets dictionary <packet hash, unix time of packet arrival> from receiver's dump
# param [in] dumpPath   - the full path of receiver's dump
# param [in] senderIP   - IP of sender
# param [in] baseTime   - base time
# param [in] secPerSlot - slot time in seconds
# returns dictionary <packet hash, unix time of packet arrival to receiver>,
# number of bytes got by receiver per each slot time,
# number of bytes/packets sent from sender, recorded at receiver,
# timestamps of first arrivals to receivers, timestamps of last arrivals to receivers,
#
def analyse_receiver_dump(dumpPath, senderIP, baseTime, secPerSlot):
    arrivals     = {}
    bytesInSlots = []
    fileSize     = os.stat(dumpPath).st_size
    progress     = Bar('receiver dump:', max=fileSize, suffix='%(percent).1f%% in %(elapsed)ds')

    bytes,        packets     = 0,    0
    sentBytes,    sentPackets = 0,    0
    firstArrival, lastArrival = None, None

    with open(dumpPath, 'rb') as dump:
        for timestamp, packet in Reader(dump):
            size = len(packet)
            ip   = Ethernet(packet).data

            if ip.src == senderIP:
                digest = hashlib.sha1(str(ip.data) + str(ip.id)).hexdigest()

                if digest in arrivals:
                    print("ERROR: Duplicate sha1 digest of two packets was found!")
                    del arrivals[digest]
                else:
                    arrivals[digest] = timestamp

                sentBytes   += size
                sentPackets += 1
                slotId       = int((timestamp - baseTime) / secPerSlot)

                if slotId >= len(bytesInSlots):
                    bytesInSlots.extend([0] * (slotId - len(bytesInSlots)))
                    bytesInSlots.append(size)
                else:
                    bytesInSlots[slotId] += size

                if not firstArrival:
                    firstArrival = timestamp

                lastArrival = timestamp

            bytes   += size
            packets += 1
            progress.goto(bytes)

    progress.goto(fileSize)
    progress.finish()

    print("Total: %d pkts/%d bytes, from sender: %d pkts/%d bytes\n" % (packets,     bytes,
                                                                        sentPackets, sentBytes))

    return arrivals, bytesInSlots, sentBytes, sentPackets, firstArrival, lastArrival


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
# Function is used to make labels of flows have horizontal layout, rather than vertical (default)
# param [in] items - array of labels/handles should be supplied here
# param [in] ncol  - required number of labels per row
# returns labels/handles sorted in such a way that they will have horizontal layout
#
def flip(items, ncol):
    return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))


#
# Function gets values to plot for one flow: packets' timestamps of departures from sender,
# packets' one-way delays in ms, number of bytes got by receiver per each slot time
# param [in] scheme     - name of the scheme
# param [in] flow       - flow id
# param [in] directory  - directory with dumps
# param [in] baseTime   - base time
# param [in] secPerSlot - slot time in seconds
# returns packets' timestamps (base time subtracted) of departures from sender,
# packets' one-way delays in ms, number of bytes got by receiver per each slot time,
# timestamps of first arrivals to receivers, timestamps of last arrivals to receivers,
# number of bytes sent by senders but not recorded at receivers, number of all bytes sent by senders
#
def analyse_dumps(scheme, flow, directory, baseTime, secPerSlot):
    receiverDump = os.path.join(directory, '%s-receiver-%d.pcap' % (scheme, flow))
    senderDump   = os.path.join(directory, '%s-sender-%d.pcap'   % (scheme, flow))

    senderIP = get_sender_ip(receiverDump, senderDump)

    arrivals,          bytesInSlots,       \
    receiverSentBytes, receiverSentPackets,\
    firstArrival,      lastArrival = analyse_receiver_dump(receiverDump, senderIP,
                                                           baseTime,     secPerSlot)

    departures,      delays,            \
    senderSentBytes, senderSentPackets, \
    phantomsBytes,   phantomPackets = analyse_sender_dump(senderDump,        senderIP,
                                                          baseTime,          arrivals,
                                                          receiverSentBytes, receiverSentPackets)
    if phantomPackets != len(arrivals):
        sys.exit("insanity") # assert
    del arrivals

    allSentBytes    = senderSentBytes   + phantomsBytes
    allSentPackets  = senderSentPackets + phantomPackets

    lostSentBytes   = allSentBytes      - receiverSentBytes
    lostSentPackets = allSentPackets    - receiverSentPackets

    print((u"\u2665 Union of data from sender recorded on both sides: %d pkts/%d bytes"       %
          (allSentPackets, allSentBytes)).encode(UTF8))

    print((u"\u2666 Subset of \u2665 which was not recorded at sender    : %d pkts/%d bytes"  %
          (phantomPackets, phantomsBytes)).encode(UTF8))

    print((u"\u2663 Subset of \u2665 which was not recorded at receiver  : %d pkts/%d bytes"  %
          (lostSentPackets, lostSentBytes)).encode(UTF8))

    if allSentBytes != 0:
        print((u"\u2660 Loss (ratio of \u2663 bytes to \u2665 bytes)              : %.3f%%\n" %
             (float(lostSentBytes) / allSentBytes * 100)).encode(UTF8))

    return departures, delays, bytesInSlots, firstArrival,  lastArrival, \
                                             lostSentBytes, allSentBytes


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
# Function saves statistics for testing to log file
# param [in] stats           - statistics per each flow
# param [in] totalStats      - statistics over all flows together
# param [in] scheme          - name of the scheme
# param [in] flows           - number of flows
# param [in] outputDirectory - output directory for logs
#
def write_stats(stats, totalStats, scheme, flows, outputDirectory):
    statsFile = open(os.path.join(outputDirectory, "%s-stats.log" % scheme), "w")

    output = '-- Total of %d %s:\n' % (flows, 'flow' if flows == 1 else 'flows')

    if DELAY_AVG not in totalStats:
        output += 'per-packet one-way delay:                 no packets\n'
    else:
        output += 'average per-packet one-way delay:         %.3f ms\n'     % totalStats[DELAY_AVG ]
        output += 'median per-packet one-way delay:          %.3f ms\n'     % totalStats[DELAY_50TH]
        output += '95th percentile per-packet one-way delay: %.3f ms\n'     % totalStats[DELAY_95TH]

    if RATE_AVG not in totalStats:
        output += 'average throughput:                       no packets\n'
    else:
        output += 'average throughput:                       %.3f Mbit/s\n' % totalStats[RATE_AVG]

    if LOSS not in totalStats:
        output += 'loss:                                     no packets\n'
    else:
        output += 'loss:                                     %.3f%%\n'      % totalStats[LOSS]

    for flow in range(1, flows + 1):
        output  += '-- Flow %d:\n' % flow
        flowStat = stats[flow]

        if DELAY_AVG not in flowStat:
            output += 'per-packet one-way delay:                 no packets\n'
        else:
            output += 'average per-packet one-way delay:         %.3f ms\n' % flowStat[DELAY_AVG ]
            output += 'median per-packet one-way delay:          %.3f ms\n' % flowStat[DELAY_50TH]
            output += '95th percentile per-packet one-way delay: %.3f ms\n' % flowStat[DELAY_95TH]

        if RATE_AVG not in flowStat:
            output += 'average throughput:                       no packets\n'
        else:
            output += 'average throughput:                       %.3f Mbit/s\n' % flowStat[RATE_AVG]

        if LOSS not in flowStat:
            output += 'loss:                                     no packets\n'
        else:
            output += 'loss:                                     %.3f%%\n'      % flowStat[LOSS]

    statsFile.write(output)
    statsFile.close()


#
# Function computes statistics for testing
# param [in] delays        - packets' one-way delays in ms
# param [in] bytesInSlots  - number of bytes got by receivers per each slot time
# param [in] firstArrivals - timestamps of first arrivals to receivers
# param [in] lastArrivals  - timestamps of last arrivals to receivers
# param [in] lostSentBytes - number of bytes sent by senders but not recorded at receivers
# param [in] allSentBytes  - number of all bytes sent by senders
# param [in] flows         - number of flows
# returns statistics per each flow, total statistics over all flows together
#
def compute_stats(delays, bytesInSlots, firstArrivals, lastArrivals,
                                        lostSentBytes, allSentBytes, flows):
    allDelays         = []
    stats             = {}
    totalStats        = {}
    totalFirstArrival = None
    totalLastArrival  = None
    totalBitsNumber   = 0
    totalSentBytes    = 0
    totalLostBytes    = 0

    for flow in range(1, flows + 1):
        stats[flow] = {}

        if len(delays[flow]) != 0:
            stats[flow][DELAY_AVG ] = numpy.average(delays[flow])
            stats[flow][DELAY_50TH] = numpy.percentile(delays[flow], 50, interpolation='nearest')
            stats[flow][DELAY_95TH] = numpy.percentile(delays[flow], 95, interpolation='nearest')
            allDelays += delays[flow]

        if firstArrivals[flow] is not None:
            if totalFirstArrival is None or firstArrivals[flow] < totalFirstArrival:
                totalFirstArrival = firstArrivals[flow]

            if totalLastArrival is None or lastArrivals[flow] > totalLastArrival:
                totalLastArrival = lastArrivals[flow]

            bitsNumber            = numpy.sum(bytesInSlots[flow]) * 8
            flowDuration          = lastArrivals[flow] - firstArrivals[flow]
            stats[flow][RATE_AVG] = bitsNumber / (flowDuration * 1000000)
            totalBitsNumber      += bitsNumber

        if allSentBytes[flow] != 0:
            stats[flow][LOSS] = (float(lostSentBytes[flow]) / allSentBytes[flow]) * 100

        totalLostBytes += lostSentBytes[flow]
        totalSentBytes += allSentBytes [flow]

    if len(allDelays) != 0:
        totalStats[DELAY_AVG ] = numpy.average(allDelays)
        totalStats[DELAY_50TH] = numpy.percentile(allDelays, 50, interpolation='nearest')
        totalStats[DELAY_95TH] = numpy.percentile(allDelays, 95, interpolation='nearest')

    if totalFirstArrival is not None:
        totalDuration        = totalLastArrival - totalFirstArrival
        totalStats[RATE_AVG] = totalBitsNumber / (totalDuration * 1000000)

    if totalSentBytes != 0:
        totalStats[LOSS] = (float(totalLostBytes) / totalSentBytes) * 100

    return stats, totalStats


#
# Function generates png plot of throughput at receivers in Mbps
# param [in] bytesInSlots    - number of bytes got by receivers per each slot time
# param [in] secPerSlot      - slot time in seconds
# param [in] scheme          - name of the scheme
# param [in] flows           - number of flows
# param [in] runtime         - runtime of testing in seconds
# param [in] outputDirectory - output directory for plots
#
def plot_rate(bytesInSlots, secPerSlot, scheme, flows, runtime, outputDirectory):
    figure, ax = plt.subplots(figsize=(16, 9))

    for flow in range(1, flows + 1):
        flowBytesInSlots = bytesInSlots[flow]
        slotsNumber      = len(flowBytesInSlots)
        slots            = []
        rates            = []

        for slotId in range(0, slotsNumber):
            if len(slots) != 0 or flowBytesInSlots[slotId] != 0: # cut off front slots with zeroes
                slots.append(slotId * secPerSlot)
                rates.append((flowBytesInSlots[slotId] * 8) / (secPerSlot * 1000000))

        label = ('Flow %s (no packets)' % flow) if slotsNumber == 0 else ('Flow %s' % flow)
        ax.plot(slots, rates, label=label)

    ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation for both axes

    locator = plticker.MultipleLocator(base=1)  # enforce tick for each second on x axis
    ax.xaxis.set_major_locator(locator)

    ax.set_xlim(0, runtime)
    ax.set_xlabel('Time (s), interval %gs' % secPerSlot, fontsize=FONT_SIZE)
    ax.set_ylabel('Throughput (Mbit/s)', fontsize=FONT_SIZE)
    ax.set_title(scheme.upper(), fontsize=FONT_SIZE)
    ax.grid()

    handles, labels = ax.get_legend_handles_labels()
    legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels, LABELS_IN_ROW),
                       ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                       fontsize=FONT_SIZE, scatterpoints=1)

    ratePlotPath = os.path.join(outputDirectory, "%s-rate.png" % scheme)
    figure.savefig(ratePlotPath, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)
    plt.close(figure)


#
# Function generates png plot of per-packer one-way delay of traffic sent from senders to receivers
# param [in] departures      - packets' timestamps (base time subtracted) of departures from senders
# param [in] delays          - packets' one-way delays in ms
# param [in] scheme          - name of the scheme
# param [in] flows           - number of flows
# param [in] runtime         - runtime of testing in seconds
# param [in] outputDirectory - output directory for plots
#
def plot_delay(departures, delays, scheme, flows, runtime, outputDirectory):
    figure, ax = plt.subplots(figsize=(16, 9))

    for flow in range(1, flows + 1):
        flowDepartures = departures[flow]
        flowDelays     = delays    [flow]

        label = ('Flow %s (no packets)' % flow) if len(flowDepartures) == 0 else ('Flow %s' % flow)
        ax.scatter(flowDepartures, flowDelays, s=1, marker='.', label=label)

    ax.ticklabel_format(useOffset=False, style='plain') # turn off scientific notation for both axes

    locator = plticker.MultipleLocator(base=1) # enforce tick for each second on x axis
    ax.xaxis.set_major_locator(locator)

    ax.set_xlim(0, runtime)
    ax.set_xlabel('Time (s)', fontsize=FONT_SIZE)
    ax.set_ylabel('Per-packet one-way delay (ms)', fontsize=FONT_SIZE)
    ax.set_title(scheme.upper(), fontsize=FONT_SIZE)
    ax.grid()

    handles, labels = ax.get_legend_handles_labels()
    legend = ax.legend(flip(handles, LABELS_IN_ROW), flip(labels, LABELS_IN_ROW),
                       ncol=LABELS_IN_ROW, bbox_to_anchor=(0.5, -0.1), loc='upper center',
                       fontsize=FONT_SIZE, scatterpoints=1, markerscale=10, handletextpad=0)

    delayPlotPath = os.path.join(outputDirectory, "%s-delay.png" % scheme)
    figure.savefig(delayPlotPath, bbox_extra_artists=(legend,), bbox_inches='tight', pad_inches=0.2)
    plt.close(figure)


#
# Function gets values to plot and to generate statistics for all flows
# param [in] scheme     - name of the scheme
# param [in] flows      - number of flows
# param [in] directory  - directory with dumps
# param [in] secPerSlot - slot time in seconds
# returns packets' timestamps (base time subtracted) of departures from senders,
# packets' one-way delays in ms, number of bytes got by receivers per each slot time,
# timestamps of first arrivals to receivers, timestamps of last arrivals to receivers,
# number of bytes sent by senders but not recorded at receivers, number of all bytes sent by senders
#
def get_data(scheme, flows, directory, secPerSlot):
    baseTime = get_base_time(scheme, flows, directory)

    departures    = {}
    delays        = {}
    bytesInSlots  = {}
    firstArrivals = {}
    lastArrivals  = {}
    lostSentBytes = {}
    allSentBytes  = {}

    for flow in range(1, flows + 1):
        print("\033[1m%s scheme, flow %d:\033[0m\n" % (scheme, flow)) # bold font in terminal

        departures   [flow], \
        delays       [flow], \
        bytesInSlots [flow], \
        firstArrivals[flow], \
        lastArrivals [flow], \
        lostSentBytes[flow], \
        allSentBytes [flow] = analyse_dumps(scheme, flow, directory, baseTime, secPerSlot)

    return departures, delays, bytesInSlots, firstArrivals, lastArrivals, \
                                             lostSentBytes, allSentBytes


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

    parser.add_argument('-i', '--interval', default=0.5, type=float,
                        help='interval per which throughput is counted in seconds, default is 0.5')

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
        print("~~~%s~~~"   % ('~' * len(scheme)))
        print("|  %s  |"   % scheme.upper())
        print("~~~%s~~~\n" % ('~' * len(scheme)))

        departures,    \
        delays,        \
        bytesInSlots,  \
        firstArrivals, \
        lastArrivals,  \
        lostSentBytes, \
        allSentBytes = get_data(scheme, meta[FLOWS], args.dir, args.interval)

        plot_delay(departures, delays, scheme, meta[FLOWS], meta[RUNTIME], args.output_dir)

        plot_rate (bytesInSlots, args.interval, scheme, meta[FLOWS], meta[RUNTIME], args.output_dir)

        stats, \
        totalStats = compute_stats(delays, bytesInSlots, firstArrivals, lastArrivals,
                                                         lostSentBytes, allSentBytes, meta[FLOWS])

        write_stats(stats, totalStats, scheme, meta[FLOWS], args.output_dir)
