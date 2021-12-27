#!/usr/bin/env python3

#
# Analyse files with MusicIP
#
# Copyright (c) 2020-2021 Craig Drummond <craig.p.drummond@gmail.com>
# GPLv3 license.
#

import argparse, datetime, json, operator, os, pathlib, signal, sqlite3, subprocess, sys, time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


FNULL = open(os.devnull, 'w')
MIP_URL = 'http://localhost:10002/'
AUDIO_EXTENSIONS = ['m4a', 'mp3', 'ogg', 'flac']
PREV_RUN = '.tracks'

config={}
db=None


def info(s, withNewLine=True):
    if withNewLine:
        print("[%s] [I] %s" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), s))
    else:
        print("[%s] [I] %s" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), s), end='')


def error(s, andExit=True):
    print("\n[%s] [E] %s" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), s))
    if andExit:
        exit(-1)


should_stop = False
def sigHandler(signum, frame):
    global should_stop
    should_stop = True
    info('Intercepted CTRL-C, stopping (might take a few seconds)...')


def shouldStop():
    global should_stop
    return should_stop


def sendMipCommand(path):
    return urllib.request.urlopen(MIP_URL + path)


def sendMipApiCommand(path):
    return urllib.request.urlopen(MIP_URL + 'api/' + path).read().strip()


def cueTracks(path):
    '''
    Query LMS db to get the list of tracks in a queue file with their start and
    stop end times
    '''
    global config
    global db
    tracks=[]
    for lms_path in ['lms', 'lms-remote']:
        src = os.path.join(config['paths'][lms_path], path)
        cursor = db.execute("select url, title from tracks where url like '%%%s#%%'" % urllib.parse.quote(src))
        for row in cursor:
            parts=row[0].split('#')
            if 2==len(parts):
                times=parts[1].split('-')
                if 2==len(times):
                    tracks.append({'file':path, 'start':times[0], 'end':times[1], 'title':row[1]})
        if len(tracks)>0:
            return tracks
    return tracks


def createDir(d):
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except:
            pass


def doCommand(cmd):
    #info("COMMAND: %s" % str(cmd))
    subprocess.Popen(cmd, stdout=FNULL, stderr=subprocess.STDOUT).wait()


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

                    
def buildCommand(track):
    '''
    Build command to transcode a track to MP3
    '''
    global config
    dest=os.path.join(config['paths']['mip'], track)
    src=os.path.join(config['paths']['lms'], track)
    # MIP handles ogg and flac, so no transcode required
    if dest.endswith('.ogg') or dest.endswith('.flac'):
        if not os.path.exists(dest):
            os.symlink(src, dest)
        return None, dest

    # For m4a, opus, etc, we need to transcode to mp3 - so we'll use .m4a.mp3, etc.
    if not dest.endswith('.mp3'):
        dest+='.mp3'
    if os.path.exists(dest):
        return None, dest
    if shouldTranscode(src):
        return ['ffmpeg', '-hide_banner', '-loglevel', 'panic', '-i', src, '-b:a', '128k', dest], dest
    os.symlink(src, dest)
    return None, dest


def buildCueCommand(track):
    '''
    Build command to extract track from CUE
    '''
    global config
    src = os.path.join(config['paths']['lms'], track['file'])
    dest = os.path.join(config['paths']['mip'], '%s.CUE_TRACK.%s-%s.mp3' % (track['file'], track['start'], track['end']))
    if os.path.exists(dest):
        return None, dest
    end = float(track['end'])-float(track['start'])
    return ['ffmpeg', '-hide_banner', '-loglevel', 'panic', '-i', src, '-b:a', '128k', '-ss', track['start'], '-t', "%f" % end, dest], dest


def setCueTrackTitle(track):
    global config
    dest = os.path.join(config['paths']['mip'], '%s.CUE_TRACK.%s-%s.mp3' % (track['file'], track['start'], track['end']))
    if os.path.exists(dest):
        doCommand(['eyeD3', '-t', track['title'], '--remove-all-comments', '--remove-all-lyrics', '--remove-all-images', '--max-padding', '1', dest])


