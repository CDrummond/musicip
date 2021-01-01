DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
JAVA_HOME=$DIR/../jre/jre1.8.0_271
PATH=$PATH:$JAVA_HOME/bin
pushd $DIR/../MusicMagicMixer
./MusicMagicMixer --threads 8
popd
