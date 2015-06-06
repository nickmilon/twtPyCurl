"""
module clients
"""

from twtPyCurl.py.utilities import DotDot, FMT_DT_GENERIC
# file_to_base64
from twtPyCurl.twt.constants import TWT_URL_MEDIA_UPLOAD, TWT_URL_API_REST, TWT_URL_API_STREAM


from twtPyCurl.py.requests import (simplejson, pycurl, Client, ClientStream, CredentialsProviderFile,
                                   ErrorRq, ErrorRqCurl, ErrorRqHttp, format_header)
from time import sleep
from twtPyCurl.twt.endpoints import EndPointsRest, EndPointsStream
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(asctime)s %(funcName)s(%(lineno)d) -- %(message)s',
    datefmt=FMT_DT_GENERIC)

log = logging.getLogger(__name__)
log.info("loading module")


def backoff(seconds):  # default backoff method
    return sleep(seconds)


class ErrorTwtStreamDisconnectReq(ErrorRq):
    def __init__(self, error_number, msg):
        log.error(msg)
        super(ErrorTwtStreamDisconnectReq, self).__init__(locals())


class ErrorTwtMissingParameters(ErrorRq):
    def __init__(self, cls, parm_names_lst):
        msg = "Missing parameter(s)[%s] in %s" % (" ".join(parm_names_lst), cls.__class__.__name__)
        super(ErrorTwtMissingParameters, self).__init__({'msg': msg})


class ErrorRqHttpTwt(ErrorRq):
    def __init__(self, response):
        if "errors" in list(response.data.keys()):
            """ i.e:{'errors': [{'message': 'Query parameters are missing.', 'code': 25}]} """
            rt = {'status': response.status, 'msg': response.data['errors'][0]['message'],
                  'code': response.data['errors'][0]['code']}
        else:
            rt = {'status': response.status}
        super(ErrorRqHttpTwt, self).__init__(rt)


class ClientTwtRest(Client):
    """client for Twitter `REST <https://dev.twitter.com/rest/public>`_ API
     examples require a credentials.json in user's home directory see :class:`.py.requests.CredentialsProviderFile`

    :param Credentials credentials: an instance of :class:`.py.requests.Credentials`
    :param dict kwargs: see :class:`.py.requests.Client` and :class:`.py.requests.ClientStream`

    :example:
        :ref:`check here <example-rest>`
    """
    def __init__(self, credentials, **kwargs):
        self._endpoints = EndPointsRest(parent=self)
        # composition with an endpoints object this allows to:
        # 1) call it using dot notation 2) validate endpoints
        super(ClientTwtRest, self).__init__(credentials=credentials, **kwargs)
        self.api = self._endpoints

    def on_request_error_http(self, err):
        if err < 500:
            self.response.data = simplejson.loads(self.response.data)
            raise ErrorRqHttpTwt(self.response)
        else:
            raise ErrorRqHttp(err, self.response)

    def on_request_end(self):
        self.response.data = simplejson.loads(self.response.data)

    def help(self, *args, **kwargs):
        '''delegate help to be handled by endpoints object'''
        return self._endpoints._help(*args, **kwargs)

    def _twtUploadMP(self, file_or_path):
        return self.request(
            TWT_URL_MEDIA_UPLOAD,
            method='POST', parms={'media': (pycurl.FORM_FILE, file_or_path)}, multipart=True)

    def _adHocCmd_(self, element, *args, **kwargs):
        # print "args", args,"kwargs", kwargs
        dic_keys = str(element).split(self._endpoints.delimiter)[1:]  # Note get rid of root
        rt = self._endpoints.get_value_validate(dic_keys)
        if rt:
            # parms_dict= args[:-1]
            if rt.path.endswith("/id"):
                if not args:
                    raise ErrorTwtMissingParameters('id')
                url = TWT_URL_API_REST.format(rt.path.replace("id", str(args[0])))
            else:
                url = TWT_URL_API_REST.format(rt.path)
            return self.request(url, rt.method, parms=kwargs)
        else:
            return False


