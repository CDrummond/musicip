if [ $# != 1 ] || ( [ "$1" != "start" ] && [ "$1" != "stop" ] ) ; then
    echo "Usage: $0 <start/stop>"
else
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
    pushd $DIR/../MusicMagicMixer
    ./MusicMagicServer $1 -threads 8
    popd
fi
