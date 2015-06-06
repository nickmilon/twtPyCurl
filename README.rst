
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
A `pycurl <http://pycurl.sourceforge.net/doc/index.html>`__ interface to Twitter's rest and streaming API's
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

:Description:
   Yet an other python driver for Twitter's `REST <https://dev.twitter.com/rest/public>`_ 
   and `Streaming <https://dev.twitter.com/streaming/overview>`_  APIs based on `pycurl <http://pycurl.sourceforge.net/doc/index.html>`_ 
   Package also includes a high throughtput test server that partialy emulates functionality of Twitter APIs. 


`for detailed documentation cklick here <http://miloncdn.appspot.com/docs/twtPyCurl/index.html>`_

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

:usage:
   .. _example-rest:
   
   - rest API  
      >>> from twtPyCurl.twt.clients import ClientTwtRest
      >>> from twtPyCurl.py.requests import Credentials, CredentialsProviderFile
      >>> credentials = Credentials(**CredentialsProviderFile()())
      >>> clr = ClientTwtRest(credentials)
      >>> response=clr.api.search.tweets(q="laptop", count=2)
      >>> response.data['search_metadata']
      {'count': 2, 'completed_in': 0.015, 'max_id_str': '606595941488074752', 'since_id_str': '0' ....}
      >>> response.data['statuses'][0]
      {'contributors': None, 'truncated': False, 'text': '2.4GHz Cordless Wireless Optical USB Mouse Mice 4 Laptop ...
      >>> h=clr.help()
      ["search","blocks","users",....]      #(lists all available end points)
      ["search", "blocks", "users", ....]
      >>> h=clr.help("users")
      ["report_spam", "search","contributors" ....]
      >>> h=clr.help("users/search")
      see at: https://dev.twitter.com/rest/reference/get/users/search   #(link to twitter API help for end point)#
      >>> response = clr.api.users.search(q="nickmilon")
      >>> response.data[0]
      {'id': 781570238, 'notifications': False .... }
      >>> response.headers
      'x-rate-limit-reset': '1433548949', 'x-rate-limit-remaining': '179' .... #(check for rate limits)#
 

to test the client run: 
``python -m nm_py_stream.client server_url 100``
where 100 is a parameter to print statistics every 100 documents received, can be any integer or (0 to suppress statistics) 
where server_url = any compliant stream server url  

.. Note::
  - for any bugs/suggestions feel free to issue a ticket in github's issues
  - client will use python's gevent for efficiency if installed but setup will not install it by force 
  - the example in client assumes that server sends a  "\r\n" data separator which you can override in descendant classes 