class ClientTwtStream(ClientStream):
    '''*A client for twitter stream API*
       disconnect can be initiated by a message to disconnect from twitter
       or by the program by setting request_abort property to a tuple (code,message)
    '''
    # some strings for formating statistics
    format_stream_stats = ClientStream.format_stream_stats + "{t_data:14,d}|{t_msgs:8,d}|"
    format_stream_stats_header = format_header(format_stream_stats)
    # ####################################################################################

    def __init__(self, credentials=None,
                 stats_every=1000,  # 0 or None to disable stats
                 **kwargs):
        self._reset_retry()
        self._endpoints = EndPointsStream(parent=self)  # class composition with endpoints object
        # delegate to endpoints could be done automatically but that would be too hackish
        self.stream = self._endpoints.stream
        self.sitestream = self._endpoints.sitestream
        self.userstream = self._endpoints.userstream
        self.name = kwargs.get('name')  # ancestor class will set it again but we need it now
        super(ClientTwtStream, self).__init__(credentials, stats_every=stats_every, **kwargs)
        self.counters.update({'t_data': 0, 't_msgs': 0})

    def on_request_error_curl(self, err):
        '''default error handling, for curl (connection) Errors override method for any special handling
        see error codes http://curl.haxx.se/libcurl/c/libcurl-errors.html
        #(E_COULDNT_CONNECT= 7)
        return True to retry request
        raise an exception or return False to abort
        '''
        if err[0] == pycurl.E_PARTIAL_FILE and self._state.retries_curl < 4:
            # err  (18, 'transfer closed with outstanding read data remaining')
            # usually happens in streams due to network/server temporary failure
            # possible remedy curl_setopt($curl, CURLOPT_HTTPHEADER, array('Expect:'))?
            if self.wait_on_nw_error(self._state.retries_curl) is not False:
                self._log_retry("pycurl", err[0], err[1], self._state.retries_curl)
                return True
        elif err[0] == pycurl.E_WRITE_ERROR and self._request_abort[0] is not None:
            code, msg = self.request_abort[1:]
            if code <= 12:  # https://dev.twitter.com/streaming/overview/messages-types
                if code in [2, 4, 7]:               # danger dublicate stream or something
                    raise ErrorTwtStreamDisconnectReq(code, msg)
                elif code in [1, 10, 11, 12]:        # twitter malfunction
                    if self.wait_on_nw_error(self._state.retries_curl) is not False:
                        # try to reconnect
                        self._log_retry("twt_disconnect_req", code, msg, self._state.retries_curl)
                        return True
                    else:
                        raise ErrorTwtStreamDisconnectReq(code + 100, "can't recover: " + str(msg))
                else:
                    raise ErrorTwtStreamDisconnectReq(code, "we don't handle:" + str(msg))
            elif code == 1001:    # by convention > 1000 comes from our side
                    return False  # disconnect gracefully
            raise ErrorTwtStreamDisconnectReq(code, "we don't handle:" + str(msg))
        # @TODO handle user streams etc
        raise ErrorRqCurl(err[0], err[1])

    def on_request_error_http(self, err):
        '''default error handling, for HTTP Errors override method for any special handling
        return True to retry request
        raise an exception or return False to abort
        '''
        if err in [500, 502, 503, 504] and self._state.retries_http < 4:
            if self.wait_on_http_error(self._state.retries_http):
                self._log_retry("http", err, "", self._state.retries_http)
                return True
        self.response.data = self.resp_buffer
        raise ErrorRqHttp(err, self.response)

    def _log_retry(self, error_type, err_num, err_msg, cur_try):
        frmt = '{:s} -auto recovering {error_type} error num= {err_num!s} {err_msg}, retries{cur_try:2d}'
        log.warning(frmt.format(self.name, **locals()))

    @classmethod
    def wait_seconds(cls, try_cnt, initial, maximum, tries_max=5, exponential=False):
        '''see https://dev.twitter.com/streaming/overview/connecting

        :Args:
            - try_cnt successive retries count starting with 0
            - initial float (seconds or fraction)
            - maximum float (seconds or fraction)
            - exponential back off exponentially if True else linearly

        :Returns:
            False or backoff value
        '''
        if try_cnt <= tries_max:
            vl = min((initial ** try_cnt) if exponential else initial * try_cnt, maximum)
            backoff(vl)
            return vl
        else:
            return False

    @classmethod
    def wait_on_nw_error(cls, current_try):
        return cls.wait_seconds(current_try, 0.25, 16)

    @classmethod
    def wait_on_http_error(cls, current_try):
        return cls.wait_seconds(current_try, 5, 320, exponential=True)

    @classmethod
    def wait_on_http_420(cls, current_try):
        return cls.wait_seconds(current_try, 60, 600)

    def on_data_default(self, data):
        '''this is where actual stream data comes after chunks are merged,
        if we don't specify an on_data_cb function on class initialization
        '''
