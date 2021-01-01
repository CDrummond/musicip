#!/usr/bin/env python3

#
# Print contents of MusicIP analyser processed albums file
#
# Copyright (c) 2020-2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request


config={}

def readProcessedAlbums():
    global config
    try:
        with open(config['files']['processed'], 'r') as f:
            return json.load(f)
    except Exception as e:
        return []


def main():
    global config
    parser = argparse.ArgumentParser(description='Read MusicIP File Analyser processed file')
    parser.add_argument('-c', '--config', type=str, help='Config file (default: config.json)', default='config.json')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        error("%s does not exist" % args.config)
    try:
        with open(args.config, 'r') as configFile:
            config = json.load(configFile)
    except ValueError:
        error("Failed to parse config file")
    except IOError:
        error("Failed to read config file")

    processedAlbums=readProcessedAlbums()
    i=1
    for album in processedAlbums:
        print("[%d] %s" % (i, album))
        i+=1


if __name__ == "__main__":
    main()
