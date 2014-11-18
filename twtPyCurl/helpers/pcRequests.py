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

    def __str__(self):
        if self.request_method and self.resource_url:
            return '%s (%s %s)' % (self._msg, self.method, self.url)
        return self._msg


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
        self.headers_raw = []
        self.data = ''
        self.status = None
        self._headers = None
        self.err_curl = None

    def write_headers(self, headers_data):
        self.headers_raw.append(headers_data.strip())

    @property
    def headers(self):
        """ set headers dictionary on demand and only once"""
        if self._headers is None:
            lh = self.headers_raw  # .strip().split("\r\n")
            hl = [hdr.split(': ') for hdr in lh if hdr and not hdr.startswith('HTTP/')]
            self._headers = DotDot((header[0].lower(), header[1]) for header in hl)
            self._headers.status_str = lh[0]
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
        """a list of request headers i.e: ['Accept: text/html', 'Max-Forwards : 2']"""
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
        return self._abort_request

    @request_abort.setter
    def request_abort(self, None_or_reason_tuple=None):
        """ Raise or reset _request_abort property
            if is not None aborts current request by returning a not None value while
            on accepting data or headers.
            thats the only way to disconnet an a connection
            its use makes more sence for streaming data connection
                Args:None_or_reason_tuple None or an abort reason tuple of the form:
                     (reason_code_int, reason_str)
                Usasge: set it to Not None value to try to abort current request
                        main purpose is controlled exit from a streaming request
        """
        self._abort_request = None_or_reason_tuple

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
            print self.format_progress.format(download_perc, upload_perc)
        return None

    def on_request_start(self):
        """ parms are in self._last_req.parms """
        pass

    def on_request_end(self):
        pass

    def on_request_error_curl(self, err, state):
        """ default error handling, for curl (connection) Errors override method for any special handling
            see error codes http://curl.haxx.se/libcurl/c/libcurl-errors.html
            #(E_COULDNT_CONNECT= 7)
            return True to retry request
            raise an exception or return False to abort
        """
        if err[0] == pycurl.E_WRITE_ERROR and self.request_abort:   # 23
            return False  # normal termination requested by us
        raise ErrorRqCurl(err[0], err[1])

    def on_request_error_http(self, err, state):
        """ default error handling, for HTTP Errors override method for any special handling
            return True to retry request
            raise an exception or return False to abort
        """
        print ("Exception %s" % (err))
        raise ErrorRqHttp(err, self.response)

    def _perform(self):
        self.on_request_start()
        retry = True
        state = DotDot()
        state.tries = -1  # 0 based (first try is number 0
        while retry:
            state.tries += 1
            retry = False
            self.request_abort = None
            self.response.reset()
            try:
                state.dt_perform_start = datetime.utcnow()
                self.perform()
                state.tries = -1
                print "state.tries ", state.tries
            except pycurl.error as err:
                print ("errrr ", err)
                state.dt_error_start = datetime.utcnow()
                state.time_since_perform = state.dt_error_start - state.dt_perform_start
                self.response.err_curl = err
                retry = self.on_request_error_curl(err, state)
            finally:
                self.response.status = self.handle.getinfo(pycurl.HTTP_CODE)
                if self.response.status > 299:
                    retry = self.on_request_error_http(self.response.status)
                self.on_request_end()
        return self.response

    def request(self, url, method, parms={},
                multipart=False
                ):
        self.handle_set(url, method, parms, multipart)
        return self.perform()

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
        self.response.write_headers(header_data)
        return self._abort_request  # disconnect if an abort

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
    format_stream_stats = "|{DHMS:s}|{chunks:12d}|{data:12d}|{data_perSec_avg:10.2f}|"
    # format string for printing stats

    def __init__(self, credentials=None, data_separator="\r\n",
                 stats_every=10000,  # output statistics every N data packets 0 or None disables
                 **kwargs):
        self.data_separator = data_separator
        self.data_separator_len = len(data_separator)
        self.stats_every = stats_every
        self.counters = DotDot({'chunks': 0, 'data': 0})
        super(ClientStream, self).__init__(credentials, **kwargs)

    def xx_handle_on_write(self, data_chunk):
        """ this must return None or number of bytes received else connection terminates"""
        if True:  # ###data !='':
            self.counters.chunks += 1
            self.resp_buffer.append(data_chunk)
            if data_chunk.endswith(self.data_separator):
                self.handle_on_write_record("".join(self.resp_buffer)[:-self.data_separator_len])
                # self.handle_on_write_record("".join(self.resp_buffer)[:2])
                self.resp_buffer = []  # l[:] = []
                return self._abort_request
            elif len(self.resp_buffer) > 100:
                raise ErrorRqStream(201, "buffer overun possibly stream isn't delimited ?")
                return True
        return self._abort_request

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
        return self._abort_request

    def on_data_default(self, data):
        """this is where actual data comes after chunks are merged,
           if you don't specify an on_data_cb function on init.
           Override it in descedants
        """
    def reset_counters(self):
        for i in list(self.counters.keys()):
            self.counters[i] = 0

    def on_request_start(self):
        self.reset_counters()
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