#         try:
#             jdata = simplejson.loads(data)
#         except simplejson.scanner.JSONDecodeError as e:
#             # we can get here if response status was not 200
#             # or a misformed json (never happened)
#             # we don't raise Exception since probably it will raised at end of request
#             self.response.data = data
#             log.warning("json error={:s} body date={:s}".format(e, data))
#             print (e, "data="+data)
        jdata = simplejson.loads(data)
        if self._last_req.subdomain == 'stream':  # it is a statuses stream
            if jdata.get('source') is not None:   # it is a status (all statuses have source key sometimes can be '')
                self.counters.t_data += 1
                self.on_twitter_data(jdata)
            else:
                self.counters.t_msgs += 1
                self.on_twitter_msg_base(jdata)   # then it is a message
        else:
            pass
        # print(jdata.get('text', jdata))

    def on_twitter_data(self, data):
        '''this is where actual twitter data comes unless you specify on_twitter_data_cb on
        class initialization
        '''
        # self.response.data = data
        # store last VALID data in any case (helpfull in Error recovery)
        # for example by checking id or date
        # print data['text']

    def on_twitter_msg_base(self, msg):
        '''twitter messages come here first so we can handle some cases here
        `see error codes here <https://dev.twitter.com/streaming/overview/messages-types>`__
        '''
        msg_type = list(msg.keys())[0]
        self.on_twitter_msg(msg_type, msg)
        if msg_type == 'disconnect':
            self.request_abort_set(msg[msg_type]['code'], msg[msg_type]['reason'])

    def on_twitter_msg(self, msg_type, msg):
        '''override it to handle twitter messages
        '''
        print (msg)

    def reqstrm(self, end_point, method, test_server, **kwargs):
        '''shortcut to request constructs url from end_point

        .. Warning:: doesn't check if end_point is a valid end_point

        :Args:
            - end_point:(str) twitter stream end point i.e.: "subdomain/type/subtype"
            - method: (str) 'GET' or 'POST'
            - test_server (boolean) if True sends request to test server
            - kwars: request parameters to send to twitter API

        :Usage:

        >>> client.reqstrm("stream/statuses/filter","POST", track="breaking, news")

        :Returns: response object
        :Raises:  see request method
        '''
        ep_lst = end_point.split("/")
        url = TWT_URL_API_STREAM.format(ep_lst[0], "/".join(ep_lst[1:]))
        if test_server:
            '''modify url to send request to test server at port 8080'''
            url = url.replace("https", 'http').replace('.com', '.com:8080')
        return self.request(url, method, kwargs)

    def help(self, *args, **kwargs):
        '''delegate help to endpoints'''
        return self._endpoints._help(*args, **kwargs)

    def _adHocCmd_(self, element, *args, **kwargs):
        dic_keys = str(element).split(self._endpoints.delimiter)[1:]  # get rid of root
        if dic_keys[-1] == 'test':
            test_server = True
            dic_keys = dic_keys[:-1]
            if dic_keys[-1] == 'error':
                # simulate error testing
                return self.reqstrm('/'.join(dic_keys), 'GET', test_server, **kwargs)
            else:
                rt = self._endpoints.get_value_validate(dic_keys)
        else:
            test_server = False
            rt = self._endpoints.get_value_validate(dic_keys)
        if rt:
            return self.reqstrm(rt.path, rt.method, test_server, **kwargs)
        else:
            raise Exception("no such end point")

    def _reset_retry(self):
        self._retry_counters = DotDot({'retries': 0, 'bo_err_420': 60, 'bo_err_http': 5})