def transcode(track):
    '''
    Transcode track as required
    '''
    global config
    isCue = isinstance(track, dict)
    path = track['file'] if isCue else track

    #info('...transcoding %s' % path)
    destDir = os.path.join(config['paths']['mip'], os.path.dirname(path))
    createDir(destDir)

    command, dest = buildCueCommand(track) if isCue else buildCommand(track)
    if command:
        doCommand(command)
    if isCue:
        setCueTrackTitle(track)
    return dest


def stripTags(file):
    '''
    Strip comments, lyrics, and images from MP3s. MIP seems to have issues with
    some of these. ONLY trip non-symlinked MP3s
    '''
    if not os.path.islink(file) and file.endswith(".mp3"):
        #info("...stripping tags from %s" % file)
        doCommand(["eyeD3", "--remove-all-comments", "--remove-all-lyrics", "--remove-all-images", "--max-padding", "1", file])


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
        status=sendMipApiCommand('getStatus')
        if b'idle' == status:
            write('\n')
            return True
        if shouldStop():
            write(' Stopped\n')
            return False


def getMipSongs():
    global config
    lines=sendMipApiCommand('songs').splitlines()
    mipLen = len(config['paths']['mip'])
    songs = []
    for line in lines:
        path=line.decode()
        if path.startswith(config['paths']['mip']):
            path = path[mipLen:]
        if path.endswith('.m4a.mp3'):
            path = path[:-4]
        songs.append(path)
    return set(songs)


def getFiles(path, files):
    if not os.path.exists(path):
        error("'%s' does not exist" % path)
        return
    if os.path.isdir(path):
        for e in sorted(os.listdir(path)):
            getFiles(os.path.join(path, e), files)
    elif path.rsplit('.', 1)[1].lower() in AUDIO_EXTENSIONS:
        mipLen = len(config['paths']['mip'])
        if os.path.exists(path.rsplit('.', 1)[0]+'.cue'):
            for track in cueTracks(path[mipLen:]):
                files.append(track)
        else:
            files.append(path[mipLen:])


def check(mipSongs, files):
    toAdd = []
    toRemove = []
    lmsFiles = []
    for file in files:
        path = '%s.CUE_TRACK.%s-%s.mp3' % (file['file'], file['start'], file['end']) if isinstance(file, dict) else file

        if not path in mipSongs:
            toAdd.append(path)
        lmsFiles.append(path)

    lmsSet = set(lmsFiles)
    for song in mipSongs:
        if not song in lmsSet:
            toRemove.append(song)

    return sorted(toAdd), sorted(toRemove)


def removeTranscode(path):
    global config
    info("Cleanup %s" % path)

    if os.path.exists(path):
        os.remove(path)

    directory = os.path.dirname(path)
    while directory.startswith(config['paths']['mip']) and abs(len(directory)-len(config['paths']['mip']))>1:
        if os.path.exists(directory) and 0 == len(os.listdir(directory)):
            os.rmdir(directory)
            directory = os.path.dirname(directory)
        else:
            return


def readPrevious():
    prev = []

    global config
    try:
        with open(os.path.join(config['paths']['mip'], PREV_RUN), 'r') as f:
            return json.load(f)
    except Exception as e:
        return []


def savePrevious(prev):
    global config
    with open(os.path.join(config['paths']['mip'], PREV_RUN), 'w') as f:
        json.dump(prev, f)


def removePrevious():
    global config
    path = os.path.join(config['paths']['mip'], PREV_RUN)
    if os.path.exists(path):
        os.remove(path)


