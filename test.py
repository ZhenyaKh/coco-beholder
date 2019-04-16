#!/usr/bin/python 

import os
import signal
import subprocess
import socket
import sys
import random
import time
from time import sleep

from mininet.topo import Topo
from mininet.net  import Mininet
from mininet.log  import setLogLevel, info
from mininet.cli  import CLI

USER_ARG        = 1
SCHEME_ARG      = 2
DIR_ARG         = 3
PANTHEON_ARG    = 4
RATE_ARG        = 5
RUNTIME_ARG     = 6
MAX_DELAY_ARG   = 7
BASE_ARG        = 8
DELTA_ARG       = 9
STEP_ARG        = 10
JITTER_ARG      = 11
WRAPPERS_PATH   = 'src/wrappers'
THIRD_PARTY_DIR = 'third_party'
FLOWS           = 100

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


def launch_clients(user, schemePath, secondHost, client, serverIp, serverPorts):
    clientProcesses = []

    for port in serverPorts:
        clientProcess = secondHost.popen(['sudo', '-u', user, schemePath, client, serverIp, port])
        clientProcesses.append(clientProcess)

    return clientProcesses


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


def launch_servers(user, schemePath, firstHost, server):
    serverPorts     = []
    serverProcesses = []

    for i in range(0, FLOWS):
        serverPort    = getFreePort()
        serverProcess = firstHost.popen(['sudo', '-u', user, schemePath, server, serverPort])

        serverPorts    .append(serverPort)
        serverProcesses.append(serverProcess)

    return serverProcesses, serverPorts


#        
# Function determines who runs first: the sender or the receiver of the scheme
# param [in] schemePath - the path of the scheme's wrapper in Pantheon
# returns sender and receiver in the order of running
#
def whoIsServer(schemePath):
    server = subprocess.check_output([schemePath, 'run_first']).strip()

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
# param [in] scheme     - the name of the scheme to test
# param [in] schemePath - the path of the scheme's wrapper in Pantheon
# param [in] user       - name of the OS user running the tests
# param [in] deltas     - array of delta times in seconds
# param [in] deltas     - array of delays in microseconds corresponding to the array of delta times
#
def run_test(firstHost, secondHost, scheme, schemePath, user, deltas, delays):
    firstIntf, secondIntf = str(firstHost.intf()), str(secondHost.intf())

    firstHost.cmd ('tc qdisc delete dev %s root' % firstIntf)
    firstHost.cmd ('tc qdisc add dev %s root netem delay %dus %sus rate %sMbit' %
                  (firstIntf,  delays[0], sys.argv[JITTER_ARG], sys.argv[RATE_ARG]))

    secondHost.cmd('tc qdisc delete dev %s root' % secondIntf)
    secondHost.cmd('tc qdisc add dev %s root netem delay %dus %sus rate %sMbit' %
                  (secondIntf, delays[0], sys.argv[JITTER_ARG], sys.argv[RATE_ARG]))

    server,   client   = whoIsServer(schemePath)
    serverIp, clientIp = firstHost.IP(firstIntf), secondHost.IP(secondIntf)

    serverDump = os.path.join(sys.argv[DIR_ARG], "%s-%s.pcap" % (scheme, server))
    clientDump = os.path.join(sys.argv[DIR_ARG], "%s-%s.pcap" % (scheme, client))

    cmd = 'tcpdump -tt -nn -i %s -Z %s -w %s '\
          'host %s and host %s and not arp and not icmp and not icmp6'

    pcapServerProcess = firstHost. popen(cmd % (firstIntf,  user, serverDump, serverIp, clientIp))
    pcapClientProcess = secondHost.popen(cmd % (secondIntf, user, clientDump, serverIp, clientIp))

    serverProcesses, serverPorts = launch_servers(user, schemePath, firstHost, server)
    sleep(1)
    clientProcesses = launch_clients(user, schemePath, secondHost, client, serverIp, serverPorts)

    sleep(deltas[0])

    for i in range(1, len(deltas)):
        timeStart = time.time()

        firstHost. cmd('tc qdisc change dev %s root netem delay %dus %sus rate %sMbit' %
                      (firstIntf,  delays[i], sys.argv[JITTER_ARG], sys.argv[RATE_ARG]))

        secondHost.cmd('tc qdisc change dev %s root netem delay %dus %sus rate %sMbit' %
                      (secondIntf, delays[i], sys.argv[JITTER_ARG], sys.argv[RATE_ARG]))

        sleep(max(0, deltas[i] - (time.time() - timeStart)))

    killProcesses(clientProcesses, serverProcesses, pcapClientProcess, pcapServerProcess)


#
# Function generates arrays of delta times and corresponding delays
# param [in] runtime  - the time during which the test should be run in total
# param [in] maxDelay - the maximum allowed delay which can be set for interfaces
# param [in] base     - the initial delay set for interfaces
# param [in] delta    - the time period after which delay is changed by specific step
# param [in] step     - the step by which delay is changed each delta time period
# returns arrays of delta times in seconds and corresponding delays in microseconds
#
def generate_steps(runtime, maxDelay, base, delta, step):
    runtime       = int(runtime) * int(1e6)
    delta         = int(delta)
    deltasNumber  = runtime / delta
    reminderDelta = runtime % delta
    deltas        = [ float(delta) / 1e6 ] * deltasNumber

    if reminderDelta != 0:
        deltas = deltas + [ float(reminderDelta) / 1e6 ]

    delay    = int(base)
    delays   = [ delay ]
    step     = int(step)
    maxDelay = int(maxDelay)

    if delay + step > maxDelay and delay - step < 0:
        sys.exit("Schedule of delay changes cannot be generated because step is too big")

    for delta in deltas[1:]:
        signs = []

        if delay + step <= maxDelay:
            signs = signs + [ 1 ]
        if delay - step >= 0:
            signs = signs + [-1 ]

        delay  += step * random.choice(signs)
        delays += [ delay ]

    return deltas, delays


#
# Entry function
#
if __name__ == '__main__':
    #setLogLevel('info')
    random.seed(1)
    scheme = sys.argv[SCHEME_ARG]

    topo = NetworkTopo()    
    net  = Mininet(topo=topo)

    schemePath = os.path.join(sys.argv[PANTHEON_ARG], WRAPPERS_PATH, scheme + '.py')
    subprocess.call([schemePath, 'setup_after_reboot'])

    deltas, delays = generate_steps(sys.argv[RUNTIME_ARG], sys.argv[MAX_DELAY_ARG],
                                    sys.argv[BASE_ARG], sys.argv[DELTA_ARG], sys.argv[STEP_ARG])

    run_test(net['h1'], net['h2'], scheme, schemePath, sys.argv[USER_ARG], deltas, delays)
    #CLI(net)
