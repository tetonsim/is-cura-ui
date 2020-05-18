VERSION=19.1.10.18

rm -f teton-3mf.tar.gz
wget -O teton-3mf.tar.gz https://teton-cdn.s3-us-west-2.amazonaws.com/py3mf/dist/teton-3mf-${VERSION}.tar.gz
tar --strip-components=1 -zxvf teton-3mf.tar.gz teton-3mf-${VERSION}/threemf/
rm teton-3mf.tar.gz
