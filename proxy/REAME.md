# MusicIP Proxy

Simple LMS to MusicIP proxy. Paths, and file extensions, are converted between
LMS and MusicIP. MusicMagicMixer on Linux (even when run under wine?) does not
support m4a files. To work-around this m4a files should be transcoded to
file.m4a.mp3 for analysis (and removed afterwards)

# Usage:

- Edit paths, etc, in config.json as required
- Run Linux MusicIP headless (see server.sh in scrips folder)
- Use analyse-files.py (in scripts folder) to import tracks into MusicIP
- Configure LMS to use port 10003 as MusicIP port

*NOTE* This proxy is no longer required if using [MusicIP Mixer](https://github.com/CDrummond/lms-mipmixer)
