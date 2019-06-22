#!/usr/bin/python

import sys
import os
import json
import random
import ipaddress
import subprocess
from subprocess import PIPE
from time import sleep
import time
import signal
import threading
from multiprocessing import Pool, cpu_count
import re

from mininet.net import Mininet
from mininet.net import CLI

USER                = 1
DIR                 = 2
PANTHEON            = 3
METADATA_NAME       = 'metadata.json'
LEFT_QUEUE          = '_left-queue'
RIGHT_QUEUE         = '_right-queue'
SORTED_LAYOUT       = 'sorted-layout'
BASE                = '_base'
DELTA               = '_delta'
STEP                = '_step'
JITTER              = '_jitter'
RATE                = '_rate'
MAX_DELAY           = '_max-delay'
SEED                = '_seed'
BUFFER              = '_buffer'
RUNTIME             = '_runtime'
FLOWS               = 'flows'
ALL_FLOWS           = '_all-flows'
SCHEME              = 'scheme'
LEFT_RATE           = 'left-rate'
RIGHT_RATE          = 'right-rate'
LEFT_DELAY          = 'left-delay'
RIGHT_DELAY         = 'right-delay'
DIRECTION           = 'direction'
START               = 'start'
RUNS_FIRST          = 'runs-first'
WRAPPERS_PATH       = 'src/wrappers'
SENDER              = 'sender'
RECEIVER            = 'receiver'
SUPERNET_SIZE       = 16
SUBNET_SIZE         = 2
SUPERNET_ADDRESS    = u'11.0.0.0/%d' % (32-SUPERNET_SIZE)
SUBNET_PREFIX       = 32 - SUBNET_SIZE
LEFT_HOSTS_LITERAL  = 'a'
RIGHT_HOSTS_LITERAL = 'b'
LEFT_ROUTER_NAME    = 'r1'
RIGHT_ROUTER_NAME   = 'r2'
USEC_PER_SEC        = int(1e6)
INCREASE            = 1
DECREASE            = -1
EXIT_SUCCESS        = 0
EXIT_FAILURE        = 1
SUCCESS_MESSAGE     = "SUCCESS"
FAILURE_MESSAGE     = "FAILURE"
DEFAULT_QUEUE_SIZE  = 1000
LEFTWARD            = '<-'
RIGHTWARD           = '->'
PORT                = 50000
SECOND              = 1.0
TIMEOUT_SEC         = 5.0


#
# Custom Exception class for errors connected to actual testing
#
class TestError(Exception):
    pass


#
# Custom Exception class for errors connected to processing of metadata containing testing's input
#
class MetadataError(Exception):
    pass


globalClients    = [] # Global array of client hosts               -- for multiprocessing map
globalClientCmds = [] # Global array of commands to launch clients -- for multiprocessing map


#
# Global function which launches flow's client -- for multiprocessing map
#
def start_client(flowId):
    print(flowId)
    x = globalClients[flowId].popen(globalClientCmds[flowId])
    print("%f" % time.time())
    return x


