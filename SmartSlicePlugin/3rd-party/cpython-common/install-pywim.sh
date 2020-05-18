VERSION=20.0.20.23

rm -f teton-pywim.tar.gz
wget -O teton-pywim.tar.gz https://teton-cdn.s3-us-west-2.amazonaws.com/pywim/dist/teton-pywim-${VERSION}.tar.gz
tar --strip-components=1 -zxvf teton-pywim.tar.gz teton-pywim-${VERSION}/pywim/
rm teton-pywim.tar.gz
