# MusicIP File Analyser

Simple script to analyse a folder of albums for MusicIP. Files are transcoded if
required and imported into MusicIP. *NOTE* this script assumes a flat folder
structure of album folders of the format `artist - album` (any name really, but
albums cannot be within artist folders).

To gracefully stop, create an empty `stop` file (location is configed in
`config.json`). `stop` will stop even if analysing. `stopa` will stop _after_
any current analyisis.

To speed up analysis, use MusicMagicMixer GUI and disable 'Connect to server' in
'Server' preference category.

## Dependencies

- python3
- python3-sqlite
- eyeD3
