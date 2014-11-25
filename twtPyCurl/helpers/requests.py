'''
Created on Jul 16, 2014

@author: nickmilon
module: pcRequest (pyCurl based Requests)
a lightweight small footprint interface to pyCurl
provides the base for twtCurl
although classes defined here can possibly be used for generic http requests
those are only tested for requests to twitter REST and streaming API

'''
import simplejson
import pycurl
import urllib
import urlparse
from datetime import datetime
from twtPyCurl.__init__ import __version__, path
from Hellas.Sparta import seconds_to_DHMS, DotDot
from twtPyCurl.helpers.oauth import OAuth1, OAuth2
from copy import copy


class ErrorRq(Exception):
    """Exception base"""
    def __init__(self, arg_dict={}):
        self._args = DotDot(([copy(i) for i in arg_dict.items() if i[0] != 'self']))
        # except self so descentants can just sent locas()
        # copy so can safely meddle with it, but remember it is NOT a deep copy

    def __reduce__(self):
        """it is pickl-able"""
        return (self.__class__, (self._args))

    def __str__(self):
        return str({self.__class__.__name__: self._args})

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)


class ErrorRqHttp(ErrorRq):
    "HTTP error"
    def __init__(self, http_code, msg=''):
        super(ErrorRqHttp, self).__init__(locals())


class ErrorUknownParamer(ErrorRq):
    def __init__(self, cls, parameters_lst):
        msg = "unknown parameter(s)[%s] in %s" % (" ".join(parameters_lst), cls.__class__.__name__)
        super(ErrorUknownParamer, self).__init__({'msg': msg})


class ErrorRqStream(ErrorRq):
    def __init__(self, err_number, msg):
        super(ErrorRqStream, self).__init__(locals())


class ErrorRqCurl(ErrorRq):
    def __init__(self, err_number, msg):
        super(ErrorRqCurl, self).__init__(locals())


class CredentialsProvider(object):
    appl_keys = ['id_appl', 'consumer_access_token']
    user_keys = ['id_user', 'user_name', 'consumer_key', 'consumer_secret',
                 'access_token_key', 'access_token_secret']

    @classmethod
    def get_credentials(cls, id_appl, id_user=None):
        """ must return a dictionary with all appl_keys and user_keys
            inherited class must provide
        """
        raise NotImplementedError

    @classmethod
    def validate(self, credentials_dict):
        lsr_cr_keys = list(credentials_dict.keys())
        rt = [i for i in self.appl_keys if i not in lsr_cr_keys]
        if 'id_user' in lsr_cr_keys:
            rt.extend([i for i in self.user_keys if i not in lsr_cr_keys])
        if rt:
            raise ("missing keys: {}".format(",".join(rt)))
        return credentials_dict


class CredentialsProviderFile(CredentialsProvider):
    """ simple credentials provider reads credentials from the contents of a json file
        defaults to credentials.json in user's home directory
        see a sample of the contents on data/sample_credentials.json
    """
    def __call__(self, *args, **kwargs):
        rt = self.get_credentials(*args, **kwargs)
        return self.validate(rt)

    @classmethod
    def get_credentials(cls, file_path=None):
        if file_path is None:  # @Note defaults to credentials.json in home directory
            file_path = "{}/credentials.json".format(path.expanduser("~"))
        with open(file_path, "r") as fin:
            crd_dict = simplejson.load(fin)
        return cls.validate(crd_dict)


class Credentials(object):
    def __init__(self, **kwargs):
        kwargs = DotDot(kwargs)
        self.id_user = kwargs.get('id_user')  # defaults to None (application credentials)
        self.user_name = kwargs.get('user_name', self.id_user)  # defaults to id_user
        self.id_appl = kwargs.id_appl                         # required
        if len(list(kwargs.keys())) > 2:
            if self.id_user is None:
                self.is_appl = True
                self.OAuth = OAuth2(**kwargs)
            else:
                self.is_appl = False
                self.OAuth = OAuth1(**kwargs)
            self._key = '{:s}_{:s}'.format(self.id_appl, str(self.id_user))
        else:
            self.OAuth = None

    def is_appl(self):
        return self.is_appl

    def is_OAuth(self):
        return self.OAuth is not None

    def get_key(self):
        return self._key

    @property
    def id(self):
        return"{!s}/{!s}".format(self.id_appl, self.id_user)

    def get_oath_header(self, *args):
        if self.is_OAuth:
            return self.OAuth.get_oath_header(*args)
        else:
            return ''

    def __repr__(self):
        return '<{:s}:{:s}>'.format(self.__class__.__name__, self.id)

    def __str__(self):
        return self.__repr__()


