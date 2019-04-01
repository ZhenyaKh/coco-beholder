#!/usr/bin/python 

import os
import subprocess
import socket
import sys
from time import sleep
import time
import random

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
#
def run_test(firstHost, secondHost, scheme, schemePath, user):
    firstIntf, secondIntf = str(firstHost.intf()), str(secondHost.intf())

    firstHost.cmd ('tc qdisc delete dev %s root' % firstIntf)
    firstHost.cmd ('tc qdisc add dev %s root netem rate %sMbit delay %dms' % (firstIntf,  sys.argv[RATE_ARG], 30))

    secondHost.cmd('tc qdisc delete dev %s root' % secondIntf)
    secondHost.cmd('tc qdisc add dev %s root netem rate %sMbit delay %dms' % (secondIntf, sys.argv[RATE_ARG], 30))


    server, client       = whoIsServer(schemePath)
    serverIp, serverPort = firstHost.IP(firstIntf), getFreePort()

    serverDump = os.path.join(sys.argv[DIR_ARG], "%s-%s.pcap" % (scheme, server))
    clientDump = os.path.join(sys.argv[DIR_ARG], "%s-%s.pcap" % (scheme, client))

    cmd = 'tcpdump -tt -nn -i %s  -Z  %s -w  %s '\
          'host 10.0.0.1 and host 10.0.0.2 and not arp and not icmp and not icmp6'
          
    firstHost. popen(cmd % (firstIntf,  user, serverDump), stdout = None)
    secondHost.popen(cmd % (secondIntf, user, clientDump), stdout = None)

    sleep(1)
    firstHost .popen(" ".join(['sudo -u', user, schemePath, server, serverPort]))
    sleep(1)
    secondHost.popen(" ".join(['sudo -u', user, schemePath, client, serverIp, serverPort]))

    #sleep(int(sys.argv[RUNTIME_ARG]))
    runtimeSecs = int(sys.argv[RUNTIME_ARG])
    deltaMsecs  = 500
    x = runtimeSecs * 1000 / deltaMsecs
    k = 30
    for i in range(0, x):
        sleep(deltaMsecs / 1000.0)
        print(time.time(), "%%%")
        if bool(random.getrandbits(1)):
            k+=10
        else:
            k-=10
        print(k)
        firstHost.cmd(
            'tc qdisc change dev %s root netem rate %sMbit delay %dms' % (firstIntf, sys.argv[RATE_ARG], k))
        secondHost.cmd(
            'tc qdisc change dev %s root netem rate %sMbit delay %dms' % (secondIntf, sys.argv[RATE_ARG], k))
        print(time.time(), "###")




    firstHost.cmd('pkill -f', schemePath)
    firstHost.cmd('pkill -f', os.path.join(sys.argv[PANTHEON_ARG], THIRD_PARTY_DIR))
    firstHost.cmd('killall tcpdump')


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

    run_test(net['h1'], net['h2'], scheme, schemePath, sys.argv[USER_ARG])
    CLI(net)
