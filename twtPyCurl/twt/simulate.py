'''
to test the client run:
python -m nm_py_stream.client server_url 100
where 100 is a parameter to print statistics every 100 documents received, can be any integer or (0 to suppress statistics) 
where server_url = any compliant stream server url 
'''
# see http://stackoverflow.com/questions/25347176/scaling-bjoern-to-multiple-servers

from twtPyCurl import _IS_PY3


if _IS_PY3:
        print ("this module is not compatible with python versions 3X")
        exit()
try:
    from gevent import monkey
    monkey.patch_all()                   # needed by Bottle for stream server
    from bottle import route, request, response, app
except ImportError:
    print ("this module requires gevent & bottle install those:>>> pip install gevent bottle")
    exit()

from datetime import datetime
import simplejson
import argparse
import weakref
import gzip
from random import randint
from gevent.pywsgi import WSGIServer
from gevent import sleep, Greenlet, pool, joinall
from twtPyCurl import _PATH_TO_DATA
from Hellas.Sparta import seconds_to_DHMS


GL_STREAM_DELAY = 0       # Default stream delay between data (seconds)
GL_REPORT_EVERY = 1
DATA_SEPARATOR = "\r\n"
GL_ERRORS_EVERY = 0
ERROR_CNT = 0

MSG_DISCONNECT = {
    "disconnect": {
        "code": 1,
        "stream_name": "sample",
        "reason": ""
        }
    }


class TweetsSampler():
    tweets_sample = None
    format_stats = "|{:3d}|{}|{:14,d}|{:10,d}|{:10,.1f}|{}|"
    instances = weakref.WeakSet()
    cls_dt_start = datetime.utcnow()
    cls_clients = 0

    def __init__(self, max_n=None):
        self._init_sample()
        TweetsSampler.cls_clients += 1
        self.cl_number = TweetsSampler.cls_clients
        self.max_n = max_n
        self.cnt = 0
        self.cnt_last = 0
        self.dt_start = datetime.utcnow()
        self.instances.add(self)

    def __iter__(self):
        return self

    @classmethod
    def _init_sample(cls):
        """initializes tweets_sample class variable with tweets from data
        we do it here on first instance creation to avoid side effects on sphinx documentation creation
        """
        if cls.tweets_sample is None:
            with gzip.open(_PATH_TO_DATA + "tweets_sample_10000.json.gz", 'rb') as fin:
                cls.tweets_sample = simplejson.load(fin)
            for i in range(0, len(cls.tweets_sample)):
                cls.tweets_sample[i]['_aux'] = {'SeqGlobal': i}
                cls.tweets_sample = [simplejson.dumps(doc) for doc in cls.tweets_sample]
                cls.tweets_sample_len = len(cls.tweets_sample)

    @classmethod
    def report(cls):
        while True:
            dt_now = datetime.utcnow()
            tmp = (dt_now - cls.cls_dt_start).total_seconds()
            num_of_instances = len(cls.instances)
            if num_of_instances == 0:
                print cls.format_stats.format(
                    -1, seconds_to_DHMS(tmp),
                    -1, -1, -1, "%2d" % (num_of_instances))
            else:
                for inst in list(cls.instances):
                    inst.report_stats()
                    sleep(0.01)
                    del inst
            sleep(GL_REPORT_EVERY - (num_of_instances * 0.01))

    def next(self):
        while self.max_n is None or self.cnt < self.max_n:
            self.cnt += 1
            return (self.cnt, self.tweets_sample[self.cnt % self.tweets_sample_len])
        raise StopIteration()

    def report_stats(self):
        if self.cnt > 0:
            dt_now = datetime.utcnow()
            tmp = (dt_now - self.dt_start).total_seconds()
            avg_docs_per_sec = (self.cnt / tmp)
            print self.format_stats.format(
                self.cl_number, seconds_to_DHMS(tmp),
                self.cnt, self.cnt-self.cnt_last, avg_docs_per_sec, '**')
            self.cnt_last = self.cnt

    def yield_tweets(self, max_n=None):
        format_yield = "%s" + DATA_SEPARATOR
        self.cnt = 0
        self.dt_start = datetime.utcnow()
        while max_n is None or self.cnt < self.max_n:
            self.cnt += 1
            yield format_yield % self.tweets_sample[self.cnt % self.tweets_sample_len], self.cnt


class Clients(object):
    def __init__(self):
        self.clients = []
        self.clients_records = []

    def add_client(self, client_obj):
        self.on_client_new(str(client_obj))
        self.clients.append(weakref.ref(client_obj, self.client_removed))
        self.clients_records.append(client_obj.record)

    def client_removed(self, client_obj):
        # print "client removed", str(client_obj())
        self.clients.remove(client_obj)
        live = [i()['id'] for i in self.clients if i()]
        removed_lst = [i for i in self.clients_records if i['id'] not in live]
        for i in removed_lst:
            self.clients_records.remove(i)
        self.on_client_removed(removed_lst)

    def on_client_new(self, client_str):
        # print "client added", client_str
        pass

    def on_client_removed(self, removed_lst):
        # print "removed_lst " * 5, removed_lst
        pass