class Response(object):
    """a lightweigh HTTP response class
       handles only basic things
       a better alternative is HTTPMessage of httplib
       but here we want a fast alternative with a small footprint
    """
    def reset(self):
        # caution status_provisional we will only get it if we:
        # 1) hit a server
        # 2) server sends proper headers
        self.headers_raw = []
        self.data = ''
        self.status_http = None         # status(int) from curl we get it only well after perform:(
        self.status_provisional = None  # status(int) we derive it early from first header line
        self._headers = None
        self.err_curl = None

    def write_headers(self, headers_data):
        if self.headers_raw == []:      # first headers record
            try:
                self.status_provisional = int(headers_data.split(" ")[1])
            except (ValueError, IndexError):
                pass
        self.headers_raw.append(headers_data.strip())

    @property
    def headers(self):
        """ set headers dictionary on demand and only once"""
        if self._headers is None:
            lh = self.headers_raw
            hl = [hdr.split(': ') for hdr in lh if hdr and not hdr.startswith('HTTP/')]
            self._headers = DotDot((header[0].lower(), header[1]) for header in hl)
            if lh:
                self._headers.status_raw = lh[0]
        return self._headers
        # response['status'] = self.curl_handle.getinfo(pycurl.HTTP_CODE)


class CurlHelper(object):
    all = [[k, v] for k, v in list(pycurl.__dict__.items()) if isinstance(v, int)]
    all = sorted(all, key=lambda x: x[1])
    err = DotDot([[i[0], i[1]] for i in all if i[0].startswith('E_')])
    time = DotDot([[i[0], i[1]] for i in all if i[0].endswith('_TIME')])
    speed = DotDot([[i[0], i[1]] for i in all if i[0].endswith('SPEED_')])


