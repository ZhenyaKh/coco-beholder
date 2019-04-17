#!/usr/bin/python 

import os
import signal
import subprocess
import socket
import sys
import random
import threading
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


#        
# Custom point-to-point Mininet topology class
#
class NetworkTopo(Topo):
    #        
    # Constructor
    #
    def build(self, **_opts):
        firstHost  = self.addHost('h1')
        secondHost = self.addHost('h2')

        self.addLink(firstHost, secondHost)


def killProcesses(clientProcesses, serverProcesses, pcapClientProcess, pcapServerProcess):
    for clientProcess in clientProcesses:
        os.killpg(os.getpgid(clientProcess.pid), signal.SIGTERM)

    for serverProcess in serverProcesses:
        os.killpg(os.getpgid(serverProcess.pid), signal.SIGTERM)

    os.kill(pcapClientProcess.pid, signal.SIGTERM)
    os.kill(pcapServerProcess.pid, signal.SIGTERM)


clientProcesses = []
startEvent = threading.Event()

def launch_clients(secondHost, client, serverIp, ports):
    f = timeStart = time.time()

    clientProcesses.append(
        secondHost.popen(['sudo', '-u', USER, SCHEME_PATH, client, serverIp, ports[0]]))

    startEvent.set()

    for i in range(1, FLOWS):
        sleep(INTERVAL_SEC - ((time.time() - timeStart) % INTERVAL_SEC))

        clientProcesses.append(
            secondHost.popen(['sudo', '-u', USER, SCHEME_PATH, client, serverIp, ports[i]]))

    print(time.time()-f)


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


def launch_servers(firstHost, server):
    serverPorts     = []
    serverProcesses = []

    for i in range(0, FLOWS):
        serverPort    = getFreePort()
        serverProcess = firstHost.popen(['sudo', '-u', USER, SCHEME_PATH, server, serverPort])

        serverPorts    .append(serverPort)
        serverProcesses.append(serverProcess)

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
    sleep(1)
    thread = threading.Thread(target = launch_clients, args = (secondHost, client, serverIp, ports))
    thread.start()
    startEvent.wait()
    sleep(deltasSec[0])

    for i in range(1, len(deltasSec)):
        timeStart = time.time()

        firstHost. cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                      (firstIntf,  delaysUsec[i], JITTER_USEC, RATE_MBITS))

        secondHost.cmd('tc qdisc change dev %s root netem delay %dus %dus rate %sMbit' %
                      (secondIntf, delaysUsec[i], JITTER_USEC, RATE_MBITS))

        sleep(max(0, deltasSec[i] - (time.time() - timeStart)))

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

    for i in deltasSec[1:]:
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
    random.seed(1)

    topo = NetworkTopo()    
    net  = Mininet(topo=topo)

    subprocess.call([SCHEME_PATH, 'setup_after_reboot'])

    deltasSec, delaysUsec = generate_steps()

    run_test(net['h1'], net['h2'], deltasSec, delaysUsec)
    #CLI(net)
