'''
Created on Oct 13, 2014

@author: nickmilon
'''

from oauthlib.oauth1 import Client, SIGNATURE_HMAC, SIGNATURE_TYPE_AUTH_HEADER
from urllib import urlencode
from Hellas.Sparta import DotDot


def OAuth(application=None, user=None, **kwargs):
    """ better than class factory for efficiency"""
    if user is None:
        print "OATH 2" * 10
        return OAuth2(application, **kwargs)
    else:
        print "OATH 1" * 10
        return OAuth1(application, user, **kwargs)


class OAuth2(object):
    authstr = 'Authorization: Bearer %s'

    def __init__(self, **kwargs):
        self.consumer_access_token = kwargs['consumer_access_token']

    def get_oath_header(self, *args):
        return self.authstr % self.consumer_access_token


class OAuth1(object):
    """gets an OAuth 1 (RFC5849) header"""
    authstr = 'Authorization'

    def __init__(
            self,
            callback_uri=None,
            signature_method=SIGNATURE_HMAC,
            signature_type=SIGNATURE_TYPE_AUTH_HEADER,
            rsa_key=None, verifier=None,
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
        """ must be reevaluated for each and ever request except if same parms(url,method,parms)"""
        rt = self.client.sign('%s?%s' % (url, urlencode(parms)), http_method=http_method)
        return "%s: %s" % (self.authstr, rt[1][self.authstr].encode('utf-8'))
