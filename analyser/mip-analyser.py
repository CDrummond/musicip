#!/usr/bin/env python3

#
# Analyse files with MusicIP
#
# Copyright (c) 2020 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse
import json
import operator
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request


FNULL = open(os.devnull, 'w')

config={}
db=None

def error(s):
    print("ERROR: %s\n" % s)
    exit(-1)


def shouldStopAfterCurrent():
    global config
    return os.path.exists(config['files']['stopa']) or os.path.exists(config['files']['stop'])


def shouldStop():
    global config
    return os.path.exists(config['files']['stop'])


def deleteStopFile():
    global config
    if os.path.exists(config['files']['stop']):
        os.remove(config['files']['stop'])
    if os.path.exists(config['files']['stopa']):
        os.remove(config['files']['stopa'])


def readProcessedAlbums():
    '''
    Read previous state
    '''
    global config
    try:
        with open(config['files']['processed'], 'r') as f:
            return json.load(f)
    except Exception as e:
        return []


def saveProcessedAlbums(processedAlbums):
    '''
    Save list of current processed albums, so that we know where to start
    from next time
    '''
    global config
    print("Save state (%d albums processed)" % len(processedAlbums))
    with open(config['files']['processed'], 'w') as f:
        json.dump(sorted(processedAlbums), f)


def cueTracks(album, track):
    '''
    Query LMS db to get the list of tracks in a queue file with their start and
    stop end times
    '''
    global config
    global db
    src = os.path.join(config['paths']['lms'], album, track)
    cursor = db.execute("select url, title from tracks where url like '%%%s#%%'" % urllib.parse.quote(src))
    tracks=[]
    for row in cursor:
        parts=row[0].split('#')
        if 2==len(parts):
            times=parts[1].split('-')
            if 2==len(times):
                tracks.append({'file':track, 'start':times[0], 'end':times[1], 'title':row[1]})
    return tracks


def getAlbumsToProcess(processedAlbums):
    '''
    Get a list of albums (and their tracks) that need to be processed. If an
    album is a Audio+CUE then each track will be a dict of title/start/end
    '''
    global config
    toProcess=[]
    for album in sorted(os.listdir(config['paths']['lms'])):
        d=os.path.join(config['paths']['lms'], album)
        if os.path.isdir(d):
            if not album in processedAlbums:
                tracks=[]
                for f in sorted(os.listdir(d)):
                    if f.endswith('.mp3') or f.endswith('.ogg') or f.endswith('.m4a') or f.endswith('.flac'):
                        if not os.path.exists(os.path.join(config['paths']['lms'], album, f.rsplit('.', 1)[0]+'.cue')):
                            tracks.append(f)
                        elif len(tracks)==0 and db is not None:
                            parts = cueTracks(album, f)
                            if len(parts)>0:
                                for p in parts:
                                    tracks.append(p)
                                break

                if len(tracks)>0:
                    toProcess.append({'name':album, 'tracks':tracks})
                    print("[%d] %s (%d)" % (len(toProcess), album, len(tracks)))
    return toProcess


def createDir(d):
    if not os.path.exists(d):
        os.makedirs(d)


def shouldTranscode(path):
    '''
    Determine if a track needs to be transcoded. Currently all are, but in
    future should check if MP3 has embedded cover or numeric genre.
    '''
    return True
    # TODO: Improve this check to also check for images? Seems like MIP does not like some embedded images...
    #if path.endswith(".mp3"):
    #    for line in subprocess.check_output(["eyeD3", "--non-std-genres", path], stderr=subprocess.STDOUT).splitlines():
    #        l=str(line)
    #        if "WARNING: Non standard genre name:" in l:
    #            try:
    #                genre=int(l.split(":")[-1:][0].replace("'", "").strip())
    #                return True
    #            except Exception as e:
    #                # Genre is text, so does not need transcoding
    #                return False
    #                pass
    #    return False
    #return True

                    
