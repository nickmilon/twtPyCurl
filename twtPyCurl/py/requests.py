'''
:module: requests (pyCurl based Requests)

a lightweight small footprint interface to pyCurl provides the base for twtCurl

.. Warning:: although classes defined here can possibly be used for generic http(s)
   requests those have only been tested for requests
   to twitter REST and streaming API
'''
import simplejson
import pycurl
import urllib
import urlparse
import logging
from datetime import datetime
from twtPyCurl import __version__, path
from twtPyCurl.py.utilities import (dict_encode, DotDot, seconds_to_DHMS, format_header)
from twtPyCurl.py.oauth import OAuth1, OAuth2

LOG = logging.getLogger(__name__)
# LOG.addHandler(logging.NullHandler())
LOG.debug("loading module: " + __name__)


class ErrorRq(Exception):
    """Exceptions base"""


class ErrorRqMissingKeys(ErrorRq):
    pass


class ErrorRqCredentialsNotValid(ErrorRq):
    pass


class ErrorRqHttp(ErrorRq):
    """HTTP error"""
    def __init__(self, http_code, msg=''):
        super(ErrorRqHttp, self).__init__(http_code, msg)


class ErrorRqCurl(ErrorRq):
    """Exceptions raised by Curl"""
    def __init__(self, err_number, msg):
        super(ErrorRqCurl, self).__init__(err_number, msg)


class CredentialsProvider(object):
    """Generic oAuth credentials provider class
    """
    appl_keys = ['id_appl', 'consumer_access_token']
    user_keys = ['id_user', 'user_name', 'consumer_key', 'consumer_secret',
                 'access_token_key', 'access_token_secret']

    @classmethod
    def get_credentials(cls, id_appl, id_user=None):
        """must return a dictionary with all appl_keys and user_keys
        classes inherited from this base class must implement this method
        """
        raise NotImplementedError

    @classmethod
    def on_revoke_credentials(self, appl_id, user_id):
        """inherited classes should handle this to inform the application """
        raise NotImplementedError

    @classmethod
    def validate(self, credentials_dict):
        """validates credentials dictionary against missing keys
        """
        lsr_cr_keys = list(credentials_dict.keys())
        rt = [i for i in self.appl_keys if i not in lsr_cr_keys]
        if 'id_user' in lsr_cr_keys:  # it is user credentials
            rt.extend([i for i in self.user_keys if i not in lsr_cr_keys])
        if rt:
            raise ErrorRqMissingKeys("missing keys: {}".format(",".join(rt)))
        return credentials_dict


class CredentialsProviderFile(CredentialsProvider):
    """simple file based credentials provider reads credentials from the contents of a json file

    .. seealso::
        - a sample file with user credentials at: twt_data/sample_credentials_user.json
        - a sample file with application credentials at: twt_data/sample_credentials_application.json
    """
    def __call__(self, *args, **kwargs):
        rt = self.get_credentials(*args, **kwargs)
        return self.validate(rt)

    @classmethod
    def get_credentials(cls, file_path=None):
        """
        :param str file_path: full path name to a file, defaults to credentials.json in user's home directory
        :returns: a validated credentials dictionary
        :raises: IOError on file error
        """
        if file_path is None:  # defaults to credentials.json in home directory
            file_path = "{}/credentials.json".format(path.expanduser("~"))
        with open(file_path, "r") as fin:
            try:
                crd_dict = simplejson.load(fin)
            except IOError:
                raise
        return cls.validate(crd_dict)


