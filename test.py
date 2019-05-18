#!/usr/bin/python

import os
import signal
import subprocess
import socket
import sys
import random
import threading
import ipaddress
import time
from time import sleep

from mininet.topo import Topo
from mininet.net  import Mininet
from mininet.log  import setLogLevel, info
from mininet.cli  import CLI

PORT            = '50000'
SUPERNET        = u'11.0.0.0/16'
SUBNET_PREFIX   = 30
USER            = sys.argv[1]
SCHEME          = sys.argv[2]
DIR             = sys.argv[3]
PANTHEON        = sys.argv[4]
RATE_MBITS      = sys.argv[5]
RUNTIME_SEC     = int(sys.argv[6])
MAX_DELAY_USEC  = int(sys.argv[7])
BASE_USEC       = int(sys.argv[8])
DELTA_USEC      = int(sys.argv[9])
STEP_USEC       = int(sys.argv[10])
JITTER_USEC     = int(sys.argv[11])
FLOWS           = int(sys.argv[12])
INTERVAL_SEC    = int(sys.argv[13])
SENDER          = 'sender'
RECEIVER        = 'receiver'
WRAPPERS_PATH   = 'src/wrappers'
THIRD_PARTY_DIR = 'third_party'
SCHEME_PATH     = os.path.join(PANTHEON, WRAPPERS_PATH, SCHEME + '.py')


#
# Function kills launched processes and its children
# param [in] serverPopens     - popen objects of launched server processes
# param [in] clientPopens     - popen objects of launched client processes
# param [in] serverDumpPopens - popen objects of tcpdump processes recording on servers
# param [in] clientDumpPopens - popen objects of tcpdump processes recording on clients
# param [in] runsFirst        - "sender" or "receiver" of the scheme depending on who servers are
#
def killProcesses(serverPopens, clientPopens, serverDumpPopens, clientDumpPopens, runsFirst):
    if runsFirst == SENDER:
        for serverPopen in serverPopens:
            os.killpg(os.getpgid(serverPopen.pid), signal.SIGKILL)

        for clientPopen in clientPopens:
            os.killpg(os.getpgid(clientPopen.pid), signal.SIGKILL)

        for serverDumpPopen in serverDumpPopens:
            os.kill(serverDumpPopen.pid, signal.SIGTERM)

        for clientDumpPopen in clientDumpPopens:
            os.kill(clientDumpPopen.pid, signal.SIGTERM)
    else:
        for clientPopen in clientPopens:
            os.killpg(os.getpgid(clientPopen.pid), signal.SIGKILL)

        for serverPopen in serverPopens:
            os.killpg(os.getpgid(serverPopen.pid), signal.SIGKILL)

        for clientDumpPopen in clientDumpPopens:
            os.kill(clientDumpPopen.pid, signal.SIGTERM)

        for serverDumpPopen in serverDumpPopens:
            os.kill(serverDumpPopen.pid, signal.SIGTERM)


#
# Array of popen objects of launched client processes. It is instantiated by launch_clients().
#
clientPopens = []
#
# Synchronization object of the main thread and the thread which launches clients
#
startEvent = threading.Event()
#
# Function launches client processes. The function runs in a separate thread.
# param [in] clients    - hosts on which the clients are launched
# param [in] runsSecond - "sender" or "receiver" of the scheme depending on who clients are
# param [in] serverIPs  - IP addresses of hosts with servers to which clients connect
#
def launch_clients(clients, runsSecond, serverIPs):
    benchmarkStart = timeStart = time.time() # TODO: remove benchmark

    if INTERVAL_SEC != 0:
        clientPopens.append(
            clients[0].popen(['sudo', '-u', USER, SCHEME_PATH, runsSecond, serverIPs[0], PORT]))

        startEvent.set()

        for i in range(1, FLOWS):
            sleep(INTERVAL_SEC - ((time.time() - timeStart) % INTERVAL_SEC))

            clientPopens.append(
                clients[i].popen(['sudo', '-u', USER, SCHEME_PATH, runsSecond, serverIPs[i], PORT]))
    else:
        for i in range(0, FLOWS):
            clientPopens.append(
                clients[i].popen(['sudo', '-u', USER, SCHEME_PATH, runsSecond, serverIPs[i], PORT]))

        startEvent.set()

    print(time.time() - benchmarkStart)


