#!/bin/bash

echo "installing dependencies"
sudo apt-get install -y paraview-python
sudo apt-get install -y python-docopt

grep 'snappy' ~/.bashrc > /dev/null
if [ $? == 1 ]; then
    echo "setting path variable"
    echo 'export PATH=$PATH:'$PWD >> ~/.bashrc
fi