#
# Class the instance of which allows to perform the testing
#
class Test(object):
    #
    # Constructor
    # param[in] user     - name of user who runs the testing
    # param[in] dir      - full path of directory with metadata to which dumps will be saved
    # param[in] pantheon - full path of Pantheon directory
    # throws MetadataError
    #
    def __init__(self, user, dir, pantheon):
        self.user      = user              # name of user who runs the testing
        self.dir       = dir               # full path of output directory
        self.pantheon  = pantheon          # full path to Pantheon directory

        metadata = self.load_metadata()
        self.baseUs         = metadata[BASE       ] # initial netem delay at central links
        self.deltaUs        = metadata[DELTA      ] # time period with which to change netem delay
        self.stepUs         = metadata[STEP       ] # step to change netem delay at central link
        self.jitterUs       = metadata[JITTER     ] # netem delay jitter at central link
        self.seed           = metadata[SEED       ] # randomization seed for delay variability
        self.bufferKiB      = metadata[BUFFER     ] # capture buffer size set for tcpdump
        self.runtimeSec     = metadata[RUNTIME    ] # testing runtime
        self.rateMbps       = metadata[RATE       ] # netem rate at central link
        self.maxDelayUs     = metadata[MAX_DELAY  ] # max netem delay in us allowed to be set
        self.leftQueuePkts  = metadata[LEFT_QUEUE ] # size of transmit queue of left router
        self.rightQueuePkts = metadata[RIGHT_QUEUE] # size of transmit queue of right router
        self.flows          = metadata[ALL_FLOWS  ] # total number of flows

        layout = self.compute_per_flow_layout(metadata[SORTED_LAYOUT])
        self.directions     = [ flow[DIRECTION  ] for flow in layout ] # per flow directions
        self.leftDelaysUs   = [ flow[LEFT_DELAY ] for flow in layout ] # per flow left delays
        self.rightDelaysUs  = [ flow[RIGHT_DELAY] for flow in layout ] # per flow right delays
        self.leftRatesMbps  = [ flow[LEFT_RATE  ] for flow in layout ] # per flow left rates
        self.rightRatesMbps = [ flow[RIGHT_RATE ] for flow in layout ] # per flow right rates
        self.runsFirst      = [ flow[RUNS_FIRST ] for flow in layout ] # per flow who runs first
        self.schemes        = [ flow[SCHEME     ] for flow in layout ] # per flow scheme names
        self.schemePaths    = self.compute_schemes_paths()             # schemes' paths

        self.network            = None # Mininet network
        self.leftRouter         = None # router interconnecting left hosts
        self.rightRouter        = None # router interconnecting right hosts
        self.leftHosts          = None # hosts at left half of the dumbbell topology
        self.rightHosts         = None # hosts at right half of the dumbbell topology
        self.leftNetemCmd       = None # template of netem cmd for central link -- for left router
        self.rightNetemCmd      = None # template of netem cmd for central link -- for right router

        self.senderDumpPopens   = []   # per flow tcpdump processes recording at the flow's sender
        self.receiverDumpPopens = []   # per flow tcpdump processes recording at the flow's receiver
        self.serverPopens       = []   # per flow processes of launched servers
        self.clientPopens       = []   # per flow processes of launched clients

        # arrays of delta times and of corresponding delays -- to variate central link netem delay
        self.deltasArraySec,     self.delaysArrayUs        = self.compute_delay_steps()
        # per flow link to container keeping sender/receiver processes
        self.senderPopenHolders, self.receiverPopenHolders = self.compute_popen_holders()

        self.startsSchedule = self.compute_starts_schedule(layout) # schedule of starting flows
        self.startEvent     = threading.Event()                    # sync with thread starting flows
        self.clients        = globalClients    # per flow client hosts
        self.clientCmds     = globalClientCmds # per flow commands to launch clients
        self.pool           = None             # pool of processes launching clients


    #
    # Method runs actual testing
    # throws TestError
    #
    def test(self):
        try:
            random.seed(self.seed)
            print("Total number of flows is %d" % self.flows)
            print("Flows have been sorted by their start")

            print("Creating the dumbbell topology...")
            self.build_dumbbell_network()
            print("Setting schemes up after reboot...")
            self.setup_schemes_after_reboot()
            print("Setting rates, delays and queue sizes at the topology's interfaces...")
            self.setup_interfaces_qdisc()
            print("Starting tcpdump recordings at hosts...")
            self.start_tcpdump_recordings()
            print("Starting servers...")
            self.start_servers()

            print("Starting clients and optionally varying delay...")
            self.pool = self.start_pool()
            thread    = threading.Thread(target=self.start_clients)
            thread.start()
            self.startEvent.wait(TIMEOUT_SEC)
            self.perform_tc_delay_changes()
            thread.join()

            print("Killing descendent processes properly...")
            self.kill_processes_properly()
            self.finish_pool()
        except:
            print("Unexpected event occurred during testing! Emergency exit:")
            print("Killing descendent processes emergently...")
            self.finish_pool()
            self.kill_processes_emergently()
            raise


    #
    # Method loads metadata of the testing
    # throws MetadataError
    # returns dictionary with metadata
    #
    def load_metadata(self):
        metadataPath = os.path.join(self.dir, METADATA_NAME)

        try:
            with open(metadataPath) as metadataFile:
                metadata = json.load(metadataFile)
        except IOError as error:
            raise MetadataError, MetadataError("Failed to open meta: %s" % error), sys.exc_info()[2]
        except ValueError as error:
            raise MetadataError, MetadataError("Failed to load meta: %s" % error), sys.exc_info()[2]

        return metadata


    #
    # Method generates layout for each flow depending on number of flows in each entry of "layout"
    # field of metadata.
    # param [in] layout - metadata layout
    # throws MetadataError
    # returns per flow layout
    #
    def compute_per_flow_layout(self, layout):
        perFlowLayout = []

        for entry in layout:
            perFlowLayout.extend([entry] * entry[FLOWS])

        # sanity check
        if len(perFlowLayout) != self.flows:
            raise MetadataError('Insanity: field "%s"=%d must be %d (sum of all "%s" in "%s")!!!' %
                               (ALL_FLOWS, self.flows, len(perFlowLayout), FLOWS, SORTED_LAYOUT))

        subnetsNumber  = 2**(SUPERNET_SIZE - SUBNET_SIZE)
        maxFlowsNumber = (subnetsNumber - 1) / 2

        if len(perFlowLayout) > maxFlowsNumber:
            raise MetadataError('Flows number is %d but, with supernet %s, max flows number is %d' %
                               (len(perFlowLayout), SUPERNET_ADDRESS, maxFlowsNumber))

        return perFlowLayout


    #
    # Method generates dictionary of schemes' paths
    # throws MetadataError
    # returns dictionary of schemes' paths
    #
    def compute_schemes_paths(self):
        schemePaths = {}

        for scheme in self.schemes:

            if scheme not in schemePaths:
                schemePath = os.path.join(self.pantheon, WRAPPERS_PATH, "%s.py" % scheme)

                if not os.path.exists(schemePath):
                    raise MetadataError('Path of scheme "%s" does not exist:\n%s' %
                                       (scheme, schemePath))

                schemePaths[scheme] = schemePath

        return schemePaths


    #
    # Method generates arrays of delta times and corresponding delays for future
    # delay variability of the central link of the dumbbell topology
    # throws MetadataError
    # returns array of delta times in seconds, array of corresponding delays in us
    #
    def compute_delay_steps(self):
        runtimeUs       = self.runtimeSec * USEC_PER_SEC
        deltasNumber    = runtimeUs / self.deltaUs
        reminderDeltaUs = runtimeUs % self.deltaUs
        deltasSecArray  = [float(self.deltaUs) / USEC_PER_SEC] * deltasNumber

        if reminderDeltaUs != 0:
            deltasSecArray.append(float(reminderDeltaUs) / USEC_PER_SEC)

        delayUs       = self.baseUs
        delaysUsArray = [delayUs]

        if delayUs + self.stepUs > self.maxDelayUs and delayUs - self.stepUs < 0:
            raise MetadataError("Schedule of delay's changes for the central link of the dumbbell "
                                "topology cannot be generated because step is too big")

        for _ in deltasSecArray[1:]:
            signs = []

            if delayUs + self.stepUs <= self.maxDelayUs:
                signs.append(INCREASE)
            if delayUs - self.stepUs >= 0:
                signs.append(DECREASE)

            delayUs += self.stepUs * random.choice(signs)
            delaysUsArray.append(delayUs)

        return deltasSecArray, delaysUsArray


    #
    # Method generates schedule to start flows: intervals of sleeping and for each interval a list
    # of ids of flows to start after the sleep
    # param [in] perFlowLayout - per flow layout sorted by flow's start
    # returns schedule to start flows
    #
    def compute_starts_schedule(self, perFlowLayout):
        startsSchedule = [[] for _ in range(perFlowLayout[-1][START] + 1)]
        previousStart  = 0

        for flowId, flow in enumerate(perFlowLayout):
            flowStart = flow[START]

            startsSchedule[flowStart].append(flowId)

            if flowStart < previousStart: # sanity check
                raise MetadataError("Insanity: layout entries must be sorted by start field!!!")

            previousStart = flowStart

        return startsSchedule


    #
    # Method computes per flow link to container keeping sender/receiver processes
    # returns array of links to containers keeping sender's processes and array of links to
    # containers keeping receiver's processes
    #
    def compute_popen_holders(self):
        senderPopenHolders   = []
        receiverPopenHolders = []

        for i in range(0, self.flows):
            if self.runsFirst[i] == RECEIVER:
                senderPopenHolders  .append(self.clientPopens)
                receiverPopenHolders.append(self.serverPopens)
            else:
                senderPopenHolders.  append(self.serverPopens)
                receiverPopenHolders.append(self.clientPopens)

        return senderPopenHolders, receiverPopenHolders


    #
    # Method generates dumbbell topology.
    # Each of 2*FLOWS hosts has 1 interface, each of 2 routers has FLOWS+1 interface.
    #
    def build_dumbbell_network(self):
        self.network = Mininet(build=False)
        freeSubnets  = ipaddress.ip_network(SUPERNET_ADDRESS).subnets(new_prefix=SUBNET_PREFIX)

        self.leftHosts,  self.leftRouter  = self.build_half_dumbbell(
            freeSubnets, LEFT_HOSTS_LITERAL,  LEFT_ROUTER_NAME)

        self.rightHosts, self.rightRouter = self.build_half_dumbbell(
            freeSubnets, RIGHT_HOSTS_LITERAL, RIGHT_ROUTER_NAME)

        # connecting the two halves of the dumbbell
        self.network.addLink(self.leftRouter, self.rightRouter)

        # getting two ip addresses for the interfaces of the two routers
        subnet = freeSubnets.next()
        ipPool = ['%s/%d' % (host, subnet.prefixlen) for host in list(subnet.hosts())]

        leftRouterIntf  = self.leftRouter. intfs[self.flows]
        rightRouterIntf = self.rightRouter.intfs[self.flows]

        # assigning the two ip addresses to the interfaces of the two routers
        self.leftRouter. setIP(ipPool[0], intf=leftRouterIntf)
        self.rightRouter.setIP(ipPool[1], intf=rightRouterIntf)

        # turning off TCP segmentation offload and UDP fragmentation offload!
        self.leftRouter. cmd('ethtool -K %s tx off sg off tso off ufo off' % leftRouterIntf)
        self.rightRouter.cmd('ethtool -K %s tx off sg off tso off ufo off' % rightRouterIntf)

        # setting arp entries for the entire subnet consisting of the two routers
        self.leftRouter. cmd('arp', '-s', rightRouterIntf.IP(), rightRouterIntf.MAC())
        self.rightRouter.cmd('arp', '-s', leftRouterIntf. IP(), leftRouterIntf. MAC())

        # allowing the two halves of the dumbbell to exchange packets
        self.leftRouter. setDefaultRoute('via %s' % rightRouterIntf.IP())
        self.rightRouter.setDefaultRoute('via %s' % leftRouterIntf. IP())


    #
    # Method makes setup after reboot for each scheme
    #
    def setup_schemes_after_reboot(self):
        for schemePath in self.schemePaths.values():
            try:
                subprocess.check_call([schemePath, 'setup_after_reboot'], stdout=PIPE, stderr=PIPE)
            except subprocess.CalledProcessError as error:
                raise TestError(error)


    #
    # Method sets rates, (base) delays and queue sizes at the topology's interfaces
    #
    def setup_interfaces_qdisc(self):
        # setting netem for the central link of the dumbbell topology

        netemCmd = \
            'tc qdisc replace dev {0} root netem delay %dus {1:d}us rate {2:f}Mbit limit {3:d}'

        leftIntf  = self.leftRouter. intfs[self.flows]
        rightIntf = self.rightRouter.intfs[self.flows]

        self.leftNetemCmd  = netemCmd.format(leftIntf,
                                             self.jitterUs, self.rateMbps, self.leftQueuePkts)

        self.rightNetemCmd = netemCmd.format(rightIntf,
                                             self.jitterUs, self.rateMbps, self.rightQueuePkts)

        self.leftRouter. cmd(self.leftNetemCmd  % self.delaysArrayUs[0])
        self.rightRouter.cmd(self.rightNetemCmd % self.delaysArrayUs[0])

        # setting netem for all the links in the left and right halves of the dumbbell topology

        netemCmd = 'tc qdisc replace dev %s root netem delay %dus rate %fMbit limit %d'

        for i in range(0, self.flows):
            self.leftRouter.   cmd(netemCmd % (self.leftRouter.intfs[i],  self.leftDelaysUs[i],
                                               self.leftRatesMbps[i],     DEFAULT_QUEUE_SIZE))

            self.leftHosts[i]. cmd(netemCmd % (self.leftHosts[i].intf(),  self.leftDelaysUs[i],
                                               self.leftRatesMbps[i],     DEFAULT_QUEUE_SIZE))

            self.rightRouter.  cmd(netemCmd % (self.rightRouter.intfs[i], self.rightDelaysUs[i],
                                               self.rightRatesMbps[i],    DEFAULT_QUEUE_SIZE))

            self.rightHosts[i].cmd(netemCmd % (self.rightHosts[i].intf(), self.rightDelaysUs[i],
                                               self.rightRatesMbps[i],    DEFAULT_QUEUE_SIZE))


    #
    # Method starts tcpdump recordings at sender host and at receiver host of each flow
    #
    def start_tcpdump_recordings(self):
        for i in range(0, self.flows):
            if self.directions[i] == LEFTWARD:
                receiverHost = self.leftHosts[i]
                senderHost   = self.rightHosts[i]
            else:
                receiverHost = self.rightHosts[i]
                senderHost   = self.leftHosts[i]

            receiverIntf     = receiverHost.intf()
            senderIntf       = senderHost.  intf()

            receiverIp       = receiverIntf.IP()
            senderIp         = senderIntf.  IP()

            receiverDumpName = "%d-%s-%s.pcap" % (i + 1, self.schemes[i], RECEIVER)
            senderDumpName   = "%d-%s-%s.pcap" % (i + 1, self.schemes[i], SENDER)

            receiverDumpPath = os.path.join(self.dir, receiverDumpName)
            senderDumpPath   = os.path.join(self.dir, senderDumpName)

            cmd = 'tcpdump -tt -nn -i %s -Z %s -B %d -w %s host %s and host %s and (tcp or udp)'

            receiverDumpPopen = receiverHost.popen(
            cmd % (receiverIntf, self.user, self.bufferKiB, receiverDumpPath, receiverIp, senderIp))

            senderDumpPopen   = senderHost.popen(
            cmd % (senderIntf,   self.user, self.bufferKiB, senderDumpPath,   receiverIp, senderIp))

            self.receiverDumpPopens.append(receiverDumpPopen)
            self.senderDumpPopens.  append(senderDumpPopen)

        sleep(0.5)  # in order not to miss the first packets


    #
    # Method starts server for each flow and prepares the corresponding client for future start
    #
    def start_servers(self):
        for i in range(0, self.flows):
            if self.directions[i] == LEFTWARD:
                leftHostRole = RECEIVER
            else:
                leftHostRole = SENDER

            if leftHostRole == self.runsFirst[i]:
                server = self.leftHosts [i]
                client = self.rightHosts[i]
            else:
                server = self.rightHosts[i]
                client = self.leftHosts [i]

            schemePath = self.schemePaths[self.schemes[i]]

            serverPopen = server.popen(
                ['sudo', '-u', self.user, schemePath, self.runsFirst[i], str(PORT)])

            self.serverPopens.append(serverPopen)

            # Check if the server's ready. Maybe, this is not the best way but in Pantheon they just
            # sleep for three seconds after opening all the servers.
            while not server.cmd("lsof -i :%d" % PORT).strip(): pass

            runsSecond = RECEIVER if self.runsFirst[i] == SENDER else SENDER

            clientCmd = ['sudo', '-u', self.user, schemePath, runsSecond, server.IP(), str(PORT)]

            self.clients.   append(client)
            self.clientCmds.append(clientCmd)


    #
    # Method starts multiprocessing pool with processes which will start clients. Size of pool is
    # computed as minimum between the number of cores minus one and the maximum number of flows
    # which will be started simultaneously, i.e. the maximum number of flows with same start value.
    # returns multiprocessing pool
    #
    def start_pool(self):
        print(self.startsSchedule)
        print("!!!!", len(max(self.startsSchedule, key=lambda x: len(x))))
        print(min(cpu_count() - 1, len(max(self.startsSchedule, key=lambda x: len(x)))))

        originalSigintHandler = signal.signal(signal.SIGINT, signal.SIG_IGN)

        pool = Pool(min(cpu_count() - 1, len(max(self.startsSchedule, key=lambda x: len(x)))))

        signal.signal(signal.SIGINT, originalSigintHandler)

        return pool


    #
    # Method starts clients for each flow
    #
    def start_clients(self):
        benchmarkStart = timeStart = time.time() # TODO: remove benchmark

        self.clientPopens.extend(self.pool.map(start_client, self.startsSchedule[0]))
        print("!", time.time() - benchmarkStart)

        self.startEvent.set()

        for i in range(1, len(self.startsSchedule)):
            sleep(SECOND - ((time.time() - timeStart) % SECOND))

            self.clientPopens.extend(self.pool.map(start_client, self.startsSchedule[i]))
            print("#", time.time())

        print("debug benchmark 1: %f" % (time.time() - benchmarkStart))


    #
    # Method performs netem delay changes on interfaces of the two routers of the dumbbell topology
    #
    def perform_tc_delay_changes(self):
        benchmarkStart = time.time() # TODO: remove benchmark
        sleep(self.deltasArraySec[0])

        intervalsNumber = len(self.deltasArraySec)

        if intervalsNumber != 1:
            timeStart = time.time()

            for i in range(1, intervalsNumber - 1):
                self.leftRouter. cmd(self.leftNetemCmd  % self.delaysArrayUs[i])
                self.rightRouter.cmd(self.rightNetemCmd % self.delaysArrayUs[i])
                sleep(self.deltasArraySec[i] - ((time.time() - timeStart) % self.deltasArraySec[i]))

            timeStart = time.time()

            self.leftRouter. cmd(self.leftNetemCmd  % self.delaysArrayUs[-1])
            self.rightRouter.cmd(self.rightNetemCmd % self.delaysArrayUs[-1])
            sleep(self.deltasArraySec[-1] - ((time.time() - timeStart) % self.deltasArraySec[-1]))

        print("debug benchmark 2: %f" % (time.time() - benchmarkStart))


    #
    # Method kills client, server and tcpdump processes
    #
    def kill_processes_properly(self):

        for dumpPopen in self.senderDumpPopens:
            os.kill(dumpPopen.pid, signal.SIGTERM)

        for dumpPopen in self.receiverDumpPopens:
            os.kill(dumpPopen.pid, signal.SIGTERM)

        for flowId, holder in enumerate(self.senderPopenHolders):
            os.killpg(os.getpgid(holder[flowId].pid), signal.SIGKILL)

        for flowId, holder in enumerate(self.receiverPopenHolders):
            os.killpg(os.getpgid(holder[flowId].pid), signal.SIGKILL)

        self.wait_child_processes()

        self.check_dropped_packets()


    #
    # Method terminates and joins multiprocessing pool of processes which started clients
    #
    def finish_pool(self):
        if self.pool is not None:
            self.pool.terminate()
            self.pool.join()
            self.pool = None


    #
    # Method kills client, server and tcpdump processes in case of testing error
    #
    def kill_processes_emergently(self):
        for clientPopen in self.clientPopens:
            try:
                os.killpg(os.getpgid(clientPopen.pid), signal.SIGKILL)
            except OSError:
                pass

        for serverPopen in self.serverPopens:
            try:
                os.killpg(os.getpgid(serverPopen.pid), signal.SIGKILL)
            except OSError:
                pass

        for dumpPopen in self.senderDumpPopens:
            try:
                os.kill(dumpPopen.pid, signal.SIGTERM)
            except OSError:
                pass

        for dumpPopen in self.receiverDumpPopens:
            try:
                os.kill(dumpPopen.pid, signal.SIGTERM)
            except OSError:
                pass

        self.wait_child_processes()


    #
    # Method generates half a dumbbell topology
    # param [in] freeSubnets  - iterator over still available subnets with prefix length 30
    # param [in] hostsLiteral - letter with which hosts are named, e.g. for x we get x1, x2, x3, ...
    # param [in] routerName   - name of the router interconnecting all the hosts
    # returns all the hosts in the half, the router interconnecting all the hosts in the half
    #
    def build_half_dumbbell(self, freeSubnets, hostsLiteral, routerName):
        hosts   = [None] * self.flows
        ipPools = [None] * self.flows

        router = self.network.addHost(routerName)
        router.cmd('sysctl net.ipv4.ip_forward=1')
        router.cmd('ifconfig lo up')

        for i in range(0, self.flows):
            # creating new host and connecting it to one of router interfaces
            hosts[i] = self.network.addHost('%s%d' % (hostsLiteral, (i + 1)))
            hosts[i].cmd('ifconfig lo up')
            self.network.addLink(hosts[i], router)

            # getting two ip addresses for router interface and host interface
            subnet     = freeSubnets.next()
            ipPools[i] = ['%s/%d' % (host, subnet.prefixlen) for host in list(subnet.hosts())]

            # assigning the two ip addresses to the router interface and host interface
            router.setIP(ipPools[i][1], intf=router.intfs[i])
            hosts[i].setIP(ipPools[i][0])

            # turning off TCP segmentation offload and UDP fragmentation offload!
            router.  cmd('ethtool -K %s tx off sg off tso off ufo off' % router.intfs[i])
            hosts[i].cmd('ethtool -K %s tx off sg off tso off ufo off' % hosts[i].intf())

            # setting arp entries for the entire subnet
            router.  cmd('arp', '-s', hosts[i].intf().IP(), hosts[i].intf().MAC())
            hosts[i].cmd('arp', '-s', router.intfs[i].IP(), router.intfs[i].MAC())

            # setting the router as the default gateway for the host
            hosts[i].setDefaultRoute('via %s' % router.intfs[i].IP())

        return hosts, router


    #
    # Method removes zombies of child processes of the current script process
    #
    def wait_child_processes(self):

        all = [self.clientPopens, self.serverPopens, self.senderDumpPopens, self.receiverDumpPopens]

        for popens in all:
            for popen in popens:
                try:
                    os.waitpid(popen.pid, 0)
                except OSError:
                    pass


    #
    # Method checks if kernel dropped any packets by checking tcpdump output on its termination
    #
    def  check_dropped_packets(self):
        droppedPackets = 0

        for popens in [self.senderDumpPopens, self.receiverDumpPopens]:
            for popen in popens:
                output = popen.communicate()[1]
                result = re.search('(\d+) packets dropped', output)
                droppedPackets += int(result.group(1))

        if droppedPackets != 0:
            print('WARNING: tcpdump processes dropped %d packets in total. '
                  'Try to increase -b/--buffer option.' % droppedPackets)


#
# Entry function
#
if __name__ == '__main__':
    user     = sys.argv[USER    ]
    dir      = sys.argv[DIR     ]
    pantheon = sys.argv[PANTHEON]
    exitCode = EXIT_SUCCESS

    try:
        test = Test(user, dir, pantheon)
        test.test()
        CLI(test.network)
    except MetadataError as error:
        print("Metadata error:\n%s" % error)
        exitCode = EXIT_FAILURE
    except TestError as error:
        print("Testing error:\n%s"  % error)
        exitCode = EXIT_FAILURE
    except KeyboardInterrupt:
        sys.exit(EXIT_FAILURE)

    exitMessage = SUCCESS_MESSAGE if exitCode == EXIT_SUCCESS else FAILURE_MESSAGE
    print(exitMessage)

    sys.exit(exitCode)
