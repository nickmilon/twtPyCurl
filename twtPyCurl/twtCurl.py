'''
Created on July 30, 2014
@author: nickmilon
'''


from Hellas.Sparta import DotDot
from Hellas.Pella import file_to_base64
from twtPyCurl.constants import TWT_URL_MEDIA_UPLOAD, TWT_URL_API_REST, TWT_URL_API_STREAM

from twtPyCurl.helpers.pcRequests import simplejson, pycurl, Client, ClientStream, Credentials,\
    CredentialsProviderFile, ErrorRq, ErrorRqCurl, ErrorRqHttp
from time import sleep

from twtPyCurl.twt_endpoints import EndPointsRest, EndPointsStream

TEMP_CREDENTIALS = CredentialsProviderFile()()


def backoff(seconds):  # default backoff method
    return sleep(seconds)


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
    """ client for Twitter rest api """
    def __init__(self, credentials=None,
                 **kwargs):
        self._endpoints = EndPointsRest(parent=self)
        # composition with an endpoints object this allowes to:
        # 1) call it using dot notation 2) validate endpoints
        super(ClientTwtRest, self).__init__(credentials, **kwargs)
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
        """ delegate help to endpoints """
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
    abort_reasons = DotDot
    abort_reasons.srv_r_rc = (10, 'server requested to reconnect ')

    def __init__(self, credentials=None,
                 stats_every=1000,  # 0 or None to disable stats
                 **kwargs):
        self._reset_retry()
        self._endpoints = EndPointsStream(parent=self)  # composition with endpoints object
        super(ClientTwtStream, self).__init__(credentials, stats_every=stats_every, **kwargs)
        # delegate to endpoints could be done automatically but that would be too tricky
        self.stream = self._endpoints.stream
        self.sitestream = self._endpoints.sitestream
        self.userstream = self._endpoints.userstream

    def on_request_error_curl(self, err, state):
        """ default error handling, for curl (connection) Errors override method for any special handling
            see error codes http://curl.haxx.se/libcurl/c/libcurl-errors.html
            #(E_COULDNT_CONNECT= 7)
            return True to retry request
            raise an exception or return False to abort
            return None to let caller handle it
        """

        if err[0] == pycurl.E_PARTIAL_FILE:
            # err  (18, 'transfer closed with outstanding read data remaining')
            # usually happens in streams due to network or server temporary failure
            # possible remedy curl_setopt($curl, CURLOPT_HTTPHEADER, array('Expect:'))?
            if self.wait_on_nw_error(state.tries) is not False:
                return True
        elif err[0] == pycurl.E_WRITE_ERROR and self.request_abort:  # 23
            if self.request_abort == self.abort_reasons.srv_r_rc:
                if self.wait_on_nw_error(state.tries) is not False:
                    return True
            else:
                return False
        raise ErrorRqCurl(err[0], err[1])

    @classmethod
    def wait_seconds(cls, try_cnt, initial, maximum, tries_max=5, exponential=False):
        """ see https://dev.twitter.com/streaming/overview/connecting
            Args    :try_cnt successive retries count starting with 0
                    :initial (seconds or fraction)
                    :maximum (seconds or fraction)
                    :exponential back off exponentially if True else linearly
            Returns:
        """
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
        """ this is where actual stream data comes after chunks are merged,
            if we don't specify an on_data_cb function on init
        """
        jdata = simplejson.loads(data)
        if self._last_req.subdomain == 'stream':  # it is a statuses stream
            if jdata.get('source'):               # it is a status (all statuses have source)
                self.on_twitter_data(jdata)
            else:
                self.on_twitter_msg(jdata)        # then it is message
        else:
            pass
        # print(jdata.get('text', jdata))

    def on_twitter_data(self, data):
        """ this is where actuall twitter data comes unless you specify on_twitter_data_cb on ini
        """
        self.response.data = data
        # store last VALID data in anycase (helpfull in Error recovery
        # for example by checking id or date
        # print data['text']

    def on_twitter_msg(self, msg):
        print msg

    def reqstrm(self, end_point, method, test_server, **kwargs):
        """
        shortcut to request constructs url from end_point
        does NOT check endpoint's validity
            Args:    end_point:(str) twitter stream end point i.e.: "subdomain/type/subtype"
                     method: 'GET' or 'POST'
                     test_server True or False
                     kwars: request parameters
            Usage:   >>> client.reqstrm("stream/statuses/filter","POST", track="breaking, news")
            Returns: response object
            Raises:  see request method
        """
        ep_lst = end_point.split("/")
        url = TWT_URL_API_STREAM.format(ep_lst[0], "/".join(ep_lst[1:]))
        if test_server:
            url = url.replace("https", 'http').replace('.com', '.com:8080')
        # print ("url ", url)
        return self.request(url, method, kwargs)

    def help(self, *args, **kwargs):
        """ delegate help to endpoints """
        return self._endpoints._help(*args, **kwargs)

    def _adHocCmd_(self, element, *args, **kwargs):
        dic_keys = str(element).split(self._endpoints.delimiter)[1:]  # get rid of root
        if dic_keys[-1] == 'test':
            test_server = True
            dic_keys = dic_keys[:-1]
        else:
            test_server = False
        rt = self._endpoints.get_value_validate(dic_keys)
        if rt:
            return self.reqstrm(rt.path, rt.method, test_server, **kwargs)
        else:
            raise Exception("no such end point")

    def _reset_retry(self):
        self._retry_counters = DotDot({'retries': 0, 'bo_err_420': 60, 'bo_err_http': 5})
# ################################################### @Todo remove vv
clr = ClientTwtRest(credentials=Credentials(**TEMP_CREDENTIALS), verbose=False)
cls = ClientTwtStream(credentials=Credentials(**TEMP_CREDENTIALS), verbose=False)