class Credentials(object):
    """stores OAuth1 or OAuth2 credentials and provides OAuth headers
    """
    def __init__(self, **kwargs):
        kwargs = DotDot(kwargs)
        self.id_user = kwargs.get('id_user')                    # defaults to None (application credentials)
        self.user_name = kwargs.get('user_name', self.id_user)  # defaults to id_user
        self.id_appl = kwargs.id_appl                           # required
        if len(list(kwargs.keys())) > 1:
            if self.id_user is None:
                self._is_appl = True
                self.OAuth = OAuth2(**kwargs)
            else:
                self._is_appl = False
                self.OAuth = OAuth1(**kwargs)
            self._id = (self.id_appl, self.id_user)
            self._id_str = "{}/{}".format(*self._id)
        else:
            raise ErrorRqCredentialsNotValid()

    def is_appl(self):
        """
        :returns: Boolean: True if credentials belong to an application False if belong to an application user
        """
        return self._is_appl

    @property
    def id(self):
        """
        :returns: tuple: (application id, user id)
        """
        return self._id

    @property
    def id_str(self):
        """
        :returns: (str) representation of intance's id
        """
        return self._id_str

    def get_oath_header(self, *args):
        """
        :returns: str: the OAuth header to be used by a request
        """
        return self.OAuth.get_oath_header(*args)

    def on_revoke_credantials(self):
        """descendants can override to handle revoking credentials"""
        raise NotImplementedError

    def __repr__(self):
        return '<{:s}:{:s}>'.format(self.__class__.__name__, self.id_str)

    def __str__(self):
        return self.__repr__()


class Response(object):
    ''''a lightweight HTTP response class handles only basic things since we want it to be fast'''
    def __init__(self):
        self.reset()

    def reset(self):
        """we reset the properties between requests so we don't have to create a new instance between each request
        """
        # caution status_provisional we will only get it if we:
        # a) hit a server and b) server sends proper headers
        self.headers_raw = []
        self.data = ''
        self.status_http = None         # status(int) from curl we get it only well after perform
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
        """sets (on demand and only once) and returns headers dictionary
        constructing the dictionary is not cheap - so we avoid only do it when this method is called
        :returns: the headers dictionary
        """
        if self._headers is None:
            lh = self.headers_raw
            hl = [hdr.split(': ') for hdr in lh if hdr and not hdr.startswith('HTTP/')]
            self._headers = DotDot((header[0].lower(), header[1]) for header in hl)
            if lh:
                self._headers.status_raw = lh[0]
        return self._headers
        # response['status'] = self.curl_handle.getinfo(pycurl.HTTP_CODE)