#
# Function launches server processes
# param [in] servers   - hosts on which the servers are launched
# param [in] runsFirst - "sender" or "receiver" of the scheme depending on who servers are
# returns popen objects of launched server processes and IP addresses of the servers
#
def launch_servers(servers, runsFirst):
    serverPopens = []
    serverIPs    = []

    for server in servers:
        serverPopen = server.popen(['sudo', '-u', USER, SCHEME_PATH, runsFirst, PORT])

        serverIPs   .append(server.IP())
        serverPopens.append(serverPopen)

        # Check if the server's ready. Maybe, this is not the best way but in Pantheon they just
        # sleep for three seconds after opening all the servers.
        while not server.cmd("lsof -i :%s" % PORT).strip(): pass

    return serverPopens, serverIPs


#
# Function determines who runs first: the sender or the receiver of the scheme
# returns sender and receiver in the order of running
#
def who_is_server():
    runsFirst = subprocess.check_output([SCHEME_PATH, 'run_first']).strip()

    if runsFirst == RECEIVER:
        runsSecond = SENDER
    elif runsFirst == SENDER:
        runsSecond = RECEIVER
    else:
        sys.exit('Must specify "receiver" or "sender" runs first')

    return runsFirst, runsSecond


#
# Function performs tc qdisc delay changes on interfaces of the two routers of the dumbbell topology
# param [in] leftRouter  - the left router of the dumbbell topology
# param [in] rightRouter - the right router of the dumbbell topology
# param [in] leftIntf    - interface of the left router
# param [in] rightIntf   - interface of the right router
# param [in] deltasSec   - array of delta times in seconds
# param [in] delaysUsec  - array of delays in microseconds corresponding to the array of delta times
#
def perform_tc_delay_changes(leftRouter, rightRouter, leftIntf, rightIntf, deltasSec, delaysUsec):
    sleep(deltasSec[0])

    intervalsNumber = len(deltasSec)

    if intervalsNumber != 1:
        timeStart = time.time()

        for i in range(1, intervalsNumber - 1):

            leftRouter. cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                           (leftIntf,  delaysUsec[i], JITTER_USEC, RATE_MBITS))

            rightRouter.cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                           (rightIntf, delaysUsec[i], JITTER_USEC, RATE_MBITS))

            sleep(deltasSec[i] - ((time.time() - timeStart ) % deltasSec[i]))

        timeStart = time.time()

        leftRouter. cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                       (leftIntf,  delaysUsec[-1], JITTER_USEC, RATE_MBITS))

        rightRouter.cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                       (rightIntf, delaysUsec[-1], JITTER_USEC, RATE_MBITS))

        sleep(deltasSec[-1] - ((time.time() - timeStart) % deltasSec[-1]))


#
# Function starts tcpdump processes recording on servers and clients
# param [in] servers    - hosts on which the servers are launched
# param [in] clients    - hosts on which the clients are launched
# param [in] runsFirst  - "sender" or "receiver" of the scheme depending on who the servers are
# param [in] runsSecond - "sender" or "receiver" of the scheme depending on who the clients are
# returns popen objects of tcpdump processes recording on servers and clients
#
def start_tcpdump(servers, clients, runsFirst, runsSecond):
    serverDumpPopens = []
    clientDumpPopens = []

    for i in range(0, FLOWS):
        serverIntf = servers[i].intf()
        clientIntf = clients[i].intf()

        serverIp   = serverIntf.IP()
        clientIp   = clientIntf.IP()

        serverDump = os.path.join(DIR, "%s-%s-%d.pcap" % (SCHEME, runsFirst,  i + 1))
        clientDump = os.path.join(DIR, "%s-%s-%d.pcap" % (SCHEME, runsSecond, i + 1))

        cmd = 'tcpdump -tt -nn -i %s -Z %s -w %s host %s and host %s and (tcp or udp)'

        serverDumpPopen = servers[i].popen(cmd % (serverIntf, USER, serverDump, serverIp, clientIp))
        clientDumpPopen = clients[i].popen(cmd % (clientIntf, USER, clientDump, serverIp, clientIp))

        serverDumpPopens.append(serverDumpPopen)
        clientDumpPopens.append(clientDumpPopen)

    sleep(0.5) # in order not to miss the first packets
    return serverDumpPopens, clientDumpPopens


