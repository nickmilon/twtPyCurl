"""
module clients
"""

import logging
from twtPyCurl.py.utilities import DotDot
from twtPyCurl.twt.constants import TWT_URL_MEDIA_UPLOAD, TWT_URL_API_REST, TWT_URL_API_STREAM
from twtPyCurl.py.requests import (simplejson, pycurl, Client, ClientStream,
                                   ErrorRq, ErrorRqCurl, ErrorRqHttp, format_header)
from time import sleep
from twtPyCurl.twt.endpoints import EndPointsRest, EndPointsStream


LOG = logging.getLogger(__name__)
# LOG.addHandler(logging.NullHandler())
LOG.debug("loading module: " + __name__)


def backoff(seconds):  # default backoff method
    return sleep(seconds)


class ErrorTwtStreamDisconnectReq(ErrorRq):
    def __init__(self, error_number, msg):
        LOG.error(msg)
        super(ErrorTwtStreamDisconnectReq, self).__init__(error_number, msg)


class ErrorTwtMissingParameters(ErrorRq):
    def __init__(self, parm_names_lst):
        msg = "Missing parameters {}".format(" ".join(parm_names_lst))
        super(ErrorTwtMissingParameters, self).__init__(msg)


class ErrorRqHttpTwt(ErrorRq):
    def __init__(self, response):
        """ i.e:
        {'errors': [{'message': 'Query parameters are missing.', 'code': 25}]}
        {'errors': [{'message': 'Invalid or expired token.', 'code': 89}]}
        """
        if "errors" in list(response.data.keys()):
            rt = {'status': response.status_http, 'msg': response.data['errors'][0]['message'],
                  'code': response.data['errors'][0]['code']}
        else:
            rt = {'status': response.status_http}
        super(ErrorRqHttpTwt, self).__init__(rt)


class ClientTwtRest(Client):
    """client for Twitter `REST <https://dev.twitter.com/rest/public>`_ API
     examples require a credentials.json in user's home directory see :class:`~.CredentialsProviderFile`

    :param Credentials credentials: an instance of :class:`~.Credentials`
    :param dict kwargs: for acceptable kwargs see :class:`~.Client`

    :example:
        :ref:`check here <example-rest>`
    """
    def __init__(self, credentials, **kwargs):
        self._endpoints = EndPointsRest(parent=self)
        # composition with an endpoints object this allows to:
        # 1) call it using dot notation 2) validate endpoints
        super(ClientTwtRest, self).__init__(credentials=credentials, **kwargs)
        self.api = self._endpoints

    def request_ep(self, end_point, method='GET', parms={}, multipart=False):
        """request end point

        :param str end_point: twitter REST end point sortcut ie 'users/search'
        :param str method: request method one of GET or POST (defaults to GET)
        :param dict parms: parameters dictionary to pass to twitter

        :return: an instance of :class:`~.Response`

         .. Warning:: doesn't check end_point's validity will raise a twitter API error if not valid

        """
        frmt_str = TWT_URL_MEDIA_UPLOAD if end_point == "media/upload" else TWT_URL_API_REST
        if end_point == "statuses/update":
            # parms['status'] = parms['status'].encode('utf-8')
            parms = self._request_ep_media(parms)  # check for media

        return self.request(frmt_str.format(end_point), method, parms, multipart)

    def _request_ep_media(self, parms_dict):
        """this is a special case `see <https://dev.twitter.com/rest/reference/post/media/upload>`_
        a post request with media(binary file(s) content or media_data (base64 encoded content)
        upload content and modify parameters with media_ids
        there is a faster but complicated `endpoint <https://dev.twitter.com/rest/reference/post/media/upload-chunked>`_
        """
        media_parm_key = [i for i in ['media', 'media_data'] if i in list(parms_dict.keys())]
        if media_parm_key:
            media_parm_key = media_parm_key[0]
            media = parms_dict[media_parm_key]
            del parms_dict[media_parm_key]
            if not isinstance(media, (list, tuple)):  # make it a list
                media = [media]
            media_ids = []
            for m in media:
                rt = self.request_ep("media/upload", "POST", parms={media_parm_key: m}, multipart=True)
                media_ids.append(rt.data['media_id_string'])
            parms_dict['media_ids'] = ",".join(media_ids)
        return parms_dict

    def on_request_error_http(self, err):
        """we got an http error, if error < 500
        twitter's error message is in data i.e: {'errors': [{'message': 'Invalid or expired token.', 'code': 89}]}
        """
        if err < 500:
            self.response.data = simplejson.loads(self.response.data)
            raise ErrorRqHttpTwt(self.response)
        else:
            raise ErrorRqHttp(err, self.response)

    def on_request_end(self):
        self.response.data = simplejson.loads(self.response.data)

    def help(self, *args, **kwargs):
        """delegate help to be handled by endpoints object"""
        return self._endpoints._help(*args, **kwargs)

    def _twtUploadMP(self, file_or_path):
        return self.request(
            TWT_URL_MEDIA_UPLOAD,
            method='POST', parms={'media': (pycurl.FORM_FILE, file_or_path)}, multipart=True)

    def _adHocCmd_(self, element, *args, **kwargs):
        """this makes the trick of issuing requests against endpoints using dot notation syntax
        it is provided only for ease of use when issuing requests from command line.
        Applications should not use dot notation but instead call :func:`request_ep` method
        """
        dic_keys = str(element).split(self._endpoints.delimiter)[1:]  # Note get rid of root
        rt = self._endpoints.get_value_validate(dic_keys)
        if rt:
            # parms_dict= args[:-1]
            if rt.path.endswith("/id"):
                if not args:
                    raise ErrorTwtMissingParameters(['id'])
                endpoint = rt.path.replace("id", str(args[0]))
            else:
                endpoint = rt.path
            return self.request_ep(endpoint, rt.method, kwargs)
        else:
            return False


