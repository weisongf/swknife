#!/usr/bin/env bash

# Description:
#   Setup environment for running on RHEL/Ubuntu.
#
# History:
#   v1.0    2019-12-02  yuxin.sun     init version
#   v1.1    2019-12-30  charles.shih  install gnuplot
#   v1.2    2020-01-02  charles.shih  install sysstat
#   v1.3    2020-01-02  charles.shih  install psmisc
#   v1.3.1  2020-01-03  charles.shih  fix a typo

# Get system info
OS-RELEASER=$(cat /etc/os-release |egrep "^ID="|awk -F"=" '{print$2}')
if [[ x$OS-RELEASER == x'ubuntu' ]];then

    apt install -y libaio-devel fio gnuplot
    apt install -y sysstat psmisc python3-yaml python3-pandas python3-click python3-numpy python3-scipy
    
    # ubuntu default dash
    sudo rm /bin/sh 
    sudo ln -s /bin/bash /bin/sh

elif [[ x$OS-RELEASER == x'centos' ]]; then
		#statements	
    project=$(cat /etc/redhat-release | grep -Po 'release \K[0-9]*')
    echo "Setup block test environment in RHEL-$project..."
    
    # Install fio
    yum install -y libaio-devel fio gnuplot
    
    # Install sysstat (sar)
    yum install -y sysstat
    systemctl enable --now sysstat
    
    # Install other pacages (killall)
    yum install -y psmisc
    
    # Install Python runtime
    if [[ x$project == x'7' ]]; then
        yum install -y python python-yaml
        pip install click pandas numpy scipy
    elif [[ x$project == x'8' ]]; then
        yum install -y python3 python3-yaml
        ln -s /usr/bin/python3 /usr/bin/python
        pip3 install click pandas numpy scipy
    else
        echo "RHEL-$project is not supported!"
        exit 1
    fi

fi
echo "Setup finished!"
exit 0
