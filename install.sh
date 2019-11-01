#!/usr/bin/env bash

sudo apt-get -y install net-tools ethtool iproute2 tcpdump lsof procps

#
# For Python 2:
#
sudo apt-get -y install python-pip
sudo pip install ipaddress pyyaml dpkt matplotlib numpy
#
# More exactly:
#
# sudo pip install ipaddress==1.0.22 pyyaml==5.1.2 dpkt==1.9.2 matplotlib==2.1.1 numpy==1.16.4
#
# For Python 3:
#
# sudo apt-get -y install python3-pip
# sudo pip3 install pyyaml dpkt matplotlib numpy
#
# More exactly:
#
# sudo pip3 install pyyaml==5.1.2 dpkt==1.9.2 matplotlib==3.0.3 numpy==1.16.4
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd)"

pushd "$script_dir" > /dev/null || exit 1

make -C variable_delay/third_party/mininet

popd > /dev/null
