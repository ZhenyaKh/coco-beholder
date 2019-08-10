#!/usr/bin/env python

import os
import sys
import hashlib

from dpkt.pcap import Reader
from dpkt.ethernet import Ethernet

from variable_delay.src.metadata.metadata import load_metadata, save_metadata, MetadataError
from variable_delay.src.metadata.metadata_fields import RUNTIME, ALL_FLOWS, SORTED_LAYOUT
from variable_delay.src.layout.layout_fields import FLOWS, DIRECTION, SCHEME
from variable_delay.src.layout.layout import RIGHTWARD, compute_per_flow
from variable_delay.src.pantheon.pantheon_constants import RECEIVER, SENDER
from variable_delay.src.analyze.progress_bar import ProgressBar
from variable_delay.src.data.data import save_data, DataError
from variable_delay.src.data.data_fields import *

MS_IN_SEC = 1000
UTF8      = 'utf-8'
PYTHON3   = 3
PERCENTS  = 100.0


#
# Custom Exception class for errors connected to analysis of pcap-files
#
class AnalysisError(Exception):
    pass


#
# Class the instance of which allows to extract data from pcap-files produced during testing
#
class DumpAnalyzer(object):
    #
    # Constructor
    # param[in] inDir  - full path of input directory with dumps to analyse
    # param[in] outDir - full path of output directory to save data extracted from the dumps
    # throws MetadataError
    #
    def __init__(self, inDir, outDir):
        self.inDir  = inDir  # full path of input directory with dumps
        self.outDir = outDir # full path of output directory for extracted data

        self.metadata   = load_metadata(self.inDir) # testing metadata
        self.runtimeSec = self.metadata[RUNTIME  ]  # testing runtime
        self.flows      = self.metadata[ALL_FLOWS]  # total number of flows

        layout = self.metadata[SORTED_LAYOUT]
        self.directions = compute_per_flow(DIRECTION, layout) # per flow directions
        self.schemes    = compute_per_flow(SCHEME,    layout) # per flow scheme names

        self.senderDumps   = self.compute_dumps_paths(SENDER)   # per flow paths of sender dumps
        self.receiverDumps = self.compute_dumps_paths(RECEIVER) # per flow paths of receiver dumps

        self.baseTime = None # timestamp of the earliest packet of all the pcap-files

        self.departures = [{} for _ in range(self.flows)] # packets' timestamps of departures
        self.arrivals   = [[] for _ in range(self.flows)] # packets' timestamps of arrivals
        self.delays     = [[] for _ in range(self.flows)] # packets' one-way delays
        self.sizes      = [[] for _ in range(self.flows)] # packets' sizes in bytes

        self.senderSentBytes   = [0] * self.flows # bytes from sender recorded at sender
        self.senderSentPkts    = [0] * self.flows # packets from sender recorded at sender
        self.receiverSentBytes = [0] * self.flows # bytes from sender recorded at receiver
        self.receiverSentPkts  = [0] * self.flows # packets from sender recorded at receiver
        self.phantomBytes      = [0] * self.flows # bytes from sender recorded only at receiver
        self.phantomPkts       = [0] * self.flows # packets from sender recorded only at receiver
        self.allSentBytes      = [0] * self.flows # total bytes from sender recorded in both dumps
        self.allSentPkts       = [0] * self.flows # total packets from sender recorded in both dumps
        self.lostSentBytes     = [0] * self.flows # bytes from sender recorded only at sender
        self.lostSentPkts      = [0] * self.flows # packets from sender recorded only at sender


    #
    # Methods extracts data from pcap-files and saves it to the output directory
    # throws AnalysisError, MetadataError, DataError
    #
    def extract_data(self):
        if sys.version_info[0] == PYTHON3:
            print("WARNING: You use python3 but for python2 analysis of dumps is ~1.3x faster.")

        save_metadata(self.outDir, self.metadata)
        self.metadata.clear()

        self.baseTime = self.get_base_time ()

        for flow in range(0, self.flows):
            print("\n\033[1m%s scheme, flow %d:\033[0m\n" % (self.schemes[flow], flow + 1)) # bold

            senderIp = self.get_sender_ip(flow)
            self.analyse_sender_dump  (flow, senderIp)
            self.analyse_receiver_dump(flow, senderIp)
            self.compute_loss(flow)

            self.departures[flow].clear()

            print("\nSaving the data of the flow to the file...\n")
            self.save_flow_data(flow)
            print("==========================================")

            del self.delays  [flow][:] # Immediately frees memory only for python3. For python2 even
            del self.sizes   [flow][:] # calling gc.collect() directly does not help. The only found
            del self.arrivals[flow][:] # comment: https://stackoverflow.com/a/35013905/4781940


    #
    # Method generates array of per flow paths of sender/receiver dumps
    # param [in] role - sender or receiver
    # returns array of per flow paths of sender/receiver dumps
    #
    def compute_dumps_paths(self, role):
        paths = []

        for flow, scheme in enumerate(self.schemes, 1):
            paths.append(os.path.join(self.inDir, "{:d}-{}-{}.pcap".format(flow, scheme, role)))

        return paths


    #
    # Method gets the minimum of timestamps of the first packets of all dumps to serve as base time
    # throws AnalysisError
    # returns the base timestamp
    #
    def get_base_time(self):
        minBaseTime = None

        for flow in range(0, self.flows):
            for dumpPath in [self.senderDumps[flow], self.receiverDumps[flow]]:

                try:
                    with open(dumpPath, 'rb') as dumpFile:
                        reader = Reader(dumpFile)
                        try:
                            baseTime = next(iter(reader))[0]

                            if minBaseTime is None:
                                minBaseTime = baseTime
                            else:
                                minBaseTime = min(minBaseTime, baseTime)

                        except StopIteration:
                            pass
                except IOError as error:
                    raise AnalysisError("Failed to read dump %s:\n%s" % (dumpPath, error))

        return minBaseTime


    #
    # Method computes ip address of sender host
    # param [in] flow - flow index
    # throws AnalysisError
    # returns ip address of sender host
    #
    def get_sender_ip(self, flow):
        senderIp = None

        for dumpPath in [self.senderDumps[flow], self.receiverDumps[flow]]:
            try:
                with open(dumpPath, 'rb') as dumpFile:
                    reader = Reader(dumpFile)
                    try:
                        packet   = next(iter(reader))[1]
                        ip       = Ethernet(packet).data
                        leftIp   = min(ip.src, ip.dst)
                        rightIp  = max(ip.src, ip.dst)
                        senderIp = leftIp if self.directions[flow] == RIGHTWARD else rightIp
                        break # switch to the next flow

                    except StopIteration:
                        pass
            except IOError as error:
                raise AnalysisError("Failed to read dump %s:\n%s" % (dumpPath, error))

        return senderIp


    #
    # Method processes sender's dump
    # param [in] flow     - flow index
    # param [in] senderIp - ip address of sender of the flow
    # throws AnalysisError
    #
    def analyse_sender_dump(self, flow, senderIp):
        bytes    = 0
        packets  = 0
        progress = ProgressBar("sender   dump", os.stat(self.senderDumps[flow]).st_size)

        try:
            with open(self.senderDumps[flow], 'rb') as dump:
                for timestamp, packet in Reader(dump):
                    pass
                    size = len(packet)
                    ip   = Ethernet(packet).data

                    if ip.src == senderIp:
                        self.process_sender_sent_packet(flow, timestamp, ip)

                        self.senderSentBytes[flow] += size
                        self.senderSentPkts [flow] += 1

                    bytes   += size
                    packets += 1
                    progress.update(bytes)

        except IOError as error:
            raise AnalysisError("Failed to read dump %s:\n%s" % (self.senderDumps[flow], error))

        progress.finish()

        print("Total: %d pkts/%d bytes, from sender: %d pkts/%d bytes\n" %
             (packets, bytes, self.senderSentPkts[flow], self.senderSentBytes[flow]))


    #
    # Method processes receiver's dump
    # param [in] flow     - flow index
    # param [in] senderIp - ip address of sender of the flow
    # throws AnalysisError
    #
    def analyse_receiver_dump(self, flow, senderIp):
        bytes    = 0
        packets  = 0
        progress = ProgressBar("receiver dump", os.stat(self.senderDumps[flow]).st_size)

        try:
            with open(self.receiverDumps[flow], 'rb') as dump:
                for timestamp, packet in Reader(dump):
                    size = len(packet)
                    ip   = Ethernet(packet).data

                    if ip.src == senderIp:
                        self.process_receiver_sent_packet(flow, timestamp, size, ip)

                        self.receiverSentBytes[flow] += size
                        self.receiverSentPkts [flow] += 1

                    bytes   += size
                    packets += 1
                    progress.update(bytes)

        except IOError as error:
            raise AnalysisError("Failed to read dump %s:\n%s" % (self.receiverDumps[flow], error))

        progress.finish()

        print("Total: %d pkts/%d bytes, from sender: %d pkts/%d bytes\n" %
             (packets, bytes, self.receiverSentPkts[flow], self.receiverSentBytes[flow]))


    #
    # Method computes the number of bytes/packets sent by sender in total and the number of
    # bytes/packets sent by sender but not recorded at the receiver
    #
    def compute_loss(self, flow):
        self.allSentBytes[flow]  = self.senderSentBytes[flow] + self.phantomBytes[flow]
        self.allSentPkts [flow]  = self.senderSentPkts [flow] + self.phantomPkts [flow]

        self.lostSentBytes[flow] = self.allSentBytes[flow]    - self.receiverSentBytes[flow]
        self.lostSentPkts [flow] = self.allSentPkts [flow]    - self.receiverSentPkts [flow]

        assert self.lostSentPkts[flow] == len(self.departures[flow])

        print((u"\u2665 Union of data from sender recorded on both sides: %d pkts/%d bytes" %
               (self.allSentPkts [flow], self.allSentBytes [flow])))

        print((u"\u2666 Subset of \u2665 which was not recorded at sender    : %d pkts/%d bytes" %
               (self.phantomPkts [flow], self.phantomBytes [flow])))

        print((u"\u2663 Subset of \u2665 which was not recorded at receiver  : %d pkts/%d bytes" %
               (self.lostSentPkts[flow], self.lostSentBytes[flow])))

        if self.allSentBytes[flow] != 0:
            print((u"\u2660 Loss (ratio of \u2663 bytes to \u2665 bytes)              : %.3f%%" %
                   (float(self.lostSentBytes[flow]) / self.allSentBytes[flow] * PERCENTS)))


    #
    # Method writes flow data to a log file
    # param [in] flow - flow index
    # throws DataError
    #
    def save_flow_data(self, flow):
        loss = [self.lostSentBytes[flow], self.allSentBytes[flow]]

        save_data(self.outDir, flow, self.arrivals[flow], self.delays[flow], self.sizes[flow], loss)


    #
    # Method processes packet sent by sender and found in sender's dump
    # param [in] flow      - flow to which the packet belongs
    # param [in] timestamp - timestamp of the packet
    # param [in] ip        - raw ip payload of the packet
    #
    def process_sender_sent_packet(self, flow, timestamp, ip):
        digest = hashlib.sha1(str(ip.id).encode(UTF8) + bytes(ip.data)).hexdigest()

        if digest in self.departures[flow]:
            print("ERROR: Duplicate sha1 digest of two packets was found!")
            del self.departures[flow][digest]
        else:
            self.departures[flow][digest] = timestamp


    #
    # Method processes packet sent by sender and found in receiver's dump
    # param [in] flow      - flow to which the packet belongs
    # param [in] timestamp - timestamp of the packet
    # param [in] size      - size of packets in bytes
    # param [in] ip        - raw ip payload of the packet
    #
    def process_receiver_sent_packet(self, flow, timestamp, size, ip):
        digest = hashlib.sha1(str(ip.id).encode(UTF8) + bytes(ip.data)).hexdigest()

        if digest in self.departures[flow]:
            delay = (timestamp - self.departures[flow][digest]) * MS_IN_SEC

            self.delays[flow].  append(delay)
            self.arrivals[flow].append(timestamp - self.baseTime)
            self.sizes[flow].   append(size)

            del self.departures[flow][digest]
        else:
            self.phantomBytes[flow] += size
            self.phantomPkts [flow] += 1
