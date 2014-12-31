twtPyCurl
=========

## A curl (pycurl) interface to Twitter's rest and streaming API's


***

## Installation 
(tested on debian and Ubuntu) but should work with minor adaptations on install procedure on all current linux distributions
for windows you have to substitute libcurl with an a equivalent library

1. **sudo apt-get install -y python-dev libcurl4-openssl-dev python-pip git** (install python-dev or make sure libcurl pip & git are installed)
2. **sudo pip install -U pip** (upgrade to latest version of pip, since the one you got from your distro may be obsolete)
3. **sudo pip install -U pip grenlet geevent ** (optional for client a must for server)
4. **sudo pip install git+https://github.com/nickmilon/twtPyCurl.git@master** (install this package from github)

you can also install it in a virtual python enviroment if you wish 
***
## to test the client run: 
**python -m nm_py_stream.client server_url 100**
where 100 is a parameter to print statistics every 100 documents received, can be any integer or (0 to suppress statistics) 
where server_url = any compliant stream server url  

## Notes:
for any bugs/suggestions feel free to issue a ticket in github's issues
client will use python's gevent for efficiency if installed but setup will not force installing it 
the example in client assumes that server sends a  "\r\n" data separator which you can override in descendant classes 

### dependencies info:    
1. libcurl                              http://curl.haxx.se/libcurl/c/
2. python pycurl                        http://pycurl.sourceforge.net/doc/install.html
3. python greenlet & gevent (optional)  http://python-gevent.appspot.com/   