class ClientTwtStream(ClientStream):
    """*A client for twitter stream API*
    disconnect can be initiated by a message to disconnect from twitter
    or by the program by setting request_abort property to a tuple (code,message)

    :param Credentials credentials: an instance of :class:`~.Credentials`
    :param int stats_every: print statististics every n data packets defaults to 0 (disables statics)
    :param dict kwargs: for acceptable kwargs see :class:`~.Client` and :class:`~.ClientStream`

    :example:
        :ref:`check here <example-stream>`
    """
    # some strings for formating statistics #############################################
    format_stream_stats = ClientStream.format_stream_stats + "{t_data:14,d}|{t_msgs:8,d}|"
    format_stream_stats_header = format_header(format_stream_stats)
    # ####################################################################################

    def __init__(self, credentials=None, stats_every=1, **kwargs):
        self._reset_retry()
        self._endpoints = EndPointsStream(parent=self)  # class composition with endpoints object
        # delegate to endpoints could be done automatically but that would be too hackish
        self.stream = self._endpoints.stream
        self.sitestream = self._endpoints.sitestream
        self.userstream = self._endpoints.userstream
        self.name = kwargs.get('name')  # ancestor class will set it again but we need it now
        super(ClientTwtStream, self).__init__(credentials=credentials, stats_every=stats_every, **kwargs)
        self.counters.update({'t_data': 0, 't_msgs': 0})

    def _handle_init_end(self):
        self.curl_low_speed = (1, 60)

    def on_request_error_curl(self, err):
        """default error handling, for curl (connection) Errors override method for any special handling
        `see curl error codes <http://curl.haxx.se/libcurl/c/libcurl-errors.html>`_
        and `twitter streaming message types  <https://dev.twitter.com/streaming/overview/messages-types>`_
        return True to retry request raise an exception or return False to abort
        remember! after 1st unsuccessful retry probably the error will be E_COULDNT_CONNECT
        """
        LOG.debug("on_request_error_curl:" + str(err))
        if err[0] == pycurl.E_PARTIAL_FILE and self._state.retries_curl < 4:
            # err  (18, 'transfer closed with outstanding read data remaining')
            # usually happens in streams due to network/server temporary failure
            # possible remedy curl_setopt($curl, CURLOPT_HTTPHEADER, array('Expect:'))?
            if self.wait_on_nw_error(self._state.retries_curl) is not False:
                self._log_retry("pycurl", err[0], err[1], self._state.retries_curl)
                return True
        elif err[0] == pycurl.E_OPERATION_TIMEDOUT and err[1].startswith('Operation too slow'):
            # timed out as defined in LOW_SPEED_LIMIT LOW_SPEED_TIME
            # check the message too because err 28 can come also from Operation timed out after
            if self._state.retries_curl < 4 and self.wait_on_nw_error(self._state.retries_curl) is not False:
                self._log_retry("curl", err[0], err[1], self._state.retries_curl)
                return True
        elif err[0] == pycurl.E_COULDNT_CONNECT and self._state.retries_curl > 0 and self._state.retries_curl < 4:
            # we check retries_curl > 0  to make sure it is a reconnect attempt initiated by an other curl error
            if self.wait_on_nw_error(self._state.retries_curl) is not False:
                self._log_retry("curl", err[0], err[1], self._state.retries_curl)
                return True

        elif err[0] == pycurl.E_WRITE_ERROR and self._request_abort[0] is not None:
            code, msg = self.request_abort[1:]
            if code <= 12:  # https://dev.twitter.com/streaming/overview/messages-types
                if code in [2, 4, 7]:               # danger duplicate stream or something
                    self._raise(ErrorTwtStreamDisconnectReq, code, msg)
                elif code in [1, 10, 11, 12]:        # twitter malfunction
                    if self.wait_on_nw_error(self._state.retries_curl) is not False:
                        # try to reconnect
                        self._log_retry("twt_disconnect_req", code, msg, self._state.retries_curl)
                        return True
                    else:
                        raise self._raise(ErrorTwtStreamDisconnectReq, code + 100, "can't recover: " + str(msg))
                else:
                    raise self._raise(ErrorTwtStreamDisconnectReq, code, "we don't handle:" + str(msg))
            elif code == 1001:    # by convention > 1000 comes from our side
                    return False  # disconnect gracefully
            raise self._raise(ErrorTwtStreamDisconnectReq, code, "we don't handle:" + str(msg))
        self._raise(ErrorRqCurl, err[0], err[1])

    def on_request_error_http(self, err):
        """default error handling, for HTTP Errors override method for any special handling
        return True to retry request
        raise an exception or return False to abort
        """
        LOG.debug("on_request_error_http:" + str(err))
        if err in [500, 502, 503, 504] and self._state.retries_http < 4:
            if self.wait_on_http_error(self._state.retries_http):
                self._log_retry("http", err, "", self._state.retries_http)
                return True
        self.response.data = self.resp_buffer
        self._raise(ErrorRqHttp, err, self.response)

    def _log_retry(self, error_type, err_num, err_msg, cur_try):
        frmt = '{:s} -auto recovering {error_type} error num = {err_num!s} {err_msg}, retries{cur_try:2d}'
        LOG.debug(frmt.format(self.name, **locals()))

    @classmethod
    def wait_seconds(cls, try_cnt, initial, maximum, tries_max=5, exponential=False):
        '''see: https://dev.twitter.com/streaming/overview/connecting

        :Parameters:
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
        """this is where actual stream data comes after chunks are merged,
        if we don't specify an on_data_cb function on class initialization
        """
        # LOG.debug("on_data_default " + str(data))
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

    def on_twitter_data(self, data):
        """this is where actual twitter data comes unless you specify on_twitter_data_cb on
        class initialization, override in descendants or provide a on_twitter_data_cb
        """
        # example:
        # self.response.data = data
        # store last VALID data in any case (helpful in Error recovery)
        # for example by checking id or date
        # print data['text']

    def on_twitter_msg_base(self, msg):
        '''twitter messages come here first so we can handle some cases here
        `see message types and error codes here <https://dev.twitter.com/streaming/overview/messages-types>`_
        '''
        msg_type = list(msg.keys())[0]
        self.on_twitter_msg(msg_type, msg)
        if msg_type == 'disconnect':
            self.request_abort_set(msg[msg_type]['code'], msg[msg_type]['reason'])
            LOG.debug('disconnect requested by twitter {:s}'.format(msg))

    def on_twitter_msg(self, msg_type, msg):
        '''override it to handle twitter messages
        '''
        LOG.warning(str(msg))

    def request_ep(self, end_point, method, test_server=False, **kwargs):
        """shortcut to request constructs url from end_point

        :param str end_point: twitter REST end point sortcut ie 'stream/statuses/filter'
        :param str method: request method one of GET or POST (defaults to GET)
        :param bool test_server: if True channels request to test server
        :param dict kwargs: parameters dictionary to pass to twitter

        :return: an instance of :class:`~.Response`

        :Raises:  see request method
        :Usage:
            >>> client.request_ep("stream/statuses/filter","POST", track="breaking, news")

         .. Warning:: doesn't check end_point's validity will raise a twitter API error if not valid

        """
        ep_lst = end_point.split("/")
        url = TWT_URL_API_STREAM.format(ep_lst[0], "/".join(ep_lst[1:]))
        if test_server:
            '''modify url to send request to test server at port 8080'''
            url = url.replace("https", 'http').replace('.com', '.com:8080')
        self._state.retries_extra = 0   # see handle_on_headers (its reset to 0 by a successful connection)
        while self._state.retries_extra < 4:
            self._state.retries_extra += 1
            res = self.request(url, method, kwargs)
            LOG.debug('request_ep end headers {:s} buffer=[{:s}]'.format(self.response.headers, self.resp_buffer))
            if self.response.status_http == 200 and self.response.headers.get('connection') == 'close':
                # sometimes it returns with http 200 but connection:close in headers
                LOG.debug('retrying http 200 with connection closed {:d}'.format(self._state.retries_extra))
                sleep(10 * self._state.retries_extra)  # back off
            self._state.retries_extra = 99  # get out of here
        return res

    def help(self, *args, **kwargs):
        """delegate help to endpoints

        :Usage:
            >>> h = client.help("userstream/user")
            see at: ( https://dev.twitter.com/streaming/overview ) ...
        """
        return self._endpoints._help(*args, **kwargs)

    def _adHocCmd_(self, element, *args, **kwargs):
        """this makes the trick of issuing requests against endpoints using dot notation syntax
        it is provided only for ease of use when issuing requests from command line.
        Applications should not use dot notation but instead call :func:`request_ep` method
        """
        dic_keys = str(element).split(self._endpoints.delimiter)[1:]  # get rid of root
        if dic_keys[-1] == 'test':
            test_server = True
            dic_keys = dic_keys[:-1]
            if dic_keys[-1] == 'error':
                # simulate error testing
                return self.request_ep('/'.join(dic_keys), 'GET', test_server, **kwargs)
            else:
                rt = self._endpoints.get_value_validate(dic_keys)
        else:
            test_server = False
            rt = self._endpoints.get_value_validate(dic_keys)
        if rt:
            return self.request_ep(rt.path, rt.method, test_server, **kwargs)
        else:
            raise Exception("no such end point")

    def _reset_retry(self):
        self._retry_counters = DotDot({'retries': 0, 'bo_err_420': 60, 'bo_err_http': 5})
