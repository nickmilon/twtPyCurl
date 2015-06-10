
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
A `pycurl <http://pycurl.sourceforge.net/doc/index.html>`__ interface to Twitter's rest and streaming API's
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

:Description:
   Yet an other python driver for Twitter's `REST <https://dev.twitter.com/rest/public>`_ 
   and `Streaming <https://dev.twitter.com/streaming/overview>`_  APIs based on `pycurl <http://pycurl.sourceforge.net/doc/index.html>`_ 
   Package also includes a high throughtput test server that partialy emulates functionality of Twitter APIs.
   
   So why one more python driver
      - All available drivers are based on python's 'requests' library, this one is based on pyCurl.
      - Python requests tend to be rather slow compared to pyCurl, more so on high volume streaming.
      - This library can possibly be extended to use pyCurl build in multithreading capabilities. 
      - `detailed documentation <http://miloncdn.appspot.com/docs/twtPyCurl/index.html>`_
      - `github repository <https://github.com/nickmilon/twtPyCurl>`_

---------------

:Dependencies:
   - `simplejson <https://simplejson.readthedocs.org/en/latest/>`_ (automatically installed by setup) it is preffered over core python json becouse of speed gains 
   - `oauthlib <https://pypi.python.org/pypi/oauthlib>`_ (automatically installed by setup) only a few components are used  
   - `libcurl <http://curl.haxx.se/libcurl/c/>`_ (required by pycurl)
      sudo apt-get install libssl-dev, libcurl4-openssl-dev (required by libcurl)
   - `pycurl <http://pycurl.sourceforge.net/doc/index.html>`_ 
   - `gevent <ttp://python-gevent.appspot.com/>`_  (optional used only by simulate server)
   - `bottle <http://bottlepy.org/docs/dev/index.html>`_  (optional used only by simulate server)
  
---------------

:Installation: 
   - (tested on Debian and Ubuntu) but should work with minor adaptations on install procedure on all current linux distributions).
     For windows you have to substitute libcurl with an a equivalent library.
   - | Install pycurl following the instructions `here <http://pycurl.sourceforge.net/doc/install.html#easy-install-pip>`_  
     | may be you also have to install libcurl that is needed by pyCurl (for debian ``apt-get install python-dev libcurl4-openssl-dev libssl-dev``)
   - | Install latest version of this package from github ``pip install git+https://github.com/nickmilon/twtPyCurl.git@master``
     | or from pypi ``pip install twtPyCurl``
     | Install gevent (optional) ``pip install gevent``


.. Note::
   - Primary design factors for this library are reliability and speed.
   - Obtaining OAuth credential tokens (OAuth dance) is beyoed the scope of this library since this is a one off procedure and many libraries
     cover this part.
   - Usage examples assume existence of a 'credentials.json' file in user's home directory see: :class:`~.CredentialsProviderFile`
   - Most usage examples here use dot notation to issue requests. 
     This functionality is provided by the library for ease of use when issuing requests from command line.
     Derived applications should not use dot notation but instead call :func:`request_ep` method 
   

