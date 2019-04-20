# Variable-Delay: Testing Congestion Control Schemes

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
