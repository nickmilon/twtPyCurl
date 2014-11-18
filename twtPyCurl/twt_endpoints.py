'''
Created on Oct 28, 2014

@author: milon
'''

import simplejson
from twtPyCurl import _PATH_TO_DATA
from twtPyCurl.constants import TWT_URL_HELP_STREAM, TWT_URL_HELP_REST, TWT_URL_HELP_REST_REF
from Hellas.Sparta import DotDot, AdHocTree


class EndPoints(object):
    _end_points = None
    _msg_wrong_ep = "no such end point, select one of the following:"
    delimiter = "/"

    def __init__(self, path_to_txt_file=None, parent=None):
        self.parent = parent
        self._attrs = AdHocTree(parent=parent, name="root")
        if self._end_points is None:
            self._eps_from_txt_file(path_to_txt_file)

    def __getattr__(self, attr):
        """ delegate to attrs object
        """
        return self._attrs.__getattr__(attr)

    def __getitem__(self, path):
        return self._attrs.__getitem__(path)

    @classmethod
    def _dict_insert(cls, partial_dict, key):
        rt = partial_dict.get(key)
        if rt is None:
            partial_dict[key] = DotDot()
            rt = partial_dict[key]
        return rt

    @classmethod
    def _dict_insert_ep(cls, ep_str, method):
        ep = ep_str.split(cls.delimiter)
        partial_dict = cls._end_points
        for i in ep:
            partial_dict = cls._dict_insert(partial_dict, i)
        partial_dict.method = method
        partial_dict.path = ep_str

    @classmethod
    def _eps_from_txt_file(cls, file_path):
        cls._end_points = DotDot()
        with open(file_path) as fin:
            _end_points = fin.readlines()
        _end_points = [i.strip().split(" ") for i in _end_points if not i.startswith("#")]
        #  start with '#' allow for remarks
        for end_point in _end_points:
            cls._dict_insert_ep(end_point[1].replace(":id", "id"), end_point[0])

    @classmethod
    def _help(cls, path=None, msg="HELP:", verbose=True):
        """ Args:path can be a string, list, or dictionary
                 see get_value method
        """
        dic = path if isinstance(path, dict) else cls.get_value(path)
        print (msg)
        print (simplejson.dumps(dic if verbose else dic.keys(), sort_keys=True,
                                indent=4, separators=(',', ': '), namedtuple_as_object=False))
        return dic

    @classmethod
    def get_value(cls, path_or_list=None):
        """ path_or_list can be a path of the form: '/users/search' or just 'users'
            or a list: ['users','search']
        """
        if path_or_list is None:
            path_or_list = []
        if not isinstance(path_or_list, list):
            path_or_list = path_or_list.split(cls.delimiter)
        dic = cls._end_points
        for k in path_or_list:
            try:
                dic = dic[k]
            except KeyError:
                return dic
        return dic

    @classmethod
    def get_value_validate(cls, uri_components_lst):
        rt = cls.get_value(uri_components_lst)
        if rt.get('method'):
            return rt
        else:
            cls._help(rt, msg=cls._msg_wrong_ep, verbose=False)
            return False


class EndPointsRest(EndPoints):
    _end_points = None

    def __init__(self, parent=None):
        if EndPointsRest._end_points is None:
            self._eps_from_txt_file("%s%s" % (_PATH_TO_DATA, 'twt_endpoints_rest.txt'))
        super(EndPointsRest, self).__init__(parent=parent)

    @classmethod
    def _help(cls, path_or_list_or_dict=None, msg="", verbose=False):
        rt = super(EndPointsRest, cls)._help(path_or_list_or_dict, verbose=verbose)
        msg = "{} \nsee at: ".format(msg)
        if rt.get('method') is None:
            msg = "{}{}".format(msg, TWT_URL_HELP_REST.format("public"))
        else:
            path = rt.path.replace("/id", "/:id") if rt.path.endswith("/id") else rt.path
            msg = "{}{}".format(msg, TWT_URL_HELP_REST_REF.format(rt.method.lower(), path))
        print (msg)
        return(rt, msg)

    def _adHocCmd_(self, element, *args, **kwargs):
        return args, kwargs


class EndPointsStream(EndPoints):
    _end_points = None
    # twt_help_base_url = "https://dev.twitter.com/streaming/overview"

    def __init__(self, parent=None):
        self.parent = parent
        if EndPointsStream._end_points is None:
            self._eps_from_txt_file("%s%s" % (_PATH_TO_DATA, 'twt_endpoints_stream.txt'))
        super(EndPointsStream, self).__init__(parent=parent)

    @classmethod
    def _help(cls, path_or_list_or_dict=None, msg="", verbose=False):
        msg = "%s see at: ( %s )" % (msg, TWT_URL_HELP_STREAM)
        rt = super(EndPointsStream, cls)._help(path_or_list_or_dict, msg, verbose)
        return(rt, msg)

    def _adHocCmd_(self, element, *args, **kwargs):
        dic_keys = str(element).split(self.delimiter)[1:]  # get rid of root
        rt = self.get_value_validate(dic_keys)
        if rt:
            return "_adHocCmd_", rt, element, args, kwargs
        else:
            return False

END_POINTS_REST = EndPointsRest()
END_POINTS_STREAM = EndPointsStream()