def buildCommand(album, track):
    '''
    Build command to transcode a track to MP3
    '''
    global config
    dest=os.path.join(config['paths']['mip'], album['name'], track)
    src=os.path.join(config['paths']['lms'], album['name'], track)
    # MIP handles ogg and flac, so no transcode required
    if dest.endswith('.ogg') or dest.endswith('.flac'):
        if not os.path.exists(dest):
            os.symlink(src, dest)
        print("...%s (use symlink)" % track)
        return None

    # For m4a, opus, etc, we need to transcode to mp3 - so we'll use .m4a.mp3, etc.
    if not dest.endswith('.mp3'):
        dest+='.mp3'
    if os.path.exists(dest):
        print("...%s already transcoded" % track)
        return None
    if shouldTranscode(src):
        print("...%s" % track)
        return ['ffmpeg', '-hide_banner', '-loglevel', 'panic', '-i', src, '-b:a', '128k', dest]
    os.symlink(src, dest)
    print("...%s (use symlink)" % track)
    return None


def buildCueCommand(album, track):
    '''
    Build command to extract track from CUE
    '''
    global config
    src = os.path.join(config['paths']['lms'], album['name'], track['file'])
    dest = os.path.join(config['paths']['mip'], album['name'], '%s.CUE_TRACK.%s-%s.mp3' % (track['file'], track['start'], track['end']))
    if os.path.exists(dest):
        print("...%s (%s - %s) already split" % (track['file'], track['start'], track['end']))
        return None
    print("...%s (%s - %s) split" % (track['file'], track['start'], track['end']))
    end = float(track['end'])-float(track['start'])
    return ['ffmpeg', '-hide_banner', '-loglevel', 'panic', '-i', src, '-b:a', '128k', '-ss', track['start'], '-t', "%f" % end, dest]


def setCueTrackTitles(albums):
    global config
    procs=[]
    for album in albums:
        print('Setting titles "%s" (%d tracks)' % (album['name'], len(album['tracks'])))
        for track in album['tracks']:
            if shouldStop():
                return False
            if isinstance(track, dict):
                dest = os.path.join(config['paths']['mip'], album['name'], '%s.CUE_TRACK.%s-%s.mp3' % (track['file'], track['start'], track['end']))
                if os.path.exists(dest):
                    print("...%s (%s - %s) set title" % (track['file'], track['start'], track['end']))
                    procs.append(subprocess.Popen(['eyeD3', '-t', track['title'], '--remove-all-comments', '--remove-all-lyrics', '--remove-all-images', '--max-padding', '1', dest], stdout=FNULL, stderr=subprocess.STDOUT))
            if len(procs)>=config['threads']:
                for p in procs:
                    p.wait()
                procs=[]
    if len(procs)>0:
        for p in procs:
            p.wait()


def transcodeAlbums(albums):
    '''
    Transcode tracks from albums as required
    '''
    global config
    procs=[]
    cueAlbums=[]
    for album in albums:
        destDir = os.path.join(config['paths']['mip'], album['name'])
        createDir(destDir)
        print('Transcoding "%s" (%d tracks)' % (album['name'], len(album['tracks'])))
        isCue = isinstance(album['tracks'][0], dict)
        if isCue:
            cueAlbums.append(album)
        for track in album['tracks']:
            if shouldStop():
                return False
            command = buildCueCommand(album, track) if isCue else buildCommand(album, track)
            if command:
                procs.append(subprocess.Popen(command))
            if len(procs)>=config['threads']:
                for p in procs:
                    p.wait()
                procs=[]
    if len(procs)>0:
        for p in procs:
            p.wait()
    setCueTrackTitles(cueAlbums)
    return True


def removeTranscode(album):
    '''
    Remove transcoded tracks, no longer required
    '''
    global config
    destDir = os.path.join(config['paths']['mip'], album['name'])
    for track in os.listdir(destDir):
        os.remove(os.path.join(destDir, track))
    os.rmdir(destDir)


def stripTags(albums):
    '''
    Strip comments, lyrics, and images from MP3s. MIP seems to have issues with
    some of these.
    '''
    global config
    procs=[]
    for album in albums:
        print('Stripping tags from "%s" (%d tracks)' % (album['name'], len(album['tracks'])))
        for track in album['tracks']:
            if shouldStop():
                return False
            if isinstance(track, dict):
                continue
            file=track if track.endswith('.mp3') else (track+'.mp3')
            path = os.path.join(config['paths']['mip'], album['name'], file)
            print('...%s' % file)
            procs.append(subprocess.Popen(["eyeD3", "--remove-all-comments", "--remove-all-lyrics", "--remove-all-images", "--max-padding", "1", path], stdout=FNULL, stderr=subprocess.STDOUT))
            if len(procs)>=config['threads']:
                for p in procs:
                    p.wait()
                procs=[]
    if len(procs)>0:
        for p in procs:
            p.wait()
    return True


