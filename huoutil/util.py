#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import logging
import logging.handlers
import hashlib
import pickle
import codecs
import json
import subprocess
from collections import defaultdict, Mapping

import six

try:
    from urlparse import urlparse
except:
    pass

if six.PY2:
    try:
        from HTMLParser import HTMLParser
    except:
        pass
else:
    try:
        from html.parser import HTMLParser
    except:
        pass

try:
    # from lxml import etree  # not exist on hadoop
    import xml.etree.ElementTree as ET
except:
    pass

try:
    import numpy as np
except ImportError:
    pass

HOST_PATTEN = re.compile(r'https?://([a-zA-Z0-9.\-_]+)')


class Context(object):
    def __init__(self):
        self.config = None
        self.state = None


class StateError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class State(object):
    def __init__(self, path=None):
        self.path = path
        if os.path.exists(path):
            self.load()
        else:
            self.dict = {}

    def set(self, key, val):
        self.dict[key] = val
        self.save()

    def get(self, key):
        try:
            val = self.dict[key]
            return val
        except KeyError:
            raise StateError('key [%s] not exist' % key)

    def add(self, key, val):
        if key in self.dict:
            raise StateError('key [%s] already exist' % key)
        else:
            self.dict[key] = val
        self.save()

    def save(self):
        with codecs.open(self.path, 'wb', encoding='utf-8') as f:
            json.dump(self.dict, f)

    def load(self):
        with codecs.open(self.path, 'rb', encoding='utf-8') as f:
            self.dict = json.load(f)

    def __del__(self):
        try:
            self.save()
        except:
            pass


class ConfigError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class ConfigBase(object):
    """
    How to use:
        class Config(ConfigBase):
            def __init__(self, path=None):
                super(Config, self).__init__()
                self.NAME = 'Tom'
                self.AGE = 12
                self.LOVE = ['apple', 'banana']

                if path:
                    self.load_conf(path)
    """

    def __init__(self):
        self.path = ''
        self.name = ''
        self.type = ''

    def is_valid_key(self, key):
        if key in self.__dict__:
            return True
        else:
            return False

    def cast(self, key, value):
        init_value = self.__dict__[key]
        if isinstance(init_value, int):
            value = int(value)
        elif isinstance(init_value, float):
            value = float(value)
        elif isinstance(init_value, (list)):
            tokens = value.split(',')
            if init_value:
                element_type = type(init_value[0])
                value = [element_type(t) for t in tokens]
            else:
                value = tokens
            if type(init_value) == tuple:
                value = tuple(value)
            elif type(init_value) == set:
                value = set(value)
        else:
            pass
        return value

    def load_conf(self, path, typ=None):
        basename = os.path.basename(path)
        ext = basename.split('.')[-1]
        self.ext = ext
        self.name = '.'.join(basename.split('.')[:-1])
        if not typ:
            if ext == 'conf':
                typ = 'sh'
        if typ == 'sh':
            self.load_sh_conf(path)
        elif typ == 'json':
            self.load_json_conf(path)
        else:
            raise ValueError('invalid conf type: {0}. Please assign to  "typ" explicitly'.format(typ))
        return None

    def load_sh_conf(self, path):
        self.path = os.path.abspath(path)
        self.type = 'sh'
        with codecs.open(path, encoding='utf-8') as fc:
            for line in fc:
                if not line.strip('\n\r '):
                    continue
                if line.lstrip('\n\r ').startswith('#'):
                    continue
                tokens = line.rstrip('\n\r ').split('=')
                if len(tokens) < 2:
                    logging.warning('invalid config line: %s' % line)
                key = tokens[0]
                key = key.upper()
                if self.is_valid_key(key):
                    value = ''.join(tokens[1:])
                    value = self.cast(key, value)
                    self.__setattr__(key, value)
                else:
                    logging.warning('invalid key {0}'.format(key))
        return None

    def load_py_conf(self, path):
        self.path = os.path.abspath(path)
        self.type = 'py'
        import path

    def load_json_conf(self, path):
        self.path = os.path.abspath(path)
        self.type = 'json'
        with codecs.open(path, encoding='utf-8') as fc:
            json_str = ''
            for line in fc:
                if not line.lstrip().startswith('//'):
                    json_str += line.rstrip('\n')
            jsn = json.loads(json_str)
            for key, value in jsn:
                key = key.upper()
                if self.is_valid_key(key):
                    value = self.cast(key, value)
                    self.__setattr__(key, value)
                else:
                    logging.warning('invalid key {0}'.format(key))
        return None

    def dump(self, path):
        with codecs.open(path, 'wb', encoding='utf-8') as fp:
            for key, value in self.__dict__.items():
                fp.write('%s=%s\n' % (key, value))
        return None

    def log(self, logger):
        logger.info('log config:')
        for key, value in self.__dict__.items():
            logger.info('%s=%s' % (key, value))

    def __str__(self):
        return str(self.__dict__)

    def __unicode__(self):
        return self.__str__()


