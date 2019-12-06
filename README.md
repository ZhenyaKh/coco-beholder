# CoCo-Beholder: Highly-Customizable Testing of Congestion Control Algorithms
```

                           ----    0-TH SEC:    ----
<--------------------------|  |                 |  |<-------------------CUBIC
                           |  |      500ms      |  |
CUBIC--------------------->|  |      ^^^^^5ms   |  |------------------------>
                           |  |  10ms|   |      |  |
                           |  |---120Mbps,20ms--|  |
                           |  |                 |  |
                           |  |    15-TH SEC:   |  |
VEGAS---120Mbps,2000pkts-->|  |                 |  |--120Mbps,5ms,3000pkts-->
                           |  |                 |  |
VEGAS---120Mbps,2000pkts-->|  |                 |  |--120Mbps,5ms,3000pkts-->
                           ----     30 SECS     ----
                    
```                
CoCo-Beholder is a human-friendly virtual network  emulator providing the 
popular dumbbell topology of any size. Each link of the topology may have 
individual  rate, delay, and queue size. The central link may also have a 
variable delay with optional jitter. Flows of different schemes may run together 
in the topology for a specified runtime of seconds. For each flow, the direction 
and the starting second of the runtime  can be chosen.

Each flow has a host in the left half and a host in the right half of the 
topology and the hosts exchange a scheme's traffic with one host being the 
sender and one being the receiver. There is the left router that interconnects 
all the hosts in the left half and the right router that interconnects all the 
hosts in the right half of the topology. All the flows share the common central 
link between the two routers.

## Testing

