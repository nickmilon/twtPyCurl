# -*- coding: utf-8 -*-
'''
Created on July 20, 2015

@author: milon
'''
import unittest
from copy import copy
from twtPyCurl.twt.clients import ClientTwtRest, ErrorRqHttpTwt
from twtPyCurl.py.requests import Credentials, CredentialsProviderFile, ErrorRqMissingKeys
from datetime import datetime
from time import sleep
class Test(unittest.TestCase):

    def setUp(self):
        self.credentials = None
        try:
            self.credentials = Credentials(**CredentialsProviderFile()()) 
        except (IOError, ErrorRqMissingKeys):
            pass

    def tearDown(self):
        pass

    def exreq(self, func, check=True, delay=0):
        """ execute a request and optionally check results
        delay write operations to simulate a human or to give time to twitter to process
        """
        res = func
        if check:
            self.assertEqual(res.status_http, 200, "{}{:d}".format("received HTTP Error", res.status_http))
        if delay:
            sleep(delay)
        return res

    def check_response(self, r):
        self.assertEqual(r.status_http, 200, "{}{:d}".format("received HTTP Error", r.status_http))

    def test_01_credentials(self):
        self.assertIsNotNone(self.credentials, "no credentials file 'credentials.json' or credentials not valid")

    def test_02(self):
        # self.assertEqual(1, 2, "1 NE 2")

        self.assertEqual(1, 1, "msg")

    def test_rest_quick(self):
        """a quick REST API test,
        checks:
            - ability Read Write Delete tweets/retweets
            - read write latency
            - basic http Errors
        """
        clr = ClientTwtRest(self.credentials)

        #    check invalid end point
        self.assertRaises(ErrorRqHttpTwt, clr.request_ep, "foo/bar")
        #     search for 1 tweet
        r = self.exreq(clr.api.search.tweets(q="Ελλάδα OR Россия", result_type='recent', count=1))
        # non Latin -check encodings
        status_search = r.data['statuses'][0]
        self.assertEqual(r.data['search_metadata']['count'], 1, "didn't find any tweets")

        #    Retweet
        r = self.exreq(self.exreq(clr.api.statuses.retweet.id(status_search['id']), delay=1))
        status_rt = r.data
        #    Post a tweet
        utc_posted = datetime.utcnow()
        r = self.exreq(clr.api.statuses.update(status=status_search['text'][:140]), delay=1)
        # original can contain long urls
        status_posted = r.data
        self.assertIn('source', r.data.keys(), "Not a status")
        #    Retreive posted tweet and check latency
        r = self.exreq(clr.api.statuses.show.id(status_posted['id']))
        self.assertLess((datetime.utcnow()-utc_posted).total_seconds(), 5, "post-retrieve latency > 5 seconds")
        self.assertEqual(status_posted['id'], r.data['id'], 'can not retrieve posted_status')
        #    check timeline to see if we get posted tweet
        r = self.exreq(clr.api.statuses.user_timeline(since_id=status_posted['id'] - 1)) 
        self.assertGreater(len(r.data), 0, "can't get any statuses in recent timeline")



        #    delete posted  and retwitted tweets
        r = self.exreq(clr.api.statuses.destroy.id(status_posted['id']), delay=1)
        self.assertEqual(status_posted['id'], r.data['id'], 'did not delete posted status')
        r = self.exreq(clr.api.statuses.destroy.id(status_rt['id']), delay=1)

        
        
        
        
        
        
if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()