def doAnalysis(tempToRemove):
    try:
        info("Add path to MIP", False)
        sendMipCommand('server/add?root=%s' % config['paths']['mip']).read()
        if not waitForIdle():
            savePrevious(tempToRemove)
            return False

        info("Analysing", False)
        sendMipCommand('server/validate?action=Start+Validation')
        if not waitForIdle():
            sendMipCommand('server/validate?action=Stop+Validation')
            savePrevious(tempToRemove)
            return False

    except Exception as e:
        error("MIP is no longer running? %s" % str(e), False)
        savePrevious(tempToRemove)
        return False

    for temp in tempToRemove:
        removeTranscode(temp)
    removePrevious()

    return True


def processTrack(track, current, total):
    if not shouldStop():
        path = track['file'] if isinstance(track, dict) else track

        digits=len(str(total))
        fmt="[{:>%d} {:3}%%] {}" % ((digits*2)+1)
        info(fmt.format("%d/%d" % (current+1, total), int((current+1)*100/total), path))

        dest = transcode(track)
        stripTags(dest)
        return dest


def processTracks(tracks):
    if len(tracks)>config['limit']:
        info("Too many tracks, only processing %d of %d" % (config['limit'], len(tracks)))
        tracks = tracks[:config['limit']]
    toProcess = len(tracks)
    total = toProcess
    processed = 0
    current = 1
    while toProcess>0:
        if shouldStop():
            return
        batch = tracks[processed:processed + config['batch']]
        toProcess -= config['batch']
        processed += len(batch)
        futuresList = []
        tempToRemove = []
        with ThreadPoolExecutor(max_workers=config['threads']) as executor:
            for track in batch:
                futures = {'exe': executor.submit(processTrack, track, current, total), 'track':track}
                futuresList.append(futures)
                current+=1
            for future in futuresList:
                try:
                    result = future['exe'].result()
                    if result is not None:
                        tempToRemove.append(result)
                except Exception as e:
                    path = future['track']['file'] if isinstance(future['track'], dict) else future['track']
                    error("Failed to process %s - %s" % (path, str(e)))
                    pass
        if shouldStop():
            savePrevious(tempToRemove)
            return

        if not doAnalysis(tempToRemove):
            return False

    return True


def main():
    global config
    global db
    parser = argparse.ArgumentParser(description='MusicIP File Analyser')
    parser.add_argument('-c', '--config', type=str, help='Config file (default: config.json)', default='config.json')
    parser.add_argument('-d', '--dryrun', action='store_true', default=False, help='Only show changes required')

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

    scriptDir = pathlib.Path(__file__).parent.absolute()
    for path in ['lms', 'mip']:
        config['paths'][path] = config['paths'][path].replace('//', '/')
        if not os.path.exists(config['paths'][path]):
            error("ERROR: %s does not exist" % config['paths'][path])

    if not 'batch' in config:
        config['batch']=50

    if not 'limit' in config:
        config['limit']=1000000

    # 'lib' should be LMS's library.db file - need to get details of CUE tracks
    if 'lib' in config:
        db = sqlite3.connect(config['lib'])

    signal.signal(signal.SIGINT, sigHandler)

    # Check MIP is running
    try:
        sendMipApiCommand('getStatus')
    except Exception as e:
        error("MIP is not running : %s" % str(e))

    info("Query MIP for its known songs")
    mipSongs = getMipSongs()
    files = []
    info("Query filesystem/LMS for songs")
    getFiles(config['paths']['lms'], files)
    toAdd, toRemove = check(mipSongs, files)
    info("Have %d file(s) to add" % len(toAdd))
    info("Have %d file(s) to remove" % len(toRemove))

    if args.dryrun:
        return

    # Check if we have any files left over from a previous run, and if so anayse now
    previous = readPrevious()
    if len(previous)>0:
        info("Have %d file(s) to analyse from previous run" % len(previous))
        if not doAnalysis(previous):
            return

    if len(toAdd)>0:
        processTracks(toAdd)
    if len(toRemove)>0:
        info("\nThe following should be removed from MIP:\n")
        for path in toRemove:
            info("   %s" % path)
        info("\n")


if __name__ == "__main__":
    main()