class ServerClient(object):
    def __init__(self, request, response):
        idApp = str(request["bottle.app"]) .split(" ")[-1][:-1]
        idSes = str(request["wsgi.input"]) .split(" ")[-1][:-1]
        self.id = "%s_%s" % (idApp, idSes)
        # self.tweets_sample = tweets_sample
        self.record = {'id': self.id, 'REMOTE_ADDR': request['REMOTE_ADDR'],
                       'PATH_INFO': request['PATH_INFO']}
        self.REMOTE_ADDR = request['REMOTE_ADDR']
        self.PATH_INFO = request['PATH_INFO']
        self.dt_start = datetime.utcnow()
        self.dt_end = None

    def __str__(self):
        return str(self.record)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, str(self.id))

CLIENTS = Clients()


def stream(request, responce):
    response.content_type = 'application/json'
    response.status = '200 OK'
    tweets_sample = TweetsSampler()
    sc = ServerClient(request, response)
    CLIENTS.add_client(sc)
    for data, cnt in tweets_sample.yield_tweets(max_n=None):
        if GL_ERRORS_EVERY:
            rnd1 = randint(1, GL_ERRORS_EVERY)
            if rnd1 == 1:  # handle disconnect messages
                rnd2 = randint(1, 12)  # https://dev.twitter.com/streaming/overview/messages-types
                MSG_DISCONNECT['disconnect']['code'] = rnd2
                yield simplejson.dumps(MSG_DISCONNECT) + DATA_SEPARATOR
            if rnd1 == 2:
                rnd2 = randint(500, 504)
                response.status = rnd2
            else:
                yield data
        else:
            if cnt % 100 == 0:  # simulate keep_alives
                yield ''
            yield data
        sleep(GL_STREAM_DELAY)


@route('/1.1/statuses/sample.json', method=['GET'])
def stream_sample():
    return stream(request, response)


@route('/1.1/statuses/filter.json', method=['POST'])
def stream_filter():
    return stream(request, response)


@route('/1.1/statuses/firehose.json', method=['GET'])
def stream_firehose():
    return stream(request, response)


@route('/1.1/statuses/error.json', method=['GET', 'POST'])
def error_http():
    """ simulates http errors """
    global ERROR_CNT
    ERROR_CNT += 1
    if ERROR_CNT % 3 == 0:
        return stream(request, response)
    else:
        print ("SERVER ERROR_CNT:{:2d}".format(ERROR_CNT))
        response.status = int(request.query.get("err_code", 200))
        return simplejson.dumps({'http_error': response.status}) + DATA_SEPARATOR


def simple_stream_appl(environ, start_response):
    """simple pure gevent WSGIServer stream server
    kind of test to see if it's more efficient than bottle over bjoern
    TL;DR results show just a marginal improvement
    """
    status = '200 OK'
    headers = [
        ('Content-Type', 'application/json')
    ]
    start_response(status, headers)
    print ("streaming starting")
    for data in TweetsSampler().yield_tweets(max_n=None):
        yield data
        sleep(GL_STREAM_DELAY)


def parse_args():
    parser = argparse.ArgumentParser(description="set up server")
    parser.add_argument('-server',  default='gevent',   choices=['WSGIServer', 'gevent', 'bjoern'],
                        help='use bottle or gevent WSGIServer(only for Streaming)')
    parser.add_argument('-host',    default='0.0.0.0',
                        help='host name or ip defaults to:0.0.0.0')
    parser.add_argument("-port",    default=8080, type=int,
                        help='port number defaults to 8080')
    parser.add_argument("-delay",   default=0, type=float,
                        help='delay in seconds between data i.e:0.001, defaults to 0')
    parser.add_argument("-errors_every", default=0, type=int,
                        help='simulate possible errors inject errors every N tweets 0=never')
    parser.add_argument("-debug",   default=False, action="store_true",
                        help='debug (engages bottle catchall')
    parser.add_argument("-report",  default=1, type=int, help='report every N seconds')
    return parser.parse_args()


def main():
        args = parse_args()
        print "starting server", vars(args)
        global GL_STREAM_DELAY
        global GL_REPORT_EVERY
        global GL_ERRORS_EVERY
        GL_STREAM_DELAY = args.delay
        GL_REPORT_EVERY = args.report
        GL_ERRORS_EVERY = args.errors_every
        if args.server == 'WSGIServer':
            server = WSGIServer((args.host, args.port), simple_stream_appl, spawn=pool.Pool(100))
            server = Greenlet.spawn(server.serve_forever)
        else:
            appl = app()
            if args.debug:
                appl.catchall = False
            server = Greenlet.spawn(appl.run, host=args.host, port=args.port, server=args.server)
        report = Greenlet.spawn(TweetsSampler.report)
        joinall([report, server])

if __name__ == "__main__":
    main()