class NewConfig(object):
    def __init__(self, obj, default_property=False):
        self._default_property = default_property
        for name, value in obj.__dict__.items():
            if name.startswith('__'):
                continue
            else:
                setattr(self, name, value)

    def __getattr__(self, attr):
        if self._default_property:
            if attr not in self.__dict__:
                return None
        raise AttributeError("'{}' object has no attribute '{}'".format(type(self).__name__, attr))


def load_python_conf(conf_path, module_name='config', default_property=False):
    import imp
    config = imp.load_module(module_name, open(conf_path), conf_path, ('', 'r', imp.PY_SOURCE))
    newconfig = NewConfig(config, default_property)
    return newconfig


def mkdir(dir_name):
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    return None


def init_log(log_path,
             level=logging.INFO,
             stdout=False,
             when="D",
             backup=7,
             format="%(levelname)s: %(asctime)s: %(filename)s:%(lineno)d * %(thread)d %(message)s",
             datefmt="%Y-%m-%d %H:%M:%S"):
    """
    init_log - initialize log module

    Args:
      log_path      - Log file path prefix.
                      Log data will go to two files: log_path.log and log_path.log.wf
                      Any non-exist parent directories will be created automatically
      level         - msg above the level will be displayed
                      DEBUG < INFO < WARNING < ERROR < CRITICAL
                      the default value is logging.INFO
      when          - how to split the log file by time interval
                      'S' : Seconds
                      'M' : Minutes
                      'H' : Hours
                      'D' : Days
                      'W' : Week day
                      default value: 'D'
      format        - format of the log
                      default format:
                      %(levelname)s: %(asctime)s: %(filename)s:%(lineno)d * %(thread)d %(message)s
                      INFO: 12-09 18:02:42: log.py:40 * 139814749787872 HELLO WORLD
      backup        - how many backup file to keep
                      default value: 7

    Raises:
        OSError: fail to create log directories
        IOError: fail to open log file

    Example:
    init_log("./log/my_program")  # 日志保存到./log/my_program.log和./log/my_program.log.wf，按天切割，保留7天
    logging.info("Hello World!!!")

    """
    formatter = logging.Formatter(format, datefmt)
    logger = logging.getLogger()
    logger.setLevel(level)

    dir = os.path.dirname(log_path)
    if not dir:
        dir = './'
    if not os.path.isdir(dir):
        os.makedirs(dir)

    #该logger为root logger，其上可能会被加入多个StreamHandler输出到std,
    #一般我们只需要一个stdout就行，所以在stdout新加之前，去掉root logger上原有的所有StreamHandler
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)

    if stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(level)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

    handler = logging.handlers.TimedRotatingFileHandler(log_path + ".log", when=when, backupCount=backup)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    # https://www.jianshu.com/p/25f70905ae9d
    handler.suffix = '%Y-%m-%d'
    logger.addHandler(handler)

    err_handler = logging.handlers.TimedRotatingFileHandler(log_path + ".log.wf", when=when, backupCount=backup)
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(formatter)
    handler.suffix = '%Y-%m-%d'
    logger.addHandler(err_handler)
    return logger


def log_kv(seq, log=logging.info, prefix='', postfix='', item_sep=';', vv_sep=','):
    if not seq:
        lst = []
    elif isinstance(seq, dict):
        lst = seq.items()
    else:
        lst = seq
    item_str_list = []
    for item in lst:
        if len(item) == 0:
            k, v = '', ''
        elif len(item) == 1:
            k, v = item, ''
        elif len(item) == 2:
            k, v = item
        elif len(item) > 2:
            k, v = item[0], vv_sep.join(item[1:])
        item_str = u'{}[{}]'.format(k, v)
        item_str_list.append(item_str)
    log_str = ""
    if prefix:
        log_str += prefix + ": "
    log_str += item_sep.join(item_str_list)
    if postfix:
        log_str += " (" + postfix + ")"
    log(log_str)
    return None