#
# Function generates arrays of delta times and corresponding delays
# returns arrays of delta times in seconds and corresponding delays in microseconds
#
def generate_steps():
    runtimeUsec       = RUNTIME_SEC * int(1e6)
    deltasNumber      = runtimeUsec / DELTA_USEC
    reminderDeltaUsec = runtimeUsec % DELTA_USEC
    deltasSec         = [ float(DELTA_USEC) / 1e6 ] * deltasNumber

    if reminderDeltaUsec != 0:
        deltasSec = deltasSec + [ float(reminderDeltaUsec) / 1e6 ]

    delayUsec  = BASE_USEC
    delaysUsec = [ delayUsec ]

    if delayUsec + STEP_USEC > MAX_DELAY_USEC and delayUsec - STEP_USEC < 0:
        sys.exit("Schedule of delay changes cannot be generated because step is too big")

    for _ in deltasSec[1:]:
        signs = []

        if delayUsec + STEP_USEC <= MAX_DELAY_USEC:
            signs = signs + [ 1 ]
        if delayUsec - STEP_USEC >= 0:
            signs = signs + [-1 ]

        delayUsec  += STEP_USEC * random.choice(signs)
        delaysUsec += [ delayUsec ]

    return deltasSec, delaysUsec


#
# Function runs testing for the scheme
# param [in] servers     - the left hosts of the dumbbell topology
# param [in] clients     - the right hosts of the dumbbell topology
# param [in] leftRouter  - the left router interconnecting servers of the dumbbell topology
# param [in] rightRouter - the right router interconnecting clients of the dumbbell topology
# param [in] runsFirst   - "sender" or "receiver" of the scheme depending on who the servers are
# param [in] runsSecond  - "sender" or "receiver" of the scheme depending on who the clients are
#
def run_test(servers, clients, leftRouter, rightRouter, runsFirst, runsSecond):
    deltasSec, delaysUsec = generate_steps()

    leftIntf, rightIntf   = leftRouter.intfs[FLOWS], rightRouter.intfs[FLOWS]

    leftRouter.cmd ('tc qdisc add dev %s root netem delay %dus %dus rate %sMbit' %
                   (leftIntf,  delaysUsec[0], JITTER_USEC, RATE_MBITS))

    rightRouter.cmd('tc qdisc add dev %s root netem delay %dus %dus rate %sMbit' %
                   (rightIntf, delaysUsec[0], JITTER_USEC, RATE_MBITS))

    serverDumpPopens, clientDumpPopens = start_tcpdump(servers, clients, runsFirst, runsSecond)

    serverPopens, serverIPs = launch_servers(servers, runsFirst)

    thread = threading.Thread(target = launch_clients, args = (clients, runsSecond, serverIPs))
    thread.start()
    startEvent.wait()

    benchmarkStart = time.time() # TODO: remove benchmark
    perform_tc_delay_changes(leftRouter, rightRouter, leftIntf, rightIntf, deltasSec, delaysUsec)
    print(time.time() - benchmarkStart)

    thread.join()
    killProcesses(serverPopens, clientPopens, serverDumpPopens, clientDumpPopens, runsFirst)