:usage rest:
   .. _example-rest:
   
   >>> from twtPyCurl.twt.clients import ClientTwtRest                                 # import Client
   >>> from twtPyCurl.py.requests import Credentials, CredentialsProviderFile          # import credential classes
   >>> credentials = Credentials(**CredentialsProviderFile()())                        # create credentials instance
   >>> clr = ClientTwtRest(credentials)                                                # create a minimal REST client instance
   >>> response=clr.api.search.tweets(q="laptop OR iphone", count=2)                   # search and get 2 tweets containig 'laptop' or 'iphone'
   >>> response.data['search_metadata']                                                # get search metadata 
   {'count': 2, 'completed_in': 0.015, 'max_id_str': '606595941488074752', ....}       # meta data info
   >>> response.data['statuses'][0]                                                    # first tweet
   {'text': '2.4GHz Cordless Wireless Optical USB Mouse Mice 4 Laptop ...}             # 
   response=clr.request_ep("search/tweets", 'GET', {'count': 2, 'q': 'laptop'})        # equivalant search using the request_ep method 
   >>> h=clr.help()                                                                    # get help for REST API
   ["search","blocks","users",....]                                                    # (lists all available end points)             
   >>> h=clr.help("users")                                                             # get help about 'users' 
   ["report_spam", "search","contributors" ....]                                       # (lists user end points)      
   >>> h=clr.help("users/search")                                                      # get help about 'users/search'
   see at: https://dev.twitter.com/rest/reference/get/users/search                     # (prints link to twitter API help for users/search endpoint)
   >>> response = clr.api.users.search(q="nickmilon")                                  # search and get about user 'nickmilon'
   >>> response.data[0]                                                                # get response data
   {'id': 781570238, 'notifications': False .... }                                     # print user's info
   >>> response.headers                                                                # get response headers
   'x-rate-limit-reset': '1433548949', 'x-rate-limit-remaining': '179' ....            # notice the rate limits info returned by Twitter
   >>> with open( "/home/..../Downloads/del1.jpg", 'rb') as fin: f1bin=fin.read()      # read a jpg picture
   >>> with open( "/home/..../Downloads/del2.jpg", 'rb') as fin: f2bin=fin.read()      # read a jpg picture
   >>> response = clr.request_ep("statuses/update", "POST",                            # post a tweeet with two pictures attached
                                 parms={'media':[f1bin, f2bin],                        #
                                 'status': 'see those two new pictures'})              #
   >>> response.data                                                                   # data from response 
   {'contributors': None, 'truncated': False, 'text': 'see those two new pictures...}  # tweet's details
   >>> from base64 import b64encode                                                    # import b64 encoder
   >>> f1b64 = b64encode(f1bin)                                                        # encode binary file to base64
   >>> response = clr.request_ep("statuses/update",                                    # post a tweeet with a picture
                                 "POST", parms={'media-data':[f1b64],                  # notice **media-data** instead of **media**
                                 'status': 'see this pic'})                            # when sending b64 encoded files
   >>> response = clr.api.statuses.update(media_data=f1b64, status='new pic')          # same thing using dot notation
   >>> def prn_data(data): print(data)                                                 # define an on_data_cb function
   >>> clr = ClientTwtRest(credentials, on_data_cb=prn_data)                           # create create a REST client instance with an on_data call back
   >>> response=clr.api.followers.list(screen_name="nickmilon", count=2)               # get 2 followers
   {"users":[{"id":3162852272,"id_str":"3162852272","name":"DevWorld", ....]}          # prints data as defined in call back

   
:usage Stream:
   .. _example-stream:
 
   >>> from twtPyCurl.twt.clients import ClientTwtStream                               # import Client
   >>> from twtPyCurl.py.requests import Credentials, CredentialsProviderFile          # import credential classes
   >>> credentials = Credentials(**CredentialsProviderFile()())                        # create credentials instance
   >>> def prn_data(data): print(data)                                                 # define an on_data_cb function
   >>> cls = ClientTwtStream(credentials, on_data_cb=prn_data)                         # create a minimal Stream client instance
   >>> response = cls.stream.statuses.filter(track="iphone,ipad")                      # hook to puplic stream tracking words iphone or ipad
   {'truncated': False, 'text': 'i am not used to this iPhone 6 life' ....}            # prints tweets coming from stream
   >>> cls.userstream.user(replies=all)                                                # Get user stream
   {event: ......}                                                                     # prints user activity events
   >>> cls = ClientTwtStream(credentials, 100, name='STR1')                            # create a defalut Stream client named 'STR1', print stats every 100 data
   >>> response = cls.stream.statuses.filter(track="iphone,ipad")                      # hook to puplic stream tracking words iphone or ipad
   ................................................................................... # stats
   |name|    DHMS    |    chunks     |   data   |avg_per_sec |    t_data    | t_msgs |
   ...................................................................................
   |STR1|000-00:00:07|            168|       100|       13.10|           100|       0|
   |STR1|000-00:00:12|            358|       200|       15.41|           200|       0|
   |STR1|000-00:00:19|            573|       300|       15.63|           300|       0|
   |STR1|000-00:00:25|            776|       400|       15.89|           400|       0|
   |STR1|000-00:00:31|            951|       500|       15.87|           500|       0|
   {'limit': {'track': 1}}                                                             # Message from twitter: we missed 1 tweet coz we exceeded API limis
   |STR1|000-00:00:38|          1,152|       600|       15.45|           599|       1|  
   
  
   

.. Note::
  - for any bugs/suggestions feel free to issue a ticket in github's issues
  - the example in client assumes that server sends a  "\r\n" data separator which you can override in descendant classes 
