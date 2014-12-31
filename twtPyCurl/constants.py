'''
Created on Nov 10, 2014

@author: milon
'''

TWT_API_VERSION = '1.1'
TWT_PIC = 'http://twitter.com/{screen_name:}/status/{id_str:}/photo/{cnt:}'
TWT_URL = 'https://{subdomain}.twitter.com/{path}'
TWT_URL_API = TWT_URL.format(subdomain='{{subdomain}}',
                             path='{version}/{{path}}.json').format(version=TWT_API_VERSION)
TWT_URL_API_REST = TWT_URL_API.format(subdomain='api', path='{}')
TWT_URL_API_REST2 = TWT_URL_API.format(subdomain='api', path='{}/{}')
TWT_URL_API_STREAM = TWT_URL_API.format(subdomain='{}', path='{}')
TWT_URL_MEDIA_UPLOAD = TWT_URL.format(subdomain='upload',
                                      path='{}/media/upload.json').format(TWT_API_VERSION)
TWT_URL_HELP_REST = TWT_URL.format(subdomain='dev', path='rest/{}')
TWT_URL_HELP_REST_REF = TWT_URL_HELP_REST.format('reference/{}/{}')  # (method, endpoint)
TWT_URL_HELP_STREAM = TWT_URL.format(subdomain='dev', path='streaming/overview')
