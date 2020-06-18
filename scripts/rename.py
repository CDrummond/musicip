#!/usr/bin/env python3

#
# Rename folders/files for MusicIP
#
# Copyright (c) 2020 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import os
import subprocess

CHARS=['"', ':', '?']

def process(path):
    if os.path.isdir(path):
        for p in sorted(os.listdir(path)):
            orig = p
            for c in CHARS:
                p=p.replace(c, '_')
            if p!=orig:
                print("RENAME %s to %s" % (os.path.join(path, orig), os.path.join(path, p)))
                os.rename(os.path.join(path, orig), os.path.join(path, p))
            process(os.path.join(path, p))


process('/path/to/Music')