This command specifies the path to the [collection](#installation) containing 
the schemes to test and launches the testing for 30 seconds, with the central 
link having 120  Mbps rate and the variable delay with the base delay 20 ms, 
delta 500 ms, step 10 ms, jitter 5 ms.

```bash
./run.py -p ~/pantheon 20ms 0.5s 10ms 5ms -t 30 -r 120 -s 12345
```

If this is the first run of the script, the default layout file `layout.yml` is
generated, as shown below. The resulting testing setup is present in the 
[drawing](#coco-beholder-highly-customizable-testing-of-congestion-control-algorithms) 
of the dumbbell topology at the top of this page. The layout file can be edited 
to get much more complex testing setups with more flows belonging to various 
schemes and having diverse network settings.

```yaml
# Delays/rates are optional: if lacking or null, they are set to 0us/0.0
# and for netem, to set delay/rate to zero is same as to leave it unset.
# Sizes of queues are optional: if lacking or null, they are set to 1000.
- direction: <-
  flows: 1
  left-delay: null
  left-queues: null
  left-rate: null
  right-delay: null
  right-queues: null
  right-rate: null
  scheme: cubic
  start: 0
- direction: ->
  flows: 2
  left-delay: 0us
  left-queues: 2000
  left-rate: 120.0
  right-delay: 5ms
  right-queues: 3000
  right-rate: 120
  scheme: vegas
  start: 15
- direction: ->
  flows: 1
  scheme: cubic
  start: 0
```

The rate, delay, and queue size are always installed **at both the interfaces** 
at the ends of each link in the topology using `tc` qdisc NetEm link emulator. 
In particular, this means that the RTT of a link is twice the (one-way) delay. 
Only the central link may have two different queue sizes of the interfaces at 
its ends -- see `-q1`, `-q2`, `-q` arguments in the help message of the script.
By default, both the queues are of 1000 packets.

The variable delay at the central link is defined by four positional arguments:
the base delay, delta, step, and jitter, where the jitter can be skipped. Each
delta time, the delay is increased or decreased by step depending on a 
pseudorandom generator, whose seed can be specified with `-s` argument or is 
assigned the current UNIX time. To have a constant delay at the central link, 
choose the delta >= the runtime `-t`.

Into a chosen output directory, `metadata.json` file is written containing
**all** the parameters of the test, including the generator seed. The file may 
be fed to CoCo-Beholder in the future to fully reproduce the test. Also, during 
the testing, PCAP dump files are recorded at all the hosts of the dumbbell 
topology into the output directory using `tcpdump`. So for the example in the
[drawing](#coco-beholder-highly-customizable-testing-of-congestion-control-algorithms),
eight PCAP dump files were recorded.

Note: the maximum delay at both the side links and the central link (jitter not 
counted) can be specified with `-m` option. To have a square-wave delay at the 
central link, set the maximum delay to the sum of the base delay and step.

## Installation

The installation process is as following:

* Install Pantheon collection of congestion control schemes and, if needed, 
[add](#adding-a-new-scheme) more schemes to the collection

* Install CoCo-Beholder emulator using its installation script

* Done. [Test](#testing) the schemes in the collection using CoCo-Beholder.

Installing CoCo-Beholder itself is always trivial because its installation 
scipt `install.sh` is super easy and short. However, installing the collection 
of the schemes often causes lots of problems. Also, there are troublesome 
bugs in some operating systems. Thus, please, see the detailed instructions for 
[Ubuntu 16.04](#installation-on-ubuntu-1604-lts), 
[Ubuntu 18.04](#installation-on-ubuntu-1804-lts), and
[Debian 10](#installation-on-debian-10).

### Installation on Ubuntu 16.04 LTS

The instructions below were tested on the VM with a fresh install of Ubuntu 
16.04.6-desktop-amd64 (Nov. 2019).

* As a general note: if you need bbr (TCP BBRv1.0) scheme make sure to use 
Linux kernel >=4.9.

* Fresh releases of 16.04 LTS (16.04.5 and higher) come with Linux kernel 4.15. 
CoCo-Beholder uses **tc qdisc netem jitter**, and the feature is 
[broken](https://bugs.launchpad.net/bugs/1783822) on Ubuntu kernel 4.15. The 
solution:

  * Please, install 4.13 kernel to have the jitter:

   ```bash
   sudo apt-get install linux-image-4.13.0-39-generic linux-headers-4.13.0-39 \
   linux-headers-4.13.0-39-generic linux-image-extra-4.13.0-39-generic
   ```
  * In file `/etc/default/grub`, comment out the line `GRUB_HIDDEN_TIMEOUT=0` 
  and run the command `sudo update-grub`. This will allow you to see Grub menu 
  after the reboot.

  * Reboot and in Grub menu, choose `Advanced options for Ubuntu` and 
  there `Ubuntu, with Linux 4.13.0-39-generic`. Check the running kernel with 
  the command `uname -ar`.

* Download Pantheon git repository and git submodules of the included schemes:

```bash
git clone https://github.com/StanfordSNR/pantheon.git && cd pantheon
git submodule update --init --recursive
```

* Prevent Pantheon from applying the patches 
[reducing MTU](https://pantheon.stanford.edu/faq/#tunnel) of some schemes:

```bash
rm -r src/wrappers/patches
```

* The installation of Pantheon and of the included schemes is described 
[here](https://github.com/StanfordSNR/pantheon#dependencies).
You can skip the installation of Pantheon itself (with  its 
`tools/install_deps.sh` script). You need to install only the schemes using the 
commands below. If the last command gives you an error like 
`Command "python setup.py egg_info" failed with error code 1...`, then execute 
`sudo pip install --upgrade pip` and repeat the failed command.

```bash
sudo apt-get install autoconf                              # for verus
sudo apt-get install nodejs-legacy                         # for webrtc
sudo apt-get install python-pip && sudo pip install pyyaml # for setup.py

src/experiments/setup.py --install-deps (--all | --schemes "<cc1> <cc2> ...")
src/experiments/setup.py --setup (--all | --schemes "<cc1> <cc2> ...")
``` 

* Leave Pantheon git repository, download CoCo-Beholder git repository, and run 
CoCo-Beholder installation script:

```bash
cd coco-beholder && sudo ./install.sh
```

Now you are ready to [test](#testing) the schemes.

### Installation on Ubuntu 18.04 LTS

The instructions below were tested on the VM with a fresh install of Ubuntu 
18.04.3-desktop-amd64 (Nov. 2019).

* As a general note: if you need bbr (TCP BBRv1.0) scheme make sure to use 
Linux kernel >=4.9.

* As explained [here](#installation-on-ubuntu-1604-lts), Ubuntu kernel 4.15 
does **not** suit. With Ubuntu >=18.04.3, you get kernel >=5.0 so, please, 
proceed to the next step.

* Download Pantheon git repository and git submodules of the included schemes:

```bash
git clone https://github.com/StanfordSNR/pantheon.git && cd pantheon
git submodule update --init --recursive
```

* Prevent Pantheon from applying the patches 
[reducing MTU](https://pantheon.stanford.edu/faq/#tunnel) of some schemes:

```bash
rm -r src/wrappers/patches
```

* The installation of Pantheon and of the included schemes is described 
[here](https://github.com/StanfordSNR/pantheon#dependencies).
You can skip the installation of Pantheon itself (with  its 
`tools/install_deps.sh` script). You need to install only the schemes using the 
commands below.

```bash
sudo apt-get install autoconf                              # for verus
sudo apt-get install python-pip && sudo pip install pyyaml # for setup.py

src/experiments/setup.py --install-deps (--all | --schemes "<cc1> <cc2> ...")
src/experiments/setup.py --setup (--all | --schemes "<cc1> <cc2> ...")
``` 

* Leave Pantheon git repository, download CoCo-Beholder git repository, and run 
CoCo-Beholder installation script:

```bash
cd coco-beholder && sudo ./install.sh
```

Now you are ready to [test](#testing) the schemes.

### Installation on Debian 10

The instructions below were tested on the VM with a fresh install of Debian 
10.1.0-amd64-netinst (Nov. 2019).

* As a general note: if you need bbr (TCP BBRv1.0) scheme make sure to use 
Linux kernel >=4.9.

* Note that Ubuntu kernel 4.15 has a significant bug, as explained 
[here](#installation-on-ubuntu-1604-lts). It is not clear if Debian kernel 4.15 
has this issue. Anyway, with Debian >=10.1.0, you get kernel >=4.19 so, please, 
proceed to the next step.

* Download Pantheon git repository and git submodules of the included schemes:

```bash
git clone https://github.com/StanfordSNR/pantheon.git && cd pantheon
git submodule update --init --recursive
```

* Prevent Pantheon from applying the patches 
[reducing MTU](https://pantheon.stanford.edu/faq/#tunnel) of some schemes:

```bash
rm -r src/wrappers/patches
```

* The installation of Pantheon and of the included schemes is described 
[here](https://github.com/StanfordSNR/pantheon#dependencies).
You can skip the installation of Pantheon itself (with  its 
`tools/install_deps.sh` script). You need to install only the schemes. First, 
install the dependencies of the schemes:

``` bash
sed -i 's/chromium-browser/chromium/g' src/wrappers/webrtc.py # for webrtc
sudo apt-get install python-pip && sudo pip install pyyaml    # for setup.py

src/experiments/setup.py --install-deps (--all | --schemes "<cc1> <cc2> ...")
```

* Add the string `export PATH=/usr/sbin:$PATH` to your `~/.bashrc` file and run 
the command `source ~/.bashrc`. This will enable `/usr/sbin/sysctl` utility, 
which is necessary not only during the installation but also later on.

* To build Verus, you need to downgrade your alglib library. So, please, add 
`deb <URL> stretch main` line to your `/etc/apt/sources.list` and run:

```bash
sudo apt-get update
sudo apt-get remove libalglib-dev             # remove  3.14 version
sudo apt-get install -t stretch libalglib-dev # install 3.10 version
```

* Now setup the schemes (build their source code, install certificates, etc.):

```bash
sudo apt-get install autoconf                             # for verus
myregex='s/milliseconds(\(.\+\))/milliseconds(int(\1))/g'    
sed -i $myregex third_party/verus/src/verus_client.cpp
sed -i $myregex third_party/verus/src/verus_server.cpp 

sudo apt-get install pkg-config                           # for sprout

sudo apt-get install libtinfo5                            # for quic
# During the setup, do not be afraid of CERTIFICATE_VERIFY_FAILED errors by quic

src/experiments/setup.py --setup (--all | --schemes "<cc1> <cc2> ...")
``` 

* Leave Pantheon git repository, download CoCo-Beholder git repository, and run 
CoCo-Beholder installation script:

```bash
cd coco-beholder && sudo ./install.sh

# matplotlib will give Python backports.functools_lru_cache error. To solve:
sudo pip install arrow==0.12.0
```

Now you are ready to [test](#testing) the schemes.

## Troubleshooting a scheme

* The first way is to launch a scheme on localhost without an emulator. This
enables to see the output of the scheme:

```bash
cd pantheon
src/wrappers/vegas.py setup_after_reboot # setup the scheme once after reboot
src/wrappers/vegas.py run_first          # who is server: sender or receiver
# receiver
src/wrappers/vegas.py receiver 54321         # start server in one shell
src/wrappers/vegas.py sender 127.0.0.1 54321 # start client in another shell
sudo pkill -9 -f vegas                       # kill all the started processes
```

* The second way is to make CoCo-Beholder show output of schemes. Change its 
source code, as shown below, and run schemes [as usual](#testing).

```bash
cd coco-beholder
myregex='s/(\(.\+\)).pid/(\1, stdout=None, stderr=None).pid/g'
sed -i "$myregex" variable_delay/src/test/test.py
```
## Adding a new scheme

If you want to test a scheme that is not present in Pantheon collection you can 
add it locally as following:

* Suppose you want to add TCP CDG. Check if the module is present in your kernel:

```bash
find /lib/modules/`(uname -r)`/kernel -type f -name *cdg*
# /lib/modules/4.19.0-6-amd64/kernel/net/ipv4/tcp_cdg.ko
```

* Add a new `cdg` entry to `pantheon/src/config.yml` file that keeps the list 
of all the schemes in the collection. The color, name, and marker can be any 
bacause CoCo-Beholder does not read them.

```yaml
  cdg:
    name: TCP CDG
    color: red
    marker: 'x'
```

* Create the wrapper for cdg scheme as a modified copy of, e.g., vegas wrapper:

```[bash]
cp pantheon/src/wrappers/vegas.py pantheon/src/wrappers/cdg.py
sed -i 's/vegas/cdg/g' pantheon/src/wrappers/cdg.py
```

Now you can [test](#testing) cdg with CoCo-Beholder as usual by specifying cdg 
flows in the layout file.

## Python Support

CoCo-Beholder is ensured to work with Python 2.7, 3.5, 3.6, and 3.7. 
CoCo-Beholder installation script `install.sh` installs Python 2 library 
dependencies by default. For Python 3, please, comment out the corresponding 
lines in the installation script.

## Third-party libraries

CoCo-Beholder utilizes [Mininet](https://github.com/mininet/mininet) library: 
the API that allows to create a virtual host as a UNIX shell in a separate 
network namespace, to create a veth pair link between a pair of virtual hosts, 
and  to launch processes at a virtual host. CoCo-Beholder does not use 
Controller, Switch, Topology, TCLink or other higher-level entities of Mininet.
To prevent any future compatability issues and to make the installation of 
CoCo-Beholder easier, the needed parts of Mininet 2.3.0d5 are included into
CoCo-Beholder repository as a third-party library according to Mininet license.