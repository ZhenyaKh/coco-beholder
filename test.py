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
WRAPPERS_PATH   = 'src/wrappers'
THIRD_PARTY_DIR = 'third_party'
SCHEME_PATH     = os.path.join(PANTHEON, WRAPPERS_PATH, SCHEME + '.py')


def build_half_dumbbell(network, availableSubnets, hostLiteral, routerName):
    hosts   = [ None ] * FLOWS
    ipPools = [ None ] * FLOWS

    router = network.addHost(routerName)
    router.cmd('sysctl net.ipv4.ip_forward=1')

    for i in range (0, FLOWS):
        # creating new host and connecting it to one of router interfaces
        hosts[i] = network.addHost('%s%d' % (hostLiteral, (i + 1)))
        network.addLink(hosts[i], router)

        # getting two ip addresses for router interface and host interface
        subnet     = availableSubnets.next()
        ipPools[i] = [ '%s/%d' % (host, subnet.prefixlen) for host in list(subnet.hosts()) ]

        # assigning the two ip addresses to the router interface and host interface
        router  .setIP(ipPools[i][1], intf=router.intfs[i])
        hosts[i].setIP(ipPools[i][0])

        # setting the router as the default gateway for the host
        hosts[i].setDefaultRoute('via %s' % router.intfs[i].IP())

    return hosts, router


def build_dumbbell_network():
    network          = Mininet(build=False)
    availableSubnets = ipaddress.ip_network(u'11.0.0.0/24').subnets(new_prefix=30)

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

    # allowing the two halves of the dumbbell to exchange packets
    leftRouter. setDefaultRoute('via %s' % rightRouter.intfs[FLOWS].IP())
    rightRouter.setDefaultRoute('via %s' % leftRouter. intfs[FLOWS].IP())

    # now each of 2*FLOWS hosts has 1 interface, each of 2 routers has FLOWS+1 interfaces
    return network, servers, clients


#
# Function kills launched processes and its children
# param [in] clientProcesses   - popen objects of launched client processes
# param [in] serverProcesses   - popen objects of launched server processes
# param [in] pcapClientProcess - tcpdump process recording on client
# param [in] pcapServerProcess - tcpdump process recording on server
#
def killProcesses(clientProcesses, serverProcesses, pcapClientProcess, pcapServerProcess):
    for clientProcess in clientProcesses:
        os.killpg(os.getpgid(clientProcess.pid), signal.SIGTERM)

    for serverProcess in serverProcesses:
        os.killpg(os.getpgid(serverProcess.pid), signal.SIGTERM)

    os.kill(pcapClientProcess.pid, signal.SIGTERM)
    os.kill(pcapServerProcess.pid, signal.SIGTERM)


#
# Array of popen objects of launched client processes. It is instantiated by launch_clients().
#
clientProcesses = []
#
# Synchronization object of the main thread and the thread which launches clients
#
startEvent = threading.Event()
#
# Function launches client processes. The function runs in a separate thread.
# param [in] secondHost - the host on which the clients are launched
# param [in] client     - "sender" or "receiver" of the scheme depending on who the clients are
# param [in] serverIp   - IP address of the host with servers to which clients connect
# param [in] ports      - array of ports of the servers to which clients connect
#
def launch_clients(secondHost, client, serverIp, ports):
    benchmarkStart = timeStart = time.time() # TODO: remove benchmark

    if INTERVAL_SEC != 0:
        clientProcesses.append(
            secondHost.popen(['sudo', '-u', USER, SCHEME_PATH, client, serverIp, ports[0]]))

        startEvent.set()

        for i in range(1, FLOWS):
            sleep(INTERVAL_SEC - ((time.time() - timeStart) % INTERVAL_SEC))

            clientProcesses.append(
                secondHost.popen(['sudo', '-u', USER, SCHEME_PATH, client, serverIp, ports[i]]))
    else:
        for i in range(0, FLOWS):
            clientProcesses.append(
                secondHost.popen(['sudo', '-u', USER, SCHEME_PATH, client, serverIp, ports[i]]))

        startEvent.set()

    print(time.time() - benchmarkStart)


#
# Function returns an available port
# returns an available port
#
def getFreePort():
    sock = socket.socket(socket.AF_INET)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return str(port)


#
# Function launches server processes.
# param [in] firstHost - the host on which the servers are launched
# param [in] server    - "sender" or "receiver" of the scheme depending on who the servers are
# returns popen objects of launched server processes and ports on which the servers listen
#
def launch_servers(firstHost, server):
    serverPorts     = []
    serverProcesses = []

    for _ in range(0, FLOWS):
        serverPort    = getFreePort()
        serverProcess = firstHost.popen(['sudo', '-u', USER, SCHEME_PATH, server, serverPort])

        serverPorts    .append(serverPort)
        serverProcesses.append(serverProcess)

        # Check if the server's ready. Maybe, this is not the best way but in Pantheon they just
        # sleep for three seconds after opening all the servers.
        while not firstHost.cmd("lsof -i :%s" % serverPort).strip(): pass

    return serverProcesses, serverPorts