def file2dict(path, kn=0, vn=1, sep='\t', encoding='utf-8', ktype=None, vtype=None, skip_line=0):
    """
    build a dict from a file.
    @param path: input file path
    @param kn: the column number of key
    @param vn: the column number of value
    @param sep: the field seperator
    @param encoding: the input encoding
    @param ktype: custom a function applied to the key of each line
    @param vtype: custom a function applied to the value of each line
    @param skip_line: skip lines number
    @return: a key value dict
    """
    d = {}
    line_number = 0
    with codecs.open(path, encoding=encoding) as fp:
        for line in fp:
            if not line.strip():
                continue
            line_number += 1
            if line_number <= skip_line:
                continue
            tokens = line.rstrip('\n\r ').split(sep)
            try:
                key = tokens[kn]
                if ktype:
                    key = ktype(key)
                if vn is None:
                    value = tokens[:kn] + tokens[kn + 1:]
                else:
                    value = tokens[vn]
                if vtype:
                    value = vtype(value)
                d[key] = value
            except IndexError:
                logging.exception('invalid line: %s' % line)
    return d


def file2dictlist(path, kn=0, vn=1, sep='\t', encoding='utf-8', dup=True, ktype=None, vtype=None, skip_line=0):
    """
    Build a dict from a file merging the values of same key into list.
    @param path: input file path
    @param kn: the column number of key
    @param vn: the column number of value
    @param sep: the field seperator
    @param encoding: the input encoding
    @param dup: True means allow values of list duplicate, False means values of list is unique
    @param ktype: custom a function applied to the key of each line
    @param vtype: custom a function applied to the value of each line
    @param skip_line: skip lines number
    @return: a key value dict
    """
    d = defaultdict(list)
    line_number = 0
    with codecs.open(path, encoding=encoding) as fp:
        for line in fp:
            if not line.strip():
                continue
            line_number += 1
            if line_number <= skip_line:
                continue
            tokens = line.rstrip('\n\r ').split(sep)
            try:
                key = tokens[kn]
                if ktype:
                    key = ktype(key)
                if vn is None:
                    value = tokens[:kn] + tokens[kn + 1:]
                else:
                    value = tokens[vn]
                if vtype:
                    value = vtype(value)
                if isinstance(value, list):
                    d[key].extend(value)
                else:
                    d[key].append(value)
            except:
                logging.exception('invalid line: %s' % line)
        for key in d.keys():
            if dup:
                d[key] = sorted(d[key])
            else:
                d[key] = sorted(list(set(d[key])))
    return d


def dict2file(d, path, encoding='utf-8', kfunc=None, vfunc=None, sep='\t'):
    """
    Dump a dict to a file.
    @param d: the dict to be dumpped
    @param path: the output file path
    @param encoding: the output file encoding
    @param kfunc: a function applied to the key
    @param vfunc: a function applied to the value
    @param sep: the seperator of the output file
    @return: always return None
    """
    with codecs.open(path, 'wb', encoding=encoding) as fo:
        for key, value in d.iteritems():
            if kfunc is not None:
                key = kfunc(key)
            if vfunc is not None:
                value = vfunc(value)
            outline = u'{}{}{}\n'.format(key, sep, value)
            fo.write(outline)
    return None


def file2ddict(path, k1n=0, k2n=1, vn=2, sep='\t', encoding='utf-8', k1type=None, k2type=None, vtype=None):
    """
    build a two level dict from a file.
    @param path: input file path
    @param k1n: the column number of key 1
    @param k1n: the column number of key 2
    @param vn: the column number of value
    @param sep: the field seperator
    @param encoding: the input encoding
    @return: a key value dict

    """
    d = defaultdict(dict)
    with codecs.open(path, encoding=encoding) as fp:
        for line in fp:
            tokens = line.rstrip('\n\r ').split(sep)
            try:
                k1 = tokens[k1n]
                k2 = tokens[k2n]
                if k1type:
                    k1 = k1type(k1)
                if k2type:
                    k2 = k2type(k2)
                if vn is None:
                    value = [tokens[i] for i in range(len(tokens)) if i != k1n and i != k2n]
                else:
                    value = tokens[vn]
                if vtype:
                    value = vtype(value)
                d[k1][k2] = value
            except IndexError:
                logging.exception('invalid line: %s' % line)
    return d


