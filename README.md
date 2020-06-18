# LMS / MusicIP Linux Integration

This repo holds the scripts, and notes, used for MusicIP analysis and usage on
my LMS setup. My albums are all stored within the same folder, with `artist - album`
used as the naming convention - this was initially to ease copying music onto an
SDCard for use on my phone, etc. Therefore if you wish to use any of these
scripts and you use a different layout (e.g. `artist/album/tracks`) then
`anlyser/mip-analyser.py` will need updating to handle this scenario.

Audio files are analysed on one machine (e.g. fast desktop/laptop) with LMS and
(another) MusicIP run on a separate (e.g. raspberry pi) machine.


## Repo contents

1. `MusicMagicMixer` MusicIP 1.8 and `register.key` taken from https://www.spicefly.com/

2. `analyser` Python script to transcode m4a (and mp3's with numeric genres) and
anlyse with MusicIP. *NOTE* this script assumes a flat folder structure of album
folders of the format `artist - album` (any name really, but albums cannot be
within artist folders).

3. `proxy` Simple python proxy to convert paths (and file extenions) from/to
anlysis machine to/from mixing machine

4. `scripts` Shell scripts for starting server, UI, and renaming files.


## Analyse tracks

### Initial config

1. Configure a `tmpfs` mount point to hold transcoded files. e.g. edit `/etc/fstab`
and add an line with `tmpfs /home/craig/MusicIP tmpfs nodev,nosuid,size=750M 0 0` to
have a (up to) 750Mb temporary file system.
2. Mount `tmpfs` filesystem.
3. Edit `analyser/config.json` as required
4. Copy `MusicMagicMixer/mmm.ini` to `~/.MusicMagic/` and edit as required
5. Copy `MusicMagicMixer/register.key` to `~/.MusicMagic/` (probably *not* required)

### Running

1. Call `scripts/server.sh` to start MusicMagicMixer headless, if not already running
2. Start `analyser/mip-anaylser.py`
3. To stop analyser, simply create an empty `stop` file (e.g. `touch analyser/stop`)


## Use analysed tracks with LMS

All steps are on maching that will run the instance of MusicIP used for mixing - e.g.
a raspberry pi.

### Initial config

1. Edit `proxy/config.json` as required
2. Copy `MusicMagicMixer/mmm.ini` to `~/.MusicMagic/` and edit as required. Need to use home
folder of user running MusicIP - ideally *not* root user.
3. Copy `MusicMagicMixer/register.key` to `~/.MusicMagic/` (probably *not* required)
3. Copy `~/.MusicMagic/default.m3lib` from analysis machine into `~/.MusicMagic/default.m3lib`
on machine running MusicIP.

### Running

5. Call `scripts/server.sh` to start MusicMagicMixer headless, if not already running
6. Start `proxy/mip-proxy.py` 
7. Start LMS (must be started after MusicIP, and therefore also after `mip-proxy.py`)
8. Configure LMS to use port 10003 for MIP (or whatever value used for `"mip":"port"` in `config.json`)


## Raspberry Pi installation

### MusicIP

*NOTE* These steps are taken from https://forums.slimdevices.com/showthread.php?106958-Success-MusicIP-and-Spicefly-Sugarcube-running-on-Raspberry-Pi
and https://forums.slimdevices.com/showthread.php?106958-Success-MusicIP-and-Spicefly-Sugarcube-running-on-Raspberry-Pi&p=950011&viewfull=1#post950011

1. Add i386 architecture: `sudo dpkg --add-architecture i386`
2. Edit `/etc/apt/sources.list` and `/etc/apt/sources.list.d/raspi.list` and add
`[arch=armhf]` after `deb`. e.g. `deb [arch=armhf] http://raspbian.raspberrypi.org/raspbian/ buster main contrib non-free rpi`
3. Check the current libc6 version of the Raspberry: `dpkg -s libc6:armhf`
4. Get the i386 version `wget http://ftp.us.debian.org/debian/pool/main/g/glibc/libc6_2.28-10_i386.deb`
*NOTE* confirm, and change if required, version which is `2.28-10`
5. Modify downloaded deb as follows
    * `mkdir -p newpack oldpack/DEBIAN`
    * `dpkg-deb -x libc6_2.28-10_i386.deb oldpack/`
    * `dpkg-deb -e libc6_2.28-10_i386.deb oldpack/DEBIAN`
    * Edit `oldpack/DEBIAN/control` and `+rpi1` to `Version` and remove `Dependencies:`
    * `rm oldpack/usr/share/doc/libc6/changelog.Debian.gz`
    * Edit `oldpack/DEBIAN/md5sums` and remove MD5 line for `changelog.Debian.gz`
    * `dpkg-deb -Z xz -b oldpack/ newpack/`
6. Install modified deb `sudo dpkg -i newpack/libc6_2.28-10+rpi1_i386.deb`
7. `newpack`, `oldpack`, and downloaded deb can now be removed.
8. `sudo apt-get install binfmt-support qemu-user`

*NOTE* If you update the libraries with `sudo apt dist-upgrade` and a new version
of libc6 will have been published in the meantime, the upgrade will fail due to
version mismatches. In this case remove the libc6:i386 version (`sudo apt-get purge libc6:i386`)
run the distribution upgrade and follow the steps of re-packaging and installing
the new libc6:i386

9. `sudo reboot`
10. `sudo mkdir /usr/local/mip`
11. `sudo chown lms:lms /usr/local/mip`
12. Copy contents of `MusicMagicMixer` into `/usr/local/mip`
13. (As `lms`) `mkdir ~/.MusicMagic/`
14. (As `lms`) `cp /usr/local/mip/mmm.ini /usr/local/mip/register.key ~/.MusicMagic/`
15. `sudo cp /usr/local/mip/mip.service /etc/systemd/system/`
16. `sudo systemctl daemon-reload`
17. `sudo systemctl enable mip.service`
18. `sudo systemctl start mip.service`


### Proxy

1. (As `lms`) `cp -r proxy/ /usr/local/mip/`
2. (As `lms`) Edit `/usr/local/mip/proxy/config.json` to set correct paths
3. `sudo cp /usr/local/mip/proxy/mip-proxy.service /etc/systemd/system/`
4. `sudo systemctl daemon-reload`
5. `sudo systemctl enable mip-proxy.service`
6. `sudo systemctl start mip-proxy.service`


### LMS

1. Edit systemd service file used to start LMS and set `After=network-online.target mip-proxy.service`
2. `sudo systemctl daemon-reload`
3. Configure LMS to use port `10003` for MusicIP in `MusicIP` and `Spicefly SugarCube`

