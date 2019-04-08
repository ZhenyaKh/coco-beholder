#!/usr/bin/python 

import os
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

    server, client       = whoIsServer(schemePath)
    serverIp, serverPort = firstHost.IP(firstIntf), getFreePort()

    serverDump = os.path.join(sys.argv[DIR_ARG], "%s-%s.pcap" % (scheme, server))
    clientDump = os.path.join(sys.argv[DIR_ARG], "%s-%s.pcap" % (scheme, client))

    cmd = 'tcpdump -tt -nn -i %s -Z %s -w %s '\
          'host 10.0.0.1 and host 10.0.0.2 and not arp and not icmp and not icmp6'

    firstHost. popen(cmd % (firstIntf,  user, serverDump), stdout = None)
    secondHost.popen(cmd % (secondIntf, user, clientDump), stdout = None)

    sleep(1)
    firstHost .popen(" ".join(['sudo -u', user, schemePath, server, serverPort]))
    sleep(1)
    secondHost.popen(" ".join(['sudo -u', user, schemePath, client, serverIp, serverPort]))
    f = time.time()
    sleep(deltas[0])

    for i in range(1, len(deltas)):
        timeStart = time.time()

        #print(firstHost. cmd('tc qdisc show dev h1-eth0'))
        #print(secondHost.cmd('tc qdisc show dev h2-eth0'))
        #print("========")

        firstHost. cmd('tc qdisc change dev %s root netem delay %dus %sus rate %sMbit' %
                      (firstIntf,  delays[i], sys.argv[JITTER_ARG], sys.argv[RATE_ARG]))

        secondHost.cmd('tc qdisc change dev %s root netem delay %dus %sus rate %sMbit' %
                      (secondIntf, delays[i], sys.argv[JITTER_ARG], sys.argv[RATE_ARG]))

        sleep(max(0, deltas[i] - (time.time() - timeStart)))
    print(time.time() - f)

    firstHost.cmd('pkill -f', schemePath)
    firstHost.cmd('pkill -f', os.path.join(sys.argv[PANTHEON_ARG], THIRD_PARTY_DIR))
    firstHost.cmd('killall tcpdump')


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

    scheme = sys.argv[SCHEME_ARG]

    topo = NetworkTopo()    
    net  = Mininet(topo=topo)

    schemePath = os.path.join(sys.argv[PANTHEON_ARG], WRAPPERS_PATH, scheme + '.py')
    subprocess.call([schemePath, 'setup_after_reboot'])

    deltas, delays = generate_steps(sys.argv[RUNTIME_ARG], sys.argv[MAX_DELAY_ARG],
                                    sys.argv[BASE_ARG], sys.argv[DELTA_ARG], sys.argv[STEP_ARG])

    run_test(net['h1'], net['h2'], scheme, schemePath, sys.argv[USER_ARG], deltas, delays)
    #CLI(net)