#
# Function determines who runs first: the sender or the receiver of the scheme
# returns sender and receiver in the order of running
#
def whoIsServer():
    server = subprocess.check_output([SCHEME_PATH, 'run_first']).strip()

    if server == 'receiver':
        client = 'sender'
    elif server == 'sender':
        client = 'receiver'
    else:
        sys.exit('Must specify "receiver" or "sender" runs first')

    return server, client


#
# Function perform tc qdisc delay changes on interfaces of the two hosts
# param [in] firstHost  - the first  host of the point-to-point topology
# param [in] secondHost - the second host of the point-to-point topology
# param [in] firstIntf  - interface of the first  host
# param [in] secondIntf - interface of the second host
# param [in] deltasSec  - array of delta times in seconds
# param [in] delaysUsec - array of delays in microseconds corresponding to the array of delta times
#
def perform_tc_delay_changes(firstHost, secondHost, firstIntf, secondIntf, deltasSec, delaysUsec):
    sleep(deltasSec[0])

    intervalsNumber = len(deltasSec)

    if intervalsNumber != 1:
        timeStart = time.time()

        for i in range(1, intervalsNumber - 1):

            firstHost. cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                          (firstIntf,  delaysUsec[i], JITTER_USEC, RATE_MBITS))

            secondHost.cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                          (secondIntf, delaysUsec[i], JITTER_USEC, RATE_MBITS))

            sleep(deltasSec[i] - ((time.time() - timeStart ) % deltasSec[i]))

        timeStart = time.time()

        firstHost. cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                      (firstIntf,  delaysUsec[-1], JITTER_USEC, RATE_MBITS))

        secondHost.cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                      (secondIntf, delaysUsec[-1], JITTER_USEC, RATE_MBITS))

        sleep(deltasSec[-1] - ((time.time() - timeStart) % deltasSec[-1]))


#
# Function runs testing for the scheme
# param [in] firstHost  - the first  host of the point-to-point topology
# param [in] secondHost - the second host of the point-to-point topology
# param [in] deltasSec  - array of delta times in seconds
# param [in] delaysUsec - array of delays in microseconds corresponding to the array of delta times
#
def run_test(firstHost, secondHost, deltasSec, delaysUsec):
    firstIntf, secondIntf = str(firstHost.intf()), str(secondHost.intf())

    firstHost.cmd ('tc qdisc delete dev %s root' % firstIntf)
    firstHost.cmd ('tc qdisc add dev %s root netem delay %dus %dus rate %sMbit' %
                  (firstIntf,  delaysUsec[0], JITTER_USEC, RATE_MBITS))

    secondHost.cmd('tc qdisc delete dev %s root' % secondIntf)
    secondHost.cmd('tc qdisc add dev %s root netem delay %dus %dus rate %sMbit' %
                  (secondIntf, delaysUsec[0], JITTER_USEC, RATE_MBITS))

    server,   client   = whoIsServer()
    serverIp, clientIp = firstHost.IP(firstIntf), secondHost.IP(secondIntf)

    serverDump = os.path.join(DIR, "%s-%s.pcap" % (SCHEME, server))
    clientDump = os.path.join(DIR, "%s-%s.pcap" % (SCHEME, client))

    cmd = 'tcpdump -tt -nn -i %s -Z %s -w %s '\
          'host %s and host %s and not arp and not icmp and not icmp6'

    pcapServerProcess = firstHost. popen(cmd % (firstIntf,  USER, serverDump, serverIp, clientIp))
    pcapClientProcess = secondHost.popen(cmd % (secondIntf, USER, clientDump, serverIp, clientIp))

    serverProcesses, ports = launch_servers(firstHost, server)

    thread = threading.Thread(target = launch_clients, args = (secondHost, client, serverIp, ports))
    thread.start()
    startEvent.wait()

    benchmarkStart = time.time() # TODO: remove benchmark
    perform_tc_delay_changes(firstHost, secondHost, firstIntf, secondIntf, deltasSec, delaysUsec)
    print(time.time() - benchmarkStart)

    thread.join()
    killProcesses(clientProcesses, serverProcesses, pcapClientProcess, pcapServerProcess)


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
# Entry function
#
if __name__ == '__main__':
    #setLogLevel('info')
    random.seed(1) # TODO: make seed parameter

    network, servers, clients = build_dumbbell_network()

    subprocess.call([SCHEME_PATH, 'setup_after_reboot'])

    deltasSec, delaysUsec = generate_steps()

    #run_test(net['h1'], net['h2'], deltasSec, delaysUsec)
    CLI(network)
