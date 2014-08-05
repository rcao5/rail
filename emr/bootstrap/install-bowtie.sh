#!/bin/bash

# install-bowtie.sh
#
# Install bowtie version 1.0.1 as of now.

set -e

wget http://downloads.sourceforge.net/project/bowtie-bio/bowtie/1.1.0/bowtie-1.1.0-linux-x86_64.zip || { echo 'wget failed' ; exit 1; }
unzip bowtie-1.1.0-linux-x86_64.zip || { echo 'unzip failed' ; exit 1; }
export PATH=$PATH:~/bowtie-1.1.0