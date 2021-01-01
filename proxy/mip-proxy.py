#!/usr/bin/env python3

#
# MusicIP <-> LMS proxy
#
# Copyright (c) 2020-2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse
import json
import os
import sys
from urllib.parse import quote
import urllib.request

from twisted.web import server, resource
from twisted.internet import reactor


config={}

def debug(s):
    global config
    if config['debug']:
        print("INFO: %s" % s)


def warning(s):
    print("WARNING: %s\n" % s)


def error(s):
    print("ERROR: %s\n" % s)
    exit(-1)


def fixPaths(data, frm, to):
    if data:
        global config
        showDebug=False
        if config['debug'] and len(data)<256:
            showDebug=True
            debug("FROM:%s" % data.decode("utf-8"))

        # Cue file hack support?
        if 'cue' in config and config['cue']:
            if frm=='mip':
                resp=[]
                for line in data.split(b'\n'):
                    orig=line.decode("utf-8")
                    line=line.replace(config['paths']['std'][frm], config['paths']['std'][to])
                    # /path/file.m4a.CUE_TRACK.start-stop.mp3 -> /path/file.m4a#start-stop
                    if b'.CUE_TRACK.' in line:
                        addprefix = False
                        if line.startswith(b'file '):
                            line=line[5:].replace(b'.CUE_TRACK.', b'#').replace(b'.mp3', b'')
                            addprefix = True
                        else:
                            line=line.replace(b'.CUE_TRACK.', b'#').replace(b'.mp3', b'')
                        parts=line.split(b'#')
                        line=b'file://'+str.encode(quote(parts[0]))+b'#'+parts[1]
                        if addprefix:
                            line=b'file '+line
                    else:
                        for t in config['types']:
                            line=line.replace(t[frm], t[to])
                        dest=line.decode("utf-8")
                        if len(dest)>3 and not os.path.exists(dest):
                            warning("%s does not exist. MIP:%s" % (dest, orig))
                    resp.append(line)
                data=b'\n'.join(resp)
            else:
                data=data.replace(config['paths']['enc'][frm], config['paths']['enc'][to])
                pos=data.find(b'%23')
                if pos>0:
                    # Replace file:///path/file.m4a#from-to&param with /path/file.m4a.CUE_TRACK.from-to.mp3&param
                    amp=data.find(b'&', pos)
                    if amp>0:
                        data=data[:pos]+b'.CUE_TRACK.'+data[pos+3:amp]+b'.mp3'+data[amp:]
                    else:
                        data=data[:pos]+b'.CUE_TRACK.'+data[pos+3:]+b'.mp3'
                    data=data.replace(b'file%3A%2F%2F', b'')
                else:
                    for t in config['types']:
                        data=data.replace(t[frm], t[to])
                data=data.replace(b'%2520', b'%20')
        else:
            for t in config['types']:
                data=data.replace(t[frm], t[to])
            data=data.replace(config['paths']['std'][frm], config['paths']['std'][to])
            data=data.replace(config['paths']['enc'][frm], config['paths']['enc'][to])
        if showDebug:
            debug("TO:%s" % data.decode("utf-8"))
    return data


class MipServer(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        global config
        debug("Request '%s'" % request.uri.decode("utf-8"))
        try:
            resp=urllib.request.urlopen('http://%s:%d%s' % (config['mip']['host'], int(config['mip']['port']), fixPaths(request.uri, 'lms', 'mip').decode("utf-8"))).read()
            return fixPaths(resp, 'mip', 'lms')
        except urllib.error.HTTPError as e:
            request.setResponseCode(e.code)
            return e.read()


def main():
    global config
    parser = argparse.ArgumentParser(description='MusicIP Proxy')
    parser.add_argument('-c', '--config', type=str, help='Config file (default: config.json)', default='config.json')
    args = parser.parse_args()
    port=10003
    mip=None

    if not os.path.exists(args.config):
        error("%s does not exist" % args.config)
    try:
        with open(args.config, 'r') as configFile:
            config = json.load(configFile)
    except ValueError:
        error("Failed to parse config file")
    except IOError:
        error("Failed to read config file")
 
    config['types']=[]
    for t in config['transcode']:
        config['types'].append({'mip':bytes(".%s.mp3" % t, 'utf-8'), 'lms':bytes(".%s" % t, 'utf-8')})
    config['paths']={'std':{'mip':bytes(config['paths']['mip'].replace('//', '/'), 'utf-8'), 
                            'lms':bytes(config['paths']['lms'].replace('//', '/'), 'utf-8')}}
    config['paths']['enc']={'lms':config['paths']['std']['lms'].replace(bytes('/', 'utf-8'), bytes('%2F', 'utf-8')),
                            'mip':config['paths']['std']['mip'].replace(bytes('/', 'utf-8'), bytes('%2F', 'utf-8'))}
    srv = server.Site(MipServer())
    debug("Listening on: %d" % port)
    reactor.listenTCP(port, srv)
    reactor.run()


if __name__ == "__main__":
    main()