#
# Function generates half a dumbbell topology
# param [in] network          - full Mininet network
# param [in] availableSubnets - iterator over still available subnets with prefix length 30
# param [in] hostLiteral      - letter with which hosts are named, e.g. for x we get x1, x2, x3, ...
# param [in] routerName       - name of the router interconnecting all the hosts
# returns all the hosts in the half, the router interconnecting all the hosts in the half
#
def build_half_dumbbell(network, availableSubnets, hostLiteral, routerName):
    hosts   = [ None ] * FLOWS
    ipPools = [ None ] * FLOWS

    router = network.addHost(routerName)
    router.cmd('sysctl net.ipv4.ip_forward=1')
    router.cmd('ifconfig lo up')

    for i in range (0, FLOWS):
        # creating new host and connecting it to one of router interfaces
        hosts[i] = network.addHost('%s%d' % (hostLiteral, (i + 1)))
        hosts[i].cmd('ifconfig lo up')
        network.addLink(hosts[i], router)

        # getting two ip addresses for router interface and host interface
        subnet     = availableSubnets.next()
        ipPools[i] = [ '%s/%d' % (host, subnet.prefixlen) for host in list(subnet.hosts()) ]

        # assigning the two ip addresses to the router interface and host interface
        router  .setIP(ipPools[i][1], intf=router.intfs[i])
        hosts[i].setIP(ipPools[i][0])

        # turning off TCP segmentation offload and UDP fragmentation offload!
        router.  cmd('ethtool -K %s tx off sg off tso off ufo off' % router.intfs[i])
        hosts[i].cmd('ethtool -K %s tx off sg off tso off ufo off' % hosts[i].intf())

        # setting egress qdisc of each of the two interfaces to FIFO queue limited by 1000 packets
        router.  cmd('tc qdisc add dev %s root pfifo limit 1000'   % router.intfs[i])
        hosts[i].cmd('tc qdisc add dev %s root pfifo limit 1000'   % hosts[i].intf())

        # setting arp entries for the entire subnet
        router.  cmd('arp', '-s', hosts[i].intf().IP(), hosts[i].intf().MAC())
        hosts[i].cmd('arp', '-s', router.intfs[i].IP(), router.intfs[i].MAC())

        # setting the router as the default gateway for the host
        hosts[i].setDefaultRoute('via %s' % router.intfs[i].IP())

    return hosts, router


#
# Function generates dumbbell topology
# param [in] runsFirst - "sender" or "receiver" of the scheme depending on who servers are
# returns full network, hosts in the left half, hosts in the right half, left router, right router
#
def build_dumbbell_network(runsFirst):
    network          = Mininet(build=False)
    availableSubnets = ipaddress.ip_network(SUPERNET).subnets(new_prefix=SUBNET_PREFIX)

    # ensuring that IP of sender is always higher than IP of receiver for future dissection of dumps
    if runsFirst == SENDER:
        availableSubnets = reversed(list(availableSubnets))

    servers, leftRouter  = build_half_dumbbell(network, availableSubnets, 's', 'r1')
    clients, rightRouter = build_half_dumbbell(network, availableSubnets, 'c', 'r2')

    # connecting the two halves of the dumbbell
    network.addLink(leftRouter, rightRouter)

    # getting two ip addresses for the interfaces of the two routers
    subnet = availableSubnets.next()
    ipPool = ['%s/%d' % (host, subnet.prefixlen) for host in list(subnet.hosts())]

    # assigning the two ip addresses to the interfaces of the two routers
    leftRouter. setIP(ipPool[0], intf=leftRouter. intfs[FLOWS])
    rightRouter.setIP(ipPool[1], intf=rightRouter.intfs[FLOWS])

    # turning off TCP segmentation offload and UDP fragmentation offload!
    leftRouter. cmd('ethtool -K %s tx off sg off tso off ufo off' % leftRouter. intfs[FLOWS])
    rightRouter.cmd('ethtool -K %s tx off sg off tso off ufo off' % rightRouter.intfs[FLOWS])

    # setting arp entries for the entire subnet consisting of the two routers
    leftRouter. cmd('arp', '-s', rightRouter.intfs[FLOWS].IP(), rightRouter.intfs[FLOWS].MAC())
    rightRouter.cmd('arp', '-s', leftRouter.intfs[FLOWS].IP(), leftRouter.intfs[FLOWS].MAC())

    # allowing the two halves of the dumbbell to exchange packets
    leftRouter. setDefaultRoute('via %s' % rightRouter.intfs[FLOWS].IP())
    rightRouter.setDefaultRoute('via %s' % leftRouter. intfs[FLOWS].IP())

    # now each of 2*FLOWS hosts has 1 interface, each of 2 routers has FLOWS+1 interfaces
    return network, servers, clients, leftRouter, rightRouter


#
# Entry function
#
if __name__ == '__main__':
    random.seed(1) # TODO: make seed parameter

    runsFirst, runsSecond = who_is_server()

    network, servers, clients, leftRouter, rightRouter = build_dumbbell_network(runsFirst)

    subprocess.call([SCHEME_PATH, 'setup_after_reboot'])

    run_test(servers, clients, leftRouter, rightRouter, runsFirst, runsSecond)

    #CLI(network)
