"""
some manual benchmarking tests
"""
import argparse
from twtPyCurl.py.requests import (Credentials, CredentialsProviderFile)
from twtPyCurl.twt.clients import (ClientTwtRest, ClientTwtStream)
import simplejson

def test_rest():
    tmp_credentials = Credentials(**CredentialsProviderFile()())
    clr = ClientTwtRest(credentials=tmp_credentials, allow_retries=False, name="test_r", verbose=2)
    r = clr.api.search.tweets(q="USA OR France", count=10)
    print (u"{}\n {}".format(r.data['search_metadata'], r.data['statuses'][0]['text']))
    # @note we need unicode  string since status[text] can be unicode it works on python3 OK
    return r


def stream_simulate():
    def on_data(data):
        return
        jdata = simplejson.loads(data)
        print jdata.get('text') 
    tmp_credentials = Credentials(**CredentialsProviderFile()())
    cls = ClientTwtStream(credentials=tmp_credentials, stats_every=10000, name="tst1", verbose=0, on_data_cb=on_data) 
    resp = cls.stream.statuses.filter.test(track="foo")
    return resp


def parse_args():
    parser = argparse.ArgumentParser(description="manual tests")
    parser.add_argument('--testfun',  choices=['test_rest', 'stream_simulate'],
                         help='test to run')
    parser.add_argument('-collection',    default=None, type=str,
                        help='name of output collection')
    parser.add_argument('-filepath',    default=None, type=str,
                        help='path to output csv file')
    parser.add_argument('--indexes',  dest='indexes', default=False, action='store_true',
                        help='create indexes after finish')
    return parser.parse_args()


def main():

        args = parse_args()
        print "starting with args", vars(args)
        if args.testfun == 'test_rest':
            test_rest()
        elif args.testfun == 'stream_simulate':
            stream_simulate()

if __name__ == "__main__":
    main()