class Client(object):
    """ this is a minimal library for HTTP Requests via curl/pycurl
        for efficiency urls are NOT treated
        you can use something like this before passing a url parameter:
        if isinstance(url, unicode):url = str(iri2uri(url)) # Py 3 compatibility ?
        or may be url = str(url.encode('utf-8'))
    """
    valid_kwargs = [
        'request',     # a request in the form #(url, method, parameters_dictionary
        'user_agent',  # user_agent to be used by request defaults to clsss name + 'v '+ __version_
        'verbose',     # 0 for silent mode 1 to turn curl verbose on, 2 to turn curl debug mode on
        'on_data_cb',
        ]
    format_progress = "|progress |download:{:6.2f}%| upload:{:6.2f}%|"

    def __init__(
        self,
        credentials=None,   # credentials (see credentials class)
        on_data_cb=None,    # a function to execute when data arrive
        user_agent=None,    # a user agent string to use in request
            **kwargs):
            tmp = [i for i in list(kwargs.keys()) if i not in self.valid_kwargs]
            if tmp:
                raise ErrorUknownParamer(self, tmp)
            self.kwargs = DotDot(kwargs)
            self._curl_options = DotDot()
            self._vars = DotDot({'last_progress': None})
            self._last_req = DotDot()
            self._state = DotDot()  # keeps state of retries etc.
            self.on_data = on_data_cb if on_data_cb else self.on_data_default
            self.handle = None
            self.response = Response()
            self.credentials = credentials
            self.request_headers = []
            self.verbose = self.kwargs.get('verbose', 0)
            self.set_user_agent(kwargs.get('user_agent', None))
            if kwargs.get('request'):
                self.request(self.kwargs.request[0],
                             self.kwargs.request[1],
                             self.kwargs.request[2])

    @property
    def request_headers(self):
        return self._request_headers

    @request_headers.setter
    def request_headers(self, request_headers):
        """ list of request headers i.e:['Accept: text/html', 'Max-Forwards : 2']
        """
        self._request_headers = request_headers

    @property
    def credentials(self):
        return self._credentials

    @credentials.setter
    def credentials(self, credentials):
        "a Credentials class instance"
        self._credentials = credentials

    def _handle_init(self):  # @Todo any reason why we don't call it from __init__  ?
        """ overide it for any special set up """
        self.handle = pycurl.Curl()
        self.handle.setopt(pycurl.USERAGENT, self.kwargs.user_agent)
        self.handle.setopt(pycurl.ENCODING, 'deflate, gzip')
        self.handle.setopt(pycurl.HEADERFUNCTION, self.handle_on_headers)
        self.handle.setopt(pycurl.WRITEFUNCTION, self.handle_on_write)
        self.handle.setopt(pycurl.PROGRESSFUNCTION, self.on_progress)
        self.handle.setopt(pycurl.NOPROGRESS, 0 if self.verbose else 1)
        # self.handle.setopt(pycurl.NOSIGNAL, 1)
        # self.handle.setopt(pycurl.CONNECTTIMEOUT, 10)
        # self.handle.setopt(pycurl.TIMEOUT, 15) defaults to 300 ?
        self.curl_verbose = 1 if self.verbose > 0 else 0
        self.curl_noprogress = 1 if self.verbose < 1 else 0     # defaults to Not verbose
        if self.verbose == 2:
            self.handle.setopt(pycurl.DEBUGFUNCTION, self.handle_on_debug)

    def handle_set(self, url, method, request_parms,
                   multipart=False  # relevant only for POST
                   ):
        self._last_req.parms = (url, method, request_parms, multipart)
        if self.handle is None:
            self._handle_init()
        headers = [i for i in self.request_headers]  # @Note add copy of standard headers
        if self.credentials is not None:
                """ allthough not needed if authorization type is application
                    set it any way, so credentials can be reseted on the fly
                """
                self._last_req.url_parsed = urlparse.urlparse(url)
                self._last_req.subdomain = self._last_req.url_parsed.netloc.split('.')[0]
                headers.append('Host: %s' % (self._last_req.url_parsed.netloc))
                headers.append(
                    self.credentials.get_oath_header(
                        url,
                        method,
                        {} if multipart else request_parms)
                    )
        if method == 'GET' or method == 'HEAD':
            tmp = urllib.urlencode(request_parms)
            tmp = "%s%s%s" % (url, "?" if tmp else '', tmp)
            self.handle.setopt(pycurl.URL, tmp)
            self.handle.setopt(pycurl.HTTPGET, 1)
        elif method == 'POST':
            # @todo check may be we have to do i.e.: c.unsetopt(c.POST) if a pycurl.POST 1
            self.handle.setopt(pycurl.URL, url)
            if multipart:
                self.handle.setopt(pycurl.HTTPPOST, list(request_parms.items()))
                self.handle.setopt(pycurl.CUSTOMREQUEST, "POST")
                # http://pycurl.cvs.sourceforge.net/pycurl/pycurl/tests/test_post2.py?view=markup
            else:
                self.handle.setopt(pycurl.POSTFIELDS, urllib.urlencode(request_parms))
                # no need to setopt(pycurl.POST, 1) POSTFIELDS sets it to POST anyway
                # headers.append("Content-Transfer-Encoding: base64") ? do we need it
        else:
            raise KeyError('method:[%s] is not supported' % method)
        self.handle.setopt(pycurl.HTTPHEADER, headers)

    def curl_set_option(self, option, value):
        """ used for general options like verbose, noprogress etc
            we also keep value internally so we can query for option status
        """
        if self.handle is not None:
            self.handle.setopt(option, value)
            self._curl_options[option] = value
            return True

    def curl_get_option(self, option):
        return self._curl_options.get(option)

    @property
    def curl_noprogress(self):
        return self._curl_options[pycurl.NOPROGRESS]

    @curl_noprogress.setter
    def curl_noprogress(self, zero_or_one):
        self.curl_set_option(pycurl.NOPROGRESS, zero_or_one)

    @property
    def curl_verbose(self):
        return self._curl_options.verbose

    @curl_verbose.setter
    def curl_verbose(self, zero_or_one):
        self.curl_set_option(pycurl.VERBOSE, zero_or_one)

    @property
    def request_abort(self):
        return self._request_abort

    def request_abort_set(self, reason_num=None, reason_msg=None):
        """ Raise or reset _request_abort property
            if reason_num is not None aborts current request by returning -1 while
            on accepting data or headers
            effetively server sees an (104 Connection reset by peer) or (32 broken pipe )
            thats the only way to disconnet an a connection
            its use makes more sence for streaming data connection
                Args:reason_num (None or int)
                    :reason_msg (str) a message
                Usasge: set it to Not None value to try to abort current request
                        main purpose is controlled exit from a streaming request
        """
        self._request_abort = (None,) if reason_num is None else (-1, reason_num, reason_msg)

    def on_progress(self, *args):
        sm = sum(args)
        if sm != self._vars.last_progress:
            self._vars.last_progress = sm
            self.on_progress_change(*args)
        return None  # all callbacks should return None - otherwise aborts

    def on_progress_change(self, download_t, download_d, upload_t, upload_d):
        upload_perc = (upload_d / upload_t) * 100 if upload_d != 0 else 0
        # no risk of div/0 (upload_t can't be 0 if upload_d !=0)
        download_perc = (download_d / download_t) * 100 if download_d != 0 else 0
        if upload_perc + download_perc:
            print (self.format_progress.format(download_perc, upload_perc))
        return None

    def on_request_start(self):
        """ parms are in self._last_req.parms """
        pass

    def on_request_end(self):
        pass

    def on_request_error_curl(self, err):
        """ default error handling, for curl (connection) Errors override method for any special handling
            see error codes http://curl.haxx.se/libcurl/c/libcurl-errors.html
            #(E_COULDNT_CONNECT= 7)
            return True to retry request
            raise an exception or return False to abort
        """
        if err[0] == pycurl.E_WRITE_ERROR and self._request_abort[0] is not None:  # 23
            return False  # normal termination requested by us
        raise ErrorRqCurl(err[0], err[1])

    def on_request_error_http(self, err):
        """ default error handling, for HTTP Errors override method for any special handling
            return True to retry request
            raise an exception or return False to abort
        """
        print ("Exception %s" % (err))
        raise ErrorRqHttp(err, self.response.status_http)

    def _perform(self):
        self.on_request_start()
        self._state.retries_curl = 0
        self._state.retries_http = 0
        retry = True
        while retry:
            self._state.retries_curl += 1
            self._state.retries_http += 1
            retry = False
            self.request_abort_set(None)
            self.response.reset()
            try:
                self.handle.perform()
            except pycurl.error as err:
                self.response.err_curl = err
                retry = self.on_request_error_curl(err)
            finally:
                self.response.status_http = self.handle.getinfo(pycurl.HTTP_CODE)
                if self.response.status_http > 299:
                    retry = self.on_request_error_http(self.response.status_http)
                self.on_request_end()
        return self.response

    def request(self, url, method, parms={}, multipart=False):
        self.handle_set(url, method, parms, multipart)
        return self._perform()

    def request_repeat(self):
        """ repeat last request
            override in subclasses to yield cursored results
            by modifying parts of pycurl options
        """
        return self._perform()

    def get(self, url, request_parms={}):
        return self.request(url, 'GET', request_parms)

    def post(self, url, request_parms={}):
        return self.request(url, 'POST', request_parms)

    def head(self, url, request_parms={}):
        return self.request(url, 'HEAD', request_parms)

    def set_user_agent(self, user_agent_str=None):
        if user_agent_str is None:
            user_agent_str = "%s v %s" % (self.__class__.__name__, __version__)
        self.kwargs.user_agent = user_agent_str
        if self.handle:
            self.handle.setopt(pycurl.USERAGENT, self.kwargs.user_agent)
        return user_agent_str

    def handle_on_headers(self, header_data):
        # first header is always the status line
        # last header_data is always a "\r\n"
        self.response.write_headers(header_data)
        if len(self.response.headers_raw) == 1:
            if self.response.status_provisional is not None:
                self._state.retries_curl = 0                # successful connection
                if self.response.status_provisional < 300:
                    self._state.retries_http = 0            # successful http status
        return self._request_abort[0]                       # disconnect if an abort

    def handle_on_write(self, data):
        """ this must return None or number of bytes received else connection terminates
        """
        self.response.data += data
        self.on_data(data)
        return None

    def on_data_default(self, data):
        """ default function to prosses data, i.e. return json.loads(data)
            override it or provide an on_data function on init
        """
        pass

    def handle_on_ioctl(self, ioctl, cmd):
        raise NotImplementedError

    def handle_on_debug(self, msg_type, msg_str):
        if msg_type == pycurl.INFOTYPE_TEXT:
            pass
        elif msg_type == pycurl.INFOTYPE_HEADER_IN:
            print("Header From Peer: %r" % msg_str)
        elif msg_type == pycurl.INFOTYPE_HEADER_OUT:
            print("Header Sent to Peer: %r" % msg_str)
        elif msg_type == pycurl.INFOTYPE_DATA_IN:
            pass
        elif msg_type == pycurl.INFOTYPE_DATA_OUT:
            pass

    def handle_reset(self):
        if self.handle:
            self.handle.reset()

    def handle_close(self):
        if hasattr(self, 'handle') and self.handle:
            self.handle.close()
            self.handle = None

    def __del__(self):
            self.handle_close()