class Client(object):
    """this is a minimal class to execute HTTP Requests via curl/pycurl,
    for efficiency urls are NOT url encoded since it is not necessary for our use case.
    all arguments are optional

    :param tuple request: (url, method, parms) if specified request will be executed following instance creation
           see :func:`request`
    :param Credentials credentials: an instance of :class:`Credentials`
    :param function on_data_cb: a call back with a single parameter to execute when data from request are ready,
           if missing or None instance's :func:`on_data_default` will be called instead
    :param str user_agent: a user agent string to use in request header (defaults to class name + 'v '+ __version)
    :param str name: name for this instance if missing a default based on instance's id is provided see: :func:`name`
    :param bool allow_retries: if True allows instance to perform retries to recover from an error if possible (defaults to True)
    :param bool allow_redirects: if True allows automatic redirects (defaults to False)
    :param int verbose: set to 0 for silent mode 1 to turn curl verbose and progress on, 2 to turn curl debug mode on (defaults to 0)


    :example:
        >>> client = Client()
        >>> response = client.request(url="https://www.yandex.com/", method='GET')
        >>> response.data
        '<!DOCTYPE html><html class="i-ua_js_no i-ua_css_standart i-ua_browser_unknown" lang="en">.......'
        >>> responce.status_http
        200
    """
    format_progress = "|progress |download:{:6.2f}%| upload:{:6.2f}%|"

    def __init__(
        self,
        request=None,           # a request in the form  (url, method, parameters_dictionary
        credentials=None,       # credentials (see credentials class)
        on_data_cb=None,        # a function to execute when data arrive
        user_agent=None,        # a user agent string to use in request
        name=None,              # a name to distinguish the instance (defaults to str(id(instance))[-4:]
        allow_retries=True,     # allows instance to perform retries
        verbose=0,              # 0 for silent mode 1 to turn curl verbose on, 2 to turn curl debug mode on
        allow_redirects=False   # if True allows automatic redirects
            ):
            self._curl_options = DotDot()
            self._vars = DotDot({'last_progress': None})
            self._last_req = DotDot()
            self._state = DotDot()  # keeps state of retries etc.
            self.on_data = on_data_cb if on_data_cb else self.on_data_default
            self.handle = None
            self.response = Response()
            self.credentials = credentials
            self.request_headers = []
            self.verbose = verbose
            self.set_user_agent(user_agent)
            self.name = name
            self.allow_retries = allow_retries
            self._allow_redirects = allow_redirects
            if request:
                self.request(request[0], request[1], request[2])

    @property
    def name(self):
        """
        :returns: instance's name
        """
        return self._name

    @name.setter
    def name(self, name=None):
        self._name = name if name is not None else str(id(self))[-4:]

    @property
    def request_headers(self):
        """
        :returns: current request headers
        """
        return self._request_headers

    @request_headers.setter
    def request_headers(self, request_headers):
        """sets request headers
        :param list request_headers: request headers i.e:['Accept: text/html', 'Max-Forwards : 2']
        """
        self._request_headers = request_headers

    @property
    def credentials(self):
        return self._credentials

    @credentials.setter
    def credentials(self, credentials):
        '''a Credentials class instance'''
        self._credentials = credentials

    def _handle_init(self):  # @Todo any reason why we don't call it from __init__  ?
        """initializes pycurl handle, override for any special set up
        `for options details see <http://curl.haxx.se/libcurl/c/curl_easy_setopt.html>`_
        """
        self.handle = pycurl.Curl()
        if self._allow_redirects is True:
            self.handle.setopt(pycurl.FOLLOWLOCATION, True)
        self.handle.setopt(pycurl.USERAGENT, self.user_agent)
        self.handle.setopt(pycurl.ENCODING, 'deflate, gzip')
        self.handle.setopt(pycurl.HEADERFUNCTION, self.handle_on_headers)
        self.handle.setopt(pycurl.WRITEFUNCTION, self.handle_on_write)
        self.handle.setopt(pycurl.PROGRESSFUNCTION, self.on_progress)
        self.handle.setopt(pycurl.NOPROGRESS, 0 if self.verbose else 1)
        # self.handle.setopt(pycurl.NOSIGNAL, 1)
        # self.handle.setopt(pycurl.CONNECTTIMEOUT, 10)
        # self.handle.setopt(pycurl.TIMEOUT, 50)  # defaults to 300 ?
        self.curl_verbose = 1 if self.verbose > 0 else 0
        self.curl_noprogress = 1 if self.verbose < 1 else 0     # defaults to Not verbose
        if self.verbose == 2:
            self.handle.setopt(pycurl.DEBUGFUNCTION, self.handle_on_debug)
        self._handle_init_end()

    def _handle_init_end(self):
        """modify in descedants if additional initialization requirements"""

    def _raise(self, err_class, *args):
        """use this mechanism to raise critical exceptions
        useful to notify applications before raising the exception and maybe try a remedy in application level
        especially useful in a threading environment to notify main thread before raising
        it calls _on_exception and raises the exception only if it returns True
        """
        LOG.exception("exception {:s}{:s}".format(err_class, args))
        if self._on_exception(err_class, *args):
            raise err_class(*args)

    def _on_exception(self, err_class, *args):
        """descendants can specify any special handling
        """
        return True

    def handle_set(self, url, method, request_parms, multipart=False):  # multipart relevant only for POST
        """
        :param str url: url to be used by request
        :param str method: method to be used by request
        :param dict request_parms: request's parameters
        :param boolean multipart: defaults to False, specify True for a multipart request
        :raises: KeyError: if method is not one of GET POST or HEAD
        """
        self._last_req.parms = (url, method, request_parms, multipart)
        if self.handle is None:
            self._handle_init()
        headers = [i for i in self.request_headers]  # @Note add copy of standard headers
        if self.credentials is not None:
                # although not needed if authorization type is application
                # set it any way, so credentials can be reseted on the fly
                self._last_req.url_parsed = urlparse.urlparse(url)
                self._last_req.subdomain = self._last_req.url_parsed.netloc.split('.')[0]
                headers.append('Host: %s' % (self._last_req.url_parsed.netloc))
                headers.append(self.credentials.get_oath_header(url, method, {} if multipart else request_parms))
        if method == 'GET' or method == 'HEAD':
            tmp = urllib.urlencode(request_parms)
            tmp = "%s%s%s" % (url, "?" if tmp else '', tmp)
            self.handle.setopt(pycurl.URL, tmp)
            self.handle.setopt(pycurl.HTTPGET, 1)
        elif method == 'POST':
            self.handle.setopt(pycurl.URL, url)
            if multipart:
                self.handle.setopt(pycurl.HTTPPOST, list(request_parms.items()))
                self.handle.setopt(pycurl.CUSTOMREQUEST, "POST")
                # http://pycurl.cvs.sourceforge.net/pycurl/pycurl/tests/test_post2.py?view=markup
            else:
                self.handle.setopt(pycurl.POSTFIELDS, urllib.urlencode(request_parms))
                # no need to setopt(pycurl.POST, 1) POSTFIELDS sets it to POST anyway
                # headers.append("Content-Transfer-Encoding: base64")   do we need it ?
        else:
            raise KeyError('method:[%s] is not supported' % method)
        self.handle.setopt(pycurl.HTTPHEADER, headers)

    def curl_set_option(self, option, value):
        '''used for general options like verbose, noprogress etc,
        we store values internally so we can query for option status
        `for options details see <http://curl.haxx.se/libcurl/c/curl_easy_setopt.html>`_
        '''
        if self.handle is not None:
            self.handle.setopt(option, value)
            self._curl_options[option] = value
            return value
        else:
            raise ErrorRq({'msg': 'pycurl handle has not been set'})

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
        return self._curl_options[pycurl.VERBOSE]

    @curl_verbose.setter
    def curl_verbose(self, zero_or_one):
        self.curl_set_option(pycurl.VERBOSE, zero_or_one)

    @property
    def curl_low_speed(self):
        return (self._curl_options[pycurl.LOW_SPEED_LIMIT], self._curl_options[pycurl.LOW_SPEED_TIME])

    @curl_low_speed.setter
    def curl_low_speed(self, speed_time_tuple):
        """sets low speed parameters raises curl Error pycurl.E_OPERATION_TIMEDOUT (28) if limits exceeded
        useful for discovering network connection breaks
        `see libcurl <http://curl.haxx.se/libcurl/c/CURLOPT_LOW_SPEED_TIME.html>`_
        :Parameters:
            - speed_time_tuple (tuple) (limit bytes, seconds)
        """
        self.curl_set_option(pycurl.LOW_SPEED_LIMIT, speed_time_tuple[0])
        self.curl_set_option(pycurl.LOW_SPEED_TIME, speed_time_tuple[1])

    @property
    def request_abort(self):
        return self._request_abort

    def request_abort_set(self, reason_num=None, reason_msg=None):
        """Raise or reset _request_abort property
        if reason_num is not None aborts current request by returning -1 while
        on accepting data or headers
        effectively server sees an (104 Connection reset by peer) or (32 broken pipe)
        thats the only way to disconnect a connection
        its use makes more sense for streaming data connection

        :param int reason_num: None or an integer that defines the reason we want to abort current request
        :param str reason_msg: a string that describes the reason we want to abort current request

        :Usage: set it to a Not None value to abort current request
                main purpose is controlled exit from a streaming request
        """

        self._request_abort = (None,) if reason_num is None else (-1, reason_num, reason_msg)

    def on_progress(self, *args):
        """pycurl on_progress callback gives progress statistics"""
        sm = sum(args)
        if sm != self._vars.last_progress:
            self._vars.last_progress = sm
            self.on_progress_change(*args)
        return None  # all callbacks should return None - otherwise aborts

    def on_progress_change(self, download_t, download_d, upload_t, upload_d):
        """called by :func:`on_progress` if it senses a change in progress (to avoid endless progress reports)"""
        upload_perc = (upload_d / upload_t) * 100 if upload_d != 0 else 0
        download_perc = (download_d / download_t) * 100 if download_t != 0 and upload_d != 0 else 0
        if upload_perc + download_perc:
            print (self.format_progress.format(download_perc, upload_perc))
        return None

    def on_request_start(self):
        '''called when a request starts override in descendants as needed'''
        pass

    def on_request_end(self):
        '''called when a request ends override in descendants as needed'''
        pass

    def on_request_error_curl(self, err):
        """default error handling, for curl (connection) Errors override method for any special handling
        `see libcurl error codes <http://curl.haxx.se/libcurl/c/libcurl-errors.html>`_
        return True to auto retry request, raise an exception or return False to abort
        """
        if err[0] == pycurl.E_WRITE_ERROR and self._request_abort[0] is not None:  # 23
            return False    # normal termination requested by us
        raise ErrorRqCurl(err[0], err[1])

    def on_request_error_http(self, err):
        """default error handling, for HTTP Errors override method for any special handling
        return True to auto retry request, raise an exception or return False to abort
        """
        raise ErrorRqHttp(err, self.response.status_http)

    def request(self, url, method, parms={}, multipart=False):
        """
         .. Warning:: 
            - Currently we don't url-encode the url, clients should encode it if needed before making a call.
            - Response object returned is hot i.e a reference to client.response will be invalid
              after next request. Clients should copy it if they intend to reuse it in future.

        :param str url: requests' url
        :param str method: request
        :param dict kwargs: parameters dictionary to pass to twitter

        :return: an instance of :class:`~.Response`

        :Raises:  proper HTTP or pyCurl errors
        """
        parms = dict_encode(parms)
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
            self.handle_set(url, method, parms, multipart)
            # we must call handle_set it every time to get fresh credentials
            # (Out-of-sync timestamp in case we retry after long time)
            self._before_perform()
            try:
                self.handle.perform()
            except pycurl.error as err:
                self.response.err_curl = err
                retry = self.on_request_error_curl(err) if self.allow_retries else False
                # LOG.info("retry _SBOU =" + str(retry))
            finally:
                self.response.status_http = self.handle.getinfo(pycurl.HTTP_CODE)
                if self.response.status_http > 299:
                    if self.allow_retries:
                        retry = self.on_request_error_http(self.response.status_http)
                    else:
                        retry = False
                self.on_request_end()
        return self.response

    def _before_perform(self):
        pass

    def del_request(self, url, method, parms={}, multipart=False):
        self.handle_set(url, method, parms, multipart)
        return self._perform()

    def request_repeat(self):
        """repeat last request, override in subclasses to yield cursor results by modifying parts of pycurl options"""
        return self._perform()

    def get(self, url, request_parms={}):
        """shortcut to a GET request"""
        return self.request(url, 'GET', request_parms)

    def post(self, url, request_parms={}):
        """shortcut to a POST request"""
        return self.request(url, 'POST', request_parms)

    def head(self, url, request_parms={}):
        """shortcut to a HEAD request"""
        return self.request(url, 'HEAD', request_parms)

    def set_user_agent(self, user_agent_str=None):
        """sets user agent header string
        :param str user_agent_str: user agent string defaults class name + version
        """
        if user_agent_str is None:
            user_agent_str = "%s v %s" % (self.__class__.__name__, __version__)
        self.user_agent = user_agent_str
        if self.handle:
            self.handle.setopt(pycurl.USERAGENT, self.user_agent)
        return user_agent_str

    def handle_on_headers(self, header_data):
        # first header is always the status line
        # last header_data is always a "\r\n"
        self.response.write_headers(header_data)
        if len(self.response.headers_raw) == 1:
            if self.response.status_provisional is not None:
                self._state.retries_curl = 0                # successful connection
                self._state.retries_extra = 0               # extra counter provision to be used by descendants
                if self.response.status_provisional < 300:
                    self._state.retries_http = 0            # successful http status
        return self._request_abort[0]                       # disconnect if an abort

    def handle_on_write(self, data):
        """this must return None or number of bytes received else connection terminates"""
        self.response.data += data
        self.on_data(data)
        return None

    def on_data_default(self, data):
        """ default function to process data, i.e. return json.loads(data),
        override it or provide an on_data_cb function on init
        """
        pass

    def handle_on_ioctl(self, ioctl, cmd):
        raise NotImplementedError

    def handle_on_debug(self, msg_type, msg_str):
        """pyCurl's handle on debug call back"""
        if msg_type == pycurl.INFOTYPE_TEXT:
            pass
        elif msg_type == pycurl.INFOTYPE_HEADER_IN:
            LOG.debug("Header From Peer: %r" % msg_str)
        elif msg_type == pycurl.INFOTYPE_HEADER_OUT:
            LOG.debug("Header Sent to Peer: %r" % msg_str)
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
    """
    :param str data_separator: string used by server to separate data
    :param int stats_every: report statistics every n data packets (specify 0 to suppress stats)
    :param dict kwargs: any other argument(s) as specified in :class:`Client`
    """
    format_stream_stats = "|{name:8s}|{DHMS:12s}|{chunks:15,d}|{data:14,d}|{avg_per_sec:12,.2f}|"
    format_stream_stats_header = format_header(format_stream_stats)
    # format strings for printing statistics

    def __init__(self,
                 data_separator="\r\n",
                 stats_every=10000,  # output statistics every N data packets 0 or None disables
                 **kwargs):
        self.data_separator = data_separator
        self.data_separator_len = len(data_separator)
        self.stats_every = stats_every
        self.stream_started = False
        self.counters = DotDot({'name': self.name[:4], 'chunks': 0,
                                'DHMS': '', 'avg_per_sec': 0,
                                'data': 0})
        super(ClientStream, self).__init__(**kwargs)

    def handle_on_write(self, data_chunk):
        '''data call back receives chunks of data from server and
        this must return None or number of bytes received else connection terminates
        '''
        # LOG.debug("counters.chunks= {:d} chunk [{:s}]".format(self.counters.chunks, data_chunk))
        # @Note:this piece of code is super critical for speed, since it is the main loop executed all the time
        #       data comes in.
        #       currently it uses string concatenation to amend data
        #       tried it with a list buffer and join with very marginal efficiency improvements
        #       when actual data/chunks ratio is close to 1.
        #       Also cstringIO can't be used since it complicates things due to utf data handling
        # @Note:descented classes can check len(self.resp_buffer) to protect
        #       from buffer overruns (not properly delimited streams)
        self.counters.chunks += 1
        self.resp_buffer += data_chunk
        if self.resp_buffer.endswith(self.data_separator):
            self.resp_buffer = self.resp_buffer[:-self.data_separator_len]
            if self.resp_buffer:           # @Note:ignore keep_alives strings ('')
                self.counters.data += 1
                self.on_data(self.resp_buffer)
                self.resp_buffer = ''
                if self.stats_every and self.counters.data % self.stats_every == 0:
                    if self.stats_every == self.counters.data:
                        print (self.format_stream_stats_header)
                    self.print_stats()
        return self._request_abort[0]

    def on_data_default(self, data):
        '''this is where actual data comes after data chunks cleansing,
           if you don't specify an on_data_cb function on init
           Override it in descendants for your use case or specify an on_data_cb function
        '''
    def _reset_counters(self, counters_dict):
        for k in list(counters_dict.keys()):
            if k not in ['name', 'DHMS']:
                self.counters[k] = 0

    def on_request_start(self):
        self._reset_counters(self.counters)
        self.resp_buffer = ''  # for streams we don't output to response object for efficiency
        self.dt_start = datetime.utcnow()

    def _before_perform(self):
        self.resp_buffer = ''

    def on_request_end(self):
        pass

    def time_since_start(self):
        return datetime.utcnow() - self.dt_start

    def stats_str(self):
        """
        :returns: a string containing operation(s) statistics
        """
        tmp = self.time_since_start().total_seconds()
        self.counters.avg_per_sec = (self.counters.data / tmp)
        self.counters.DHMS = seconds_to_DHMS(tmp)
        return self.format_stream_stats.format(**self.counters)

    def print_stats(self):
        """prints a string containing operation(s) statistics"""
        print (self.stats_str())
