"""
some useful utilities used in multiple places
:author: nickmilon
"""
from copy import copy
import re

FMT_DT_GENERIC = "%y%m%d %H:%M:%S"                                    # generic date time format
FMT_DHMS_DICT = "{days:03d}-{hours:02d}:{minutes:02d}:{seconds:02d}"  # format for printing out timedelta objects


def format_header(frmt):
    """creates a header string from a new style format string useful when printing dictionaries

    :param str frmt: a new style format string
    :returns: a table header string

    assumptions for frmt specs:
        - all have a separator = '|' and include a key size format directive i.e.: '{key:size}'
        - no other character allowed in frmt except separator

    :Example:
        >>> frmt = '|{count:12,d}|{percent:7.2f}|{depth:5d}|'
        >>> data_dict = {'count': 100, 'percent': 10.5, 'depth': 10}
        >>> print(format_header(frmt)); print(frmt.format(**data_dict))
        ............................
        |   count    |percent|depth|
        ............................
        |         100|  10.50|   10|

    """
    names = re.sub("{(.*?):.*?}", r"\1", frmt)
    names = [i for i in names.split("|") if i]
    frmt_clean = re.sub("\.\df", r"", frmt)  # get read of floats i.e {:8.2f}
    sizes = re.findall(r'\d+', frmt_clean)
    frmt_header = "|{{:^{}}}" * len(sizes) + "|"
    header_frmt = frmt_header.format(*sizes)
    header = header_frmt.format(*names)
    header_len = len(header)
    header = "{}\n{}\n{}\n".format("." * header_len, header, "." * header_len)
    return header.strip()


class DotDot(dict):
    """
    A dictionary that can handle dot notation to access its members (useful when parsing JSON content),
    to keep casting to it cheap it doesn't handle creating multilevel keys using dot notation. For this functionality
    look for `easydict <https://github.com/makinacorpus/easydict>`_  or `addict <https://github.com/mewwts/addict>`_

    :Example:
        >>> dd = DotDot()
        >>> dd.a = 1
        >>> dd
        {'a': 1}
        >>> dd.b.c = 100
        'AttributeError ...  '
        >>> dd.b = {'b1': 21, 'b2': 22}
        >>> dd.b.b3 = 23
        >>> dd
        {'a': 1, 'b': {'b1': 21, 'b2': 22}, 'b3': 23}

    .. Warning:: don't try to delete a nested key using dot notation i.e: `del dd.a.b.b1` (it will fail silently)
    """
    def __getattr__(self, attr):
        try:
            item = self[attr]
        except KeyError as e:
            raise AttributeError(e)    # expected Error by pickle on __getstate__ etc
        if isinstance(item, dict) and not isinstance(item, DotDot):
            item = DotDot(item)
        return item
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class AdHocTree(object):
    """builds an arbitrary tree structure using object attributes

    :Usage:
        >>> aht = AdHocTree().foo.bar
        >>> aht
        <AdHocTree: root/foo/bar>
            - can be extended:
        >>> newtree = newtree = aht.new_foo.new_bar
        >>> newtree
        <AdHocTree: root/foo/bar/new_foo/new_bar>
    """

    __slots__ = ['parent', 'name']  # don't create __dict__ just those 2 slots

    def __init__(self, parent=None, name="root"):
        """
        :param obj parent: parent object, defaults to None
        :param str name: name of the Tree, defaults to root
        """
        self.parent = parent
        self.name = name

    def __call__(self, *args, **kwargs):
        """calls _adHocCmd_ method on root's parent if exists"""
        elements = list(self)
        try:
            cmd = elements[-1].parent.__getattribute__('_adHocCmd_')
            # we don't use get or getattr here to avoid circular references
        except AttributeError:
            raise NotImplementedError("_adHocCmd_ {:!s}".format((type(elements[-1].parent))))
        return cmd(elements[0], *args, **kwargs)

    def __getattr__(self, attr):
        return AdHocTree(self, attr)

    def __reduce__(self):
        """its pickle-able"""
        return (self.__class__, (self.parent, self.name))

    def __iter__(self):
        """iterates breadth-first up to root"""
        curAttr = self
        while isinstance(curAttr, AdHocTree):
            yield curAttr
            curAttr = curAttr.parent

    def __reversed__(self):
        return reversed(list(self))

    def __str__(self, separator="/"):
        return self.path()

    def __repr__(self):
        return '<{}: {}>'.format(self.__class__.__name__, self.path())

    def path(self, separator="/"):
        """:returns: a string representing the path to root element separated by separator"""
        rt = ""
        for i in reversed(self):
            rt = "{}{}{}".format(rt, i.name, separator)
        return rt[:-1]

    def root_and_path(self):
        """:returns: a tuple (parent, [members,... ]"""
        rt = []
        curAttr = self
        while isinstance(curAttr.parent, AdHocTree):
            print "attr", curAttr
            rt.append(curAttr.name)
            curAttr = curAttr.parent
        rt.reverse()
        return (curAttr.parent, rt)


def seconds_to_DHMS(seconds, as_string=True):
    """converts seconds to Days, Hours, Minutes, Seconds

    :param int seconds: number of seconds
    :param bool as_string: to return a formated string defaults to True
    :returns: a formated string if as string else a dictionary
    :Example:
        >>> seconds_to_DHMS(60*60*24)
        001-00:00:00
        >>> seconds_to_DHMS(60*60*24, False)
        {'hours': 0, 'seconds': 0, 'minutes': 0, 'days': 1}
    """
    d = DotDot()
    d.days = int(seconds // (3600 * 24))
    d.hours = int((seconds // 3600) % 24)
    d.minutes = int((seconds // 60) % 60)
    d.seconds = int(seconds % 60)
    return FMT_DHMS_DICT.format(**d) if as_string else d


def dict_copy(a_dict, exclude_keys_lst=[], exclude_values_lst=[]):
    """a **sallow** copy of a dict excluding items in exclude_keys_lst and exclude_values_lst
    useful for copying locals etc...

    :param dict a_dict: a dictionary
    :param list exclude_keys_lst: a list of dictionary keys to exclude from copying
    :param list exclude_values_lst: a list of dictionary values to exclude from copying
    :returns: a dictionary

    .. Warning:: remember returned dict it is **NOT** a deep copy of original
    """
    return dict([copy(i) for i in a_dict.items()
                 if i[0] not in exclude_keys_lst and i[1] not in exclude_values_lst])
