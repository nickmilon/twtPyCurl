'''a small foot print oauth module'''

from oauthlib.oauth1 import Client, SIGNATURE_HMAC, SIGNATURE_TYPE_AUTH_HEADER
from urllib import urlencode
from twtPyCurl.py.utilities import DotDot


def OAuth(application, user=None, **kwargs):
    '''a function to abstract OAuth1 / OAuth2 classes (more efficient than a class factory)

    :param str application: application name
    :param str user: user name
    :param dict kwargs: arguments to be passed to OAuth class

    :return:
        - an OAuth2 class instance if user is None
        - an OAuth1 class instance if user is not None
    '''
    return OAuth2(application, **kwargs) if user is None else OAuth1(application, user, **kwargs)


class OAuth2(object):
    authstr = 'Authorization: Bearer %s'

    def __init__(self, **kwargs):
        self.consumer_access_token = kwargs['consumer_access_token']

    def get_oath_header(self, *args):
        """
        :return: an OAuth 2 header
        """
        return self.authstr % self.consumer_access_token


class OAuth1(object):
    '''gets an OAuth 1 (RFC5849) header'''
    authstr = 'Authorization'

    def __init__(
            self,
            callback_uri=None,
            signature_method=SIGNATURE_HMAC,
            signature_type=SIGNATURE_TYPE_AUTH_HEADER,
            rsa_key=None,
            verifier=None,
            decoding='utf-8',
            **kwargs):
        kwargs = DotDot(kwargs)
        if signature_type:
            signature_type = signature_type.upper()

        self.client = Client(
            kwargs.consumer_key,
            kwargs.consumer_secret,
            kwargs.access_token_key,
            kwargs.access_token_secret,
            callback_uri, signature_method,
            signature_type, rsa_key, verifier, decoding=decoding)

    def get_oath_header(self, url, http_method, parms):
        '''call it to get a recalculated OAuth1 header

        :param str url: request URL
        :param str http_method: request method GET|POST|PUT etc.......
        :param dict parms: request parameters

        :return: an OAuth 1 header
        '''
        rt = self.client.sign('%s?%s' % (url, urlencode(parms)), http_method=http_method)
        return "%s: %s" % (self.authstr, rt[1][self.authstr].encode('utf-8'))