def ddict2file(d, path, encoding='utf-8', k1func=None, k2func=None, vfunc=None, sep='\t'):
    """
    Dump a two level dict to a file.
    @param d: the dict to be dumpped
    @param path: the output file path
    @param encoding: the output file encoding
    @param k1func: a function applied to the key 1
    @param k2func: a function applied to the key 2
    @param vfunc: a function applied to the value
    @param sep: the seperator of the output file
    @return: always return None
    """
    with codecs.open(path, 'wb', encoding=encoding) as fo:
        for k1, d2 in d.iteritems():
            if k1func is not None:
                k1 = k1func(k1)
            for k2, value in d2.iteritems():
                if k2func is not None:
                    k2 = k2func(k2)
                if vfunc is not None:
                    value = vfunc(value)
            outline = u'{}{}{}{}{}\n'.format(k1, sep, k2, sep, value)
            fo.write(outline)
    return None


def file2list(path, n=0, sep='\t', encoding='utf-8', typ=None, skip_line=0):
    """
    build a list from a file.
    @param path: input file path
    @param kn: the column number of key
    @param sep: the field seperator
    @param encoding: the input encoding
    @param skip_line: skip lines number
    @return: a list

    """
    d = []
    if not os.path.exists(path):
        return d
    line_number = 0
    with codecs.open(path, encoding=encoding) as fp:
        for line in fp:
            if not line.strip():
                continue
            line_number += 1
            if line_number <= skip_line:
                continue
            tokens = line.rstrip('\n\r ').split(sep)
            try:
                value = tokens[n]
                if typ:
                    value = typ(value)
                d.append(value)
            except IndexError:
                logging.exception('invalid line: %s' % line)
    return d


def file2set(path, n=0, sep='\t', encoding='utf-8', typ=None, skip_line=0):
    """
    build a set from a file.
    The parameters are the same as file2list
    @return: a set
    """
    return set(file2list(path, n=n, sep=sep, encoding=encoding, typ=typ, skip_line=skip_line))


def set2file(d, path, encoding='utf-8', func=None):
    """
    Dump a set to a file.
    @param d: the set to be dumpped
    @param path: the output file path
    @param encoding: the output file encoding
    @param func: a function applied to the value
    @return: always return None
    """
    with codecs.open(path, 'wb', encoding=encoding) as fo:
        for value in d:
            if func is not None:
                value = func(value)
            outline = u'{}\n'.format(value)
            fo.write(outline)
    return None


def cout(s, encoding='utf-8', newline=True):
    sys.stdout.write(s.encode(encoding))
    if newline:
        sys.stdout.write('\n')
    return None


def print_list(lst):
    for e in lst:
        p(e)
    return None


def print_matrix(matrix):
    for lst in matrix:
        print_list(lst)
    return None


def print_dict(d, encoding='utf-8'):
    for k, v in d.iteritems():
        outline = u'{}: {}'.format(k, v)
        print(outline.encode(encoding))
    return None


def p(obj, encoding='utf-8', indent=0):
    indent = indent
    typ = type(obj)
    if typ in (six.binary_type, six.text_type):
        logging.info(' ' * indent, )
        logging.info(obj.encode(encoding))
    elif typ == list or typ == tuple:
        for e in obj:
            p(e, indent=indent)
    elif typ == dict or typ == defaultdict:
        indent += 4
        for k, v in obj.items():
            p(k)
            p(v, indent=indent)
    else:
        logging.info(obj)
    return None


def splite_sentence(text):
    long_sep = u'\x03\x04。！？；!?;'
    short_sep = u'，,:： '
    long_sents = []
    offset_begin = 0
    short_sents = []
    for i, e in enumerate(text):
        if e in short_sep:
            short_sents.append(text[offset_begin:i + 1])
            offset_begin = i + 1
        elif e in long_sep:
            short_sents.append(text[offset_begin:i + 1])
            long_sents.append(short_sents)
            short_sents = []
            offset_begin = i + 1
        else:
            pass
    if offset_begin != len(text):
        short_sents.append(text[offset_begin:])
    if short_sents:
        long_sents.append(short_sents)
    return long_sents


