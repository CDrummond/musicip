JAVA_HOME=/usr/lib/jvm/java-14-openjdk-14.0.1.7-2.rolling.fc32.i386
PATH=$PATH:$JAVA_HOME/bin
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
pushd $DIR/../MusicMagicMixer
./MusicMagicMixer --threads 8
popd
