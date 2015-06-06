'''
 
'''
import argparse
from twtPyCurl.py.requests import (Credentials, CredentialsProviderFile)
from twtPyCurl.twt.clients import (ClientTwtRest, ClientTwtStream)



def test_rest():
    tmp_credentials = Credentials(**CredentialsProviderFile()())
    clr = ClientTwtRest(credentials=tmp_credentials, allow_retries=False, name="test_r", verbose=2)
    r = clr.api.search.tweets(q="Greece, Athens", count=10)
    print (u"{}\n{:16s}-{}".format(r.data['search_metadata'], r.data['statuses'][0]['id_str'], r.data['statuses'][0]['text']))
    # @note we need unicode format string since status[text] can be unicode it works on python3 OK 

    return r




# ###################################################

# clr = ClientTwtRest(credentials=Credentials(**TEMP_CREDENTIALS), allow_retries=False, name="test_r", verbose=False)
# cls = ClientTwtStream(credentials=Credentials(**TEMP_CREDENTIALS), allow_retries=False, name="test_s",verbose=False)
# r = cls.stream.statuses.filter(track="(,:),-(")


def parse_args():
    parser = argparse.ArgumentParser(description="manual tests")
    parser.add_argument('--testfun',
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

if __name__ == "__main__":
    main()