def file_line_num(path, encoding='utf-8'):
    with codecs.open(path, encoding=encoding) as fp:
        for i, _ in enumerate(fp):
            pass
    return i + 1


def timer(logfmt=None):
    def actual_decorator(func):
        def wrapper(*arg, **kw):
            t1 = time.time()
            ret = func(*arg, **kw)
            t2 = time.time()
            ms = int((t2 - t1) * 1000)
            if logfmt is None:
                infomation = u'Timer {}: {}ms'.format(func.func_code, ms)
            else:
                infomation = logfmt.format(ms)
            logging.info(infomation)
            return ret

        return wrapper

    return actual_decorator


def load_matrix(path, skip_lines=0):
    matrix = []
    with open(path) as f:
        # skip the head lines
        for i in range(skip_lines):
            f.readline()
        for line in f.readlines():
            row = [float(e) for e in line.split()]
            matrix.append(row)
    return matrix


def dump_matrix(matrix, path, headlines=[]):
    with open(path, 'wb') as out:
        for line in headlines:
            out.write(line)
            out.write(os.linesep)
        for row in matrix:
            out.write(' '.join([str(e) for e in row]))
            out.write(os.linesep)
    logging.info('Finish writing matrix to %s' % path)
    return None


def pickle_me(obj, path, typ=None):
    with open(path, 'wb') as f:
        if typ == 'json':
            json.dump(obj, f)
        else:
            pickle.dump(obj, f)
    return None


def load_pickle(path, typ=None):
    with open(path) as f:
        if typ == 'json':
            return json.load(f)
        else:
            return pickle.load(f)


def xml2list(xml):
    ###### there is no lxml on hadoop ###########
    # try:
    #     # http://stackoverflow.com/questions/16396565/how-to-make-lxmls-iterparse-ignore-invalid-xml-charachters
    #     para = etree.XML(xml)
    # except etree.XMLSyntaxError:
    #     return None
    # subsent_list = para.xpath('//subsent/text()')
    # ret = [unicode(subsent) for subsent in subsent_list]
    # return ret
    ############################################

    try:
        para = ET.XML(xml.encode('utf-8'))
    except ET.ParseError:
        return None
    subsent_list = para.findall('./*/subsent')
    ret = [six.text_type(subsent.text) for subsent in subsent_list]
    return ret


def append_file(a, b, encoding='utf-8'):
    """
    append file a to file b
    """
    with codecs.open(a, 'rb', encoding=encoding) as fa, \
        codecs.open(b, 'ab', encoding=encoding) as fb:
        fb.write(fa.read())
    return None


class Answer(object):
    def __init__(self):
        self.sents = []
        self.query = ''
        self.url = ''


class Sentence(object):
    def __init__(self, s=''):
        self.query = ''
        self.s = s
        self.baseline = 0.0
        self.is_opinion = 0.0
        self.sent_sim_cooc = 0.0
        self.lexrank = 0.0
        self.word2vec = 0.0
        self.score = 0.0

    def __eq__(self, other):
        if isinstance(other, Sentence):
            return (self.query == other.query and self.s == other.s)
        else:
            return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.query + self.s)


def gaussian(x, mu, sig):

    ret = np.exp(-np.power(x - mu, 2.) / (2 * np.power(sig, 2.)))
    return ret


def gaussian_list(a):
    """
    a: a numpy array
    """
    if len(a) <= 1:
        return a
    mu = a.mean()
    sig = np.sqrt(np.sum((a - mu)**2) / len(a))
    return gaussian(a, mu, sig)


def median(lst):
    return sorted(lst)[len(lst) / 2]


def chunk(iterable, size):
    if not iterable:
        return []
    ret = []
    begin_idx = 0
    for i, e in enumerate(iterable):
        if i != 0 and i % size == 0:
            ret.append(iterable[begin_idx:i])
            begin_idx = i
    # append the last part
    ret.append(iterable[begin_idx:])
    return ret


def test_chunk():
    assert chunk([], 2) == []
    assert chunk([1], 2) == [[1]]
    assert chunk([1, 2], 2) == [[1, 2]]
    assert chunk([1, 2, 3], 2) == [[1, 2], [3]]


def is_number(s):
    try:
        _ = float(s)
        return True
    except ValueError:
        return False


def find_host(s):
    found = HOST_PATTEN.findall(s)
    return found


