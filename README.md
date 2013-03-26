Nexel
=====

Python based RESTful web-service to create and launch remote virtual
machine sessions using the Nectar cloud, connecting to data housed at the
Australian Synchrotron

Jarrod Sinclair, VPAC/VeRSI
(jsinclair@vpac.org)

Usage:

- start web-service daemon: nexeld /path/to/settings.conf
- command-line interface: nexelcl --help
- web-service access: curl -X GET|POST|PUT|DELETE http://localhost:8888/...

Python requirements:

- Python 2.6+

Required Python packages:

- Tornado 2.4.1+ (http://www.tornadoweb.org/)
- Paramiko 1.9.0+ (http://www.lag.net/paramiko/)
- PyCrypto 2.5+ (https://www.dlitz.net/software/pycrypto/)
- FormEncode 1.2.6+ (http://www.formencode.org/)
- Requests 1.0.2+ (http://www.python-requests.org/)

Optional Python packages:

- Pyinotify 0.9.4+ (https://github.com/seb-m/pyinotify)

Installation
------------

On Centos 6.3 (as root):

1. Ensure pip is installed: easy_install pip
2. Ensure git, gcc and python dev are installed: yum install -y git gcc python-devel
3. Install Nexel from GitHub: pip install git+https://github.com/AustralianSynchrotron/nexel

On Ubuntu 12.10 (as user):

1. sudo apt-get update
2. sudo apt-get -y install python-pip
3. sudo apt-get -y install git
4. sudo pip install git+https://github.com/AustralianSynchrotron/nexel

TODO:

- Logging of launched instances with username/email for uptake tracking
- Install binaries "nexeld" (daemon) and "nexel" (shell)
- Timeouts inside of build.conf and boot.conf

