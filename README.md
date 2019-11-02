# CoCo-Beholder: Testing Congestion Control Schemes

CoCo-Beholde was ensured to work with Python 2.7, 3.5, 3.6, and 3.7. 
CoCo-Beholder installation script `install.sh` installs Python 2 library 
dependencies by default. For Python 3, please, comment out the corresponding 
lines in the installation script.

## Installation

The installation process is as following:

* Install Pantheon collection of congestion control schemes and, if needed, 
[add](#adding-a-new-scheme) more schemes to the collection

* Install CoCo-Beholder using its installation script

* Done. [Test](#testing) the schemes in the collection using CoCo-Beholder.

CoCo-Beholder installation scipt `install.sh` is super easy and short. However, 
due to the facts that there are bugs in the operating systems and that some 
schemes fail to get installed properly, the above described installation 
process is not always simple. Please, cosider the detailed instructions for 
[Ubuntu 16.04](#installation-on-ubuntu-1604-lts), 
[Ubuntu 18.04](#installation-on-ubuntu-1804-lts), and
[Debian 10](#installation-on-debian-10).

### Installation on Ubuntu 16.04 LTS

The instructions below were tested on the VM with a fresh install of Ubuntu 
16.04.6-desktop-amd64 (Nov. 2019).

* As a general note: if you need TCP BBRv1.0 scheme make sure to use Linux 
kernels >=4.9.

* Fresh releases of 16.04 LTS (16.04.5 and higher) provide Linux kernel 
4.15 with HWE. The information on Ubuntu kernels and HWE can be found 
[here](https://wiki.ubuntu.com/Kernel/LTSEnablementStack). 
CoCo-Beholder [uses](#testing) **tc qdisc netem jitter**, and the feature is 
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

* Fresh releases of 18.04 LTS (18.04.3 and higher) provide Linux kernel 
5.0 with HWE. This is okay and we switch to the next step at once.

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

## Testing

## Adding a new scheme

## Dependencies to install
  
- ### [**Pantheon**](https://github.com/StanfordSNR/pantheon)

  **IMPORTANT!**
Before testing the third-party schemes present in Pantheon using the 
Variable-Delay tool, it is crucial not only to install dependencies of the 
schemes using `src/experiments/setup.py --install-deps` command but also to set 
up the schemes using `src/experiments/setup.py --setup` command. Without the 
setup, some schemes can work in a wrong way. For example, the scheme *quic* 
installs necessary certificates into the OS during the setup – without the 
certificates, *quic* traffic will not start to flow between client and server 
due to invalid certificate error. It is enough to run the two commands once on 
a user's machine.
   
  At the same time, there is no need to run `src/experiments/setup.py` 
command (without `--setup`) on every reboot because the Variable-Delay tool 
runs the command for all the schemes to be tested as it is. 
    
- ### [**Mininet**](https://github.com/mininet/mininet)

  The point-to-point topology is built with Mininet. Launching clients and 
servers of schemes, launching tcpdump recording, changing tc qdisc netem 
settings for host interfaces, and etc. is done using Mininet popen API. Mininet 
controllers and switches are _not_ used and so the network is _not_ started up 
in terms of Mininet, as there is no need for it.