def url2host(url):
    if isinstance(url, (six.binary_type, six.text_type)):
        su = urlparse(url)
    else:
        su = url
    if su.netloc:
        return su.netloc
    else:
        return su.path.split('/')[0]


def norm_url(url):
    su = urlparse(url)
    new_url = su.netloc + su.path
    if su.scheme:
        new_url = su.scheme + "://" + new_url
    if new_url in ('3g.163.com/touch/article.html', 'wenku.baidu.com/link', 'baike.baidu.com/link',
                   'zhidao.baidu.com/link', 'www.welltang.com/webapp/baidu.php'):
        return url
    else:
        return new_url


def iter_by_key(iterable, key_idx=0, func=None, filter_func=None):
    info_list = []
    last_key = None
    key = None
    for item in iterable:
        if func:
            try:
                item = func(item)
            except:
                continue
        if filter_func and not filter_func(item):
            continue
        try:
            key = item[key_idx]
        except IndexError:
            continue
        remain = item[:key_idx] + item[key_idx + 1:]

        # Continue the same key
        if key == last_key:
            info_list.append(remain)

        # Begin a new Key
        else:
            # The line is not the first line in the file.
            if last_key is not None:
                yield (last_key, info_list)

            info_list = [remain]
            last_key = key
    # The last key of the file
    if info_list:
        yield (key, info_list)


def iter_file_by_key(path, key_idx=0, encoding='utf-8', sep='\t', func=None, filter_func=None):
    info_list = []
    key = None
    with codecs.open(path, encoding=encoding) as f:

        def line_func(line):
            return line.strip('\n\r ').split(sep)

        if func:
            new_func = lambda line: func(line_func(line))
        else:
            new_func = line_func
        for key, info_list in iter_by_key(f, key_idx=key_idx, func=new_func, filter_func=filter_func):
            yield (key, info_list)


def iter_file_in_dir(directory, encoding='utf-8'):
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        with codecs.open(path, encoding=encoding) as f:
            yield f


def dict_dot(dict_a, dict_b):
    production = 0.0
    for k, va in dict_a.items():
        try:
            vb = dict_b[k]
            production += va * vb
        except KeyError:
            continue
    return production


def list_dot(a, b):
    production = 0.0
    for i in range(min(len(a), len(b))):
        production += a[i] * b[i]
    return production


def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


class MLStripper(HTMLParser):
    """
    http://stackoverflow.com/a/925630/1282982
    """

    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)

    def strip_tags(self, html):
        self.reset()
        self.fed = []
        html = self.unescape(html)
        self.feed(html)
        return self.get_data()


def strip_tags(html):
    """
    If you need to strip multi times. It is better not to use the function but the class method.
    """
    s = MLStripper()
    html = s.unescape(html)
    s.feed(html)
    return s.get_data()


def send_mail_by_mailx(subject, content, user_list, sender=None, html=False):
    header = {}
    sender_name, sender_mail = None, None
    if sender:
        if isinstance(sender, (six.binary_type, six.text_type)):
            sender_name, sender_mail = sender, sender
        elif (isinstance(sender, list) or isinstance(sender, tuple)) and len(sender) == 2:
            sender_name, sender_mail = sender
        else:
            pass
    if sender_name and sender_mail:
        header['From'] = u'{} <{}>'.format(sender_name, sender_mail)
    if html:
        header['Content-Type'] = 'text/html'
    if header:
        header_str = '\n'.join([u'{}: {}'.format(k, v) for k, v in header.items()])
        subject = '$(echo -e "{}\n{}")'.format(subject, header_str)

    if isinstance(user_list, (six.binary_type, six.text_type)):
        user_list = [
            user_list,
        ]
    cmd = 'echo "{}" | mailx -s "{}" {}'.format(content, subject, ','.join(user_list))
    subprocess.call(cmd, shell=True)
    return None


def send_mail(subject, content, user_list, sender=None, html=False):
    send_mail_by_mailx(subject, content, user_list, sender=sender, html=html)
    return None


def update_dict(d, u):
    """
    update dict d by dict u
    d will be modified and returned
    From: http://stackoverflow.com/a/3233356/1282982
    """
    for k, v in u.iteritems():
        if isinstance(v, Mapping):
            r = update_dict(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def is_all_ascii(s):
    try:
        _ = str(s)
        return True
    except UnicodeEncodeError:
        return False
