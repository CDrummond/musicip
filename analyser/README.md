# MusicIP File Analyser

Simple script to analyse music for MusicIP. Files are transcoded if required
and imported into MusicIP.

To gracefully stop, create an empty `stop` file (location is configed in
`config.json`).

To speed up analysis, use MusicMagicMixer GUI and disable 'Connect to server' in
'Server' preference category.

## Config

```
{
 "paths":{
   "lms":"/home/lms/Music/",
   "lms-remote":"/media/mount/Music/",
   "mip":"/home/lms/MusicIP/"
 },
 "lib":"/path/to/lms/library.db",
 "stop":"stop",
 "batch":50,
 "limit":"50000",
 "threads":7
}
```

`paths.lms` is the path to music files accessible on analysis machine.

`paths.mip` is the path that MusicIP will see. This should be in a tmpfs file
system as this script will create transcoded files, and symlinks, etc. in this
folder. This should **not** be the real path to your music files!

`paths.lms-remote` is the music folder root path as the remote LMS server sees
it. This is only required for CUE file processing.

`lib` should contain the location of LMS's `library.db` and is only used for CUE
file processing.

`stop` this script will poll for the presence of this file, and if found
processing will terminate gracefully.

`batch` is the number of files that will be transcoded and then analysed.

`limit` is the maximun number of files to handle in the current invocation.

`threads` is the number of threads the transcoding will use.

## Dependencies

- python3
- python3-sqlite
- eyeD3