class ClientStream(Client):
    format_stream_stats = "|{DHMS:s}|{chunks:15,d}|{data:14,d}|{data_perSec_avg:12,.2f}|"
    # format string for printing stats

    def __init__(self, credentials=None, data_separator="\r\n",
                 stats_every=10000,  # output statistics every N data packets 0 or None disables
                 **kwargs):
        self.data_separator = data_separator
        self.data_separator_len = len(data_separator)
        self.stats_every = stats_every
        self.counters = DotDot({'chunks': 0, 'data': 0})
        super(ClientStream, self).__init__(credentials, **kwargs)

    def handle_on_write(self, data_chunk):
        """ this must return None or number of bytes received else connection terminates"""
        # Note:tryied it with a list buffer and join with very marginal efficiency imporvements
        #      when actual data/chunks ratio is close to 1.
        #      Also cstringIO complicates things due to utf data handling
        # Note:descented classes can check len(self.resp_buffer) to protect
        #      from buffer ogveruns (not properly delimited streams)
        self.counters.chunks += 1
        self.resp_buffer += data_chunk
        if self.resp_buffer.endswith(self.data_separator):
            self.resp_buffer = self.resp_buffer[:-self.data_separator_len]
            if self.resp_buffer:           # @Note:ignore keep_alives strings ('')
                self.counters.data += 1
                self.on_data(self.resp_buffer)
                self.resp_buffer = ''
                if self.stats_every and self.counters.data % self.stats_every == 0:
                    self.print_stats()
        return self._request_abort[0]

    def on_data_default(self, data):
        """this is where actual data comes after chunks are merged,
           if you don't specify an on_data_cb function on init.
           Override it in descedants
        """
    def _reset_counters(self, counters_dict):
        for i in list(counters_dict.keys()):
            self.counters[i] = 0

    def on_request_start(self):
        self._reset_counters(self.counters)
        self.resp_buffer = ''  # for Streams we don't output to response object for efficiency
        self.dt_start = datetime.utcnow()

    def on_request_end(self):
        pass

    def time_since_start(self):
        return datetime.utcnow() - self.dt_start

    def stats_str(self):
        tmp = self.time_since_start().total_seconds()
        self.counters.data_perSec_avg = (self.counters.data / tmp)
        self.counters.DHMS = seconds_to_DHMS(tmp)
        return self.format_stream_stats.format(**self.counters)

    def print_stats(self):
        print (self.stats_str())