def write(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def waitForIdle():
    '''
    Wait for MIP to indicate it is idle
    '''
    while True:
        write('.')
        time.sleep(5)
        status=urllib.request.urlopen('http://localhost:10002/api/getStatus').read().strip()
        if b'idle' == status:
            return True
        if shouldStop():
            return False


def analyseAlbums(albums):
    '''
    Pass album paths to MIP, and then ask MIP to analyse tracks
    '''
    global config
    # As we can be transcoding whilst MIP is saving (due to mipcode check above) we need to
    # wait for MIP to be idle before adding more paths...
    try:
        write('\nWait for MIP')
        waitForIdle()
        for album in albums:
            if shouldStop():
                return False
            # Add album to MIP for analysis
            path=urllib.parse.quote_plus(os.path.join(config['paths']['mip'], album['name']))
            write('\nAdd "%s" to MIP' % album['name'])
            urllib.request.urlopen('http://localhost:10002/server/add?root=%s' % path).read()
            if not waitForIdle():
                write("cancelled\n")
                return False

        # Start analysis
        write("\nAnalysing")
        urllib.request.urlopen('http://localhost:10002/server/validate?action=Start+Validation')
        if not waitForIdle():
            write("cancelled\n")
            urllib.request.urlopen('http://localhost:10002/server/validate?action=Stop+Validation')
            return False
        write("\n")
        return True
    except:
        error("MIP no longer running?")


def handleAlbums(albums, processedAlbums):
    '''
    Handle a list of albums; transcode, strip tags, analyse
    '''
    if len(albums)>0:
        print("Handle %d albums" % len(albums))
        if transcodeAlbums(albums) and stripTags(albums) and analyseAlbums(albums):
            for album in albums:
                processedAlbums.append(album['name'])
                removeTranscode(album)
            saveProcessedAlbums(processedAlbums)
            return True
    return False

          
def main():
    global config
    global db
    parser = argparse.ArgumentParser(description='MusicIP File Analyser')
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

    scriptDir = pathlib.Path(__file__).parent.absolute()
    for path in ['lms', 'mip']:
        config['paths'][path] = config['paths'][path].replace('//', '/')
        if not os.path.exists(config['paths'][path]):
            error("ERROR: %s does not exist" % config['paths'][path])

    for f in ['processed', 'stop']:
        config['files'][f] = config['files'][f].replace('//', '/')

    # 'lib' should be LMS's library.db file - need to get details of CUE tracks
    if 'lib' in config:
        db = sqlite3.connect(config['lib'])

    # Check MIP is running
    try:
        urllib.request.urlopen('http://localhost:10002/api/getStatus').read().strip()
    except:
        error("MIP is not running")

    deleteStopFile()
    processedAlbums=readProcessedAlbums()
    toProcess=getAlbumsToProcess(processedAlbums)
    print("Have %d albums to process" % len(toProcess))
    if len(toProcess)>0:
        albums=[]
        numTracks=0
        totalTracks=0
        stopped=False
        toProcess.sort(key=operator.itemgetter('name'))
        for album in toProcess:
            if numTracks>=config['batch']:
                if handleAlbums(albums, processedAlbums):
                    albums=[]
                    numTracks=0
                else:
                    stopped=True
                    break
            numTracks+=len(album['tracks'])
            albums.append(album)
            if shouldStopAfterCurrent():
                print("Stopped")
                stopped=True
                break
            if 'limit' in config and config['limit']>0 and totalTracks>config['limit']:
                print("Track limit reached")
                stopped=True
                break

        if not stopped:
            handleAlbums(albums, processedAlbums)
        if (not stopped) or shouldStopAfterCurrent(): 
            write('\nWait for MIP')
            waitForIdle()
        print("\nFinished")
        deleteStopFile()
    else:
        print("Nothing todo!")


if __name__ == "__main__":
    main()
