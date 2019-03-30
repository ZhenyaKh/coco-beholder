#!/usr/bin/python
#
# The script fully relies on tshark -z <statistics> output format persistence
#

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import sys
import re
from subprocess import check_output, CalledProcessError
import numpy as np
import argparse

SENDER                 = 'sender'
SENDERS_FILE_NAME      = 'senders-throughputs.png'
RECEIVERS_FILE_NAME    = 'receivers-throughputs.png'
DURATION_LINE          = 4
BYTES_COLUMN           = -2
FRAMES_COLUMN          = -3
COLUMN_DELIMITER       = '|'
MIN_STATS_LINES_NUMBER = 15
FIRST_INTERVAL_LINE    = 12
LAST_INTERVAL_LINE     = -2

#
# Function plots summary of throughputs for all pcap-files
# param throughputs [in] - dictionary with algorithm names as keys and throughputs as values
# param imagePath   [in] - path where the plot should be saved
#
def plot_throughputs_summary(throughputs, imagePath):
    if len(throughputs) == 0:
        return

    print("\nGenerating summary file %s" % imagePath)

    algorithmNames    = []
    throughputsSorted = []
    for key, value in sorted(throughputs.iteritems(), key=lambda (k,v): (v,k)):
        algorithmNames.append(key)
        throughputsSorted.append(value)

    positions  = np.arange(len(algorithmNames))
    figure, ax = plt.subplots(figsize=(16, 9))

    ax.bar(positions, throughputsSorted)

    for index, value in enumerate(throughputsSorted):
        ax.text(index, value / 2, '%.2f' % value, fontweight='bold', horizontalalignment='center',
                                                                     verticalalignment  ='center')
    ax.set(ylabel='Throughput (Mbps)')
    ax.grid()
    plt.xticks(positions, algorithmNames)

    plt.tight_layout()
    figure.savefig(imagePath)
    plt.close(figure)


#
# Function plots throughput for one pcap-file
# param intervals        [in] - time intervals
# param bytesPerInterval [in] - number of bytes received/sent during each time interval
# param imagePath        [in] - path where the plot should be saved
#
def plot_throughput(intervals, bytesPerInterval, imagePath):
    figure, ax = plt.subplots(figsize=(16, 9))

    ax.plot(intervals, bytesPerInterval)

    ax.set(xlabel='Time (s)', ylabel='Throughput (Mbps)')
    ax.grid()
    plt.xticks(intervals)
    ax.set_ylim(ymin=0.0)

    plt.tight_layout()
    figure.savefig(imagePath)
    plt.close(figure)

#
# Function gathers statistics for .pcap file and outputs the statistics to *.data file
# param filePath [in] - Pcap-file path
# returns statistics for each pcap-file: intervals, mbitsPerInterval and totalThroughputMbps
#
def generate_stats(filePath):
    stats = check_output('tshark -nr %s -q -z io,stat,1,ip.src==10.0.0.2' % filePath, shell=True)

    duration            = 0.0
    size                = 0
    frames              = 0
    totalThroughputMbps = 0.0
    intervals           = []
    mbitsPerInterval    = []
    lines               = stats.split('\n')

    if len(lines) >= MIN_STATS_LINES_NUMBER:
        durationString   = re.search('Duration: (.*) secs', lines[DURATION_LINE]).group(1)
        duration         = float(durationString.replace(" ", "0")) # due to tshark output bug
        intervalLines    = lines[FIRST_INTERVAL_LINE:LAST_INTERVAL_LINE]

        for line in intervalLines:
            bytesPerInterval = float(line.split(COLUMN_DELIMITER)[BYTES_COLUMN])
            mbitsPerInterval.append(bytesPerInterval * 8 / 1000000)
            size   = size + bytesPerInterval
            frames = frames + float(line.split(COLUMN_DELIMITER)[FRAMES_COLUMN])

        totalThroughputMbps = ((size * 8 / duration) / 1000000) if (duration != 0.0) else 0.0
        # Intervals from tshark statistics: (n-1)<>n where n is from 1 to Dur
        intervals = list(range(0, len(mbitsPerInterval)))

    statsPath = re.sub('.pcap$', '.data', filePath)
    with open(statsPath, 'w') as statsFile:
        statsFile.write('Duration  : %f s\nFrames    : %d\nBytes     : %d\nThroughput: %f Mbps\n%s'
                     % (duration, frames, size, totalThroughputMbps, stats))

    return intervals, mbitsPerInterval, totalThroughputMbps


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

    filesList            = [f for f in os.listdir(args.dir) if f.endswith('.pcap')]
    sendersThroughputs   = {}
    receiversThroughputs = {}

    for fileBasename in filesList:
        filePath = os.path.join(args.dir, fileBasename)
        print("Processing %s" % filePath)

        try:
            intervals, mbitsPerInterval, totalThroughputMbps = generate_stats(filePath)
        except CalledProcessError as error:
            print(error)
            continue

        imagePath = re.sub('.pcap$', '.png', filePath)
        plot_throughput(intervals, mbitsPerInterval, imagePath)

        fileNameParsed   = re.search('^(.*)-(.*)\.pcap$', fileBasename)
        algorithmName    = fileNameParsed.group(1)
        senderOrReceiver = fileNameParsed.group(2)

        if senderOrReceiver == SENDER:
            sendersThroughputs  [algorithmName] = totalThroughputMbps
        else:
            receiversThroughputs[algorithmName] = totalThroughputMbps

    plot_throughputs_summary(sendersThroughputs,   os.path.join(args.dir, SENDERS_FILE_NAME))
    plot_throughputs_summary(receiversThroughputs, os.path.join(args.dir, RECEIVERS_FILE_NAME))


