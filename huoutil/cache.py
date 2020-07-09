#!/usr/bin/env python
# coding=utf-8

import json
import six

if six.PY2:
    import cPickle as pickle
else:
    import pickle

try:
    import redis
except ImportError:
    pass


class RedisCache(object):
    def __init__(self, host='localhost', port=6379, db=0, decode_responses=False):
        self.host = host
        self.port = port
        self.db = db
        self._cache = redis.StrictRedis(host=self.host, port=self.port, db=self.db, decode_responses=decode_responses)
        self._key_sep = '\x01'
        self._expire = None

    def set_key_sep(self, sep):
        self._key_sep = sep

    def set_expire(self, time):
        self._expire = time

    def _wrap_key(
            self,
            k,
    ):
        if isinstance(k, (list, tuple)):
            return self._key_sep.join(k)
        else:
            return k

    def get(self, k):
        k = self._wrap_key(k)
        return self._cache.get(k)

    def set(self, k, v, ex=None):
        k = self._wrap_key(k)
        if ex is None:
            ex = self._expire
        return self._cache.set(k, v, ex=ex)

    def hset(self, k, n, v, ex=None):
        """hset操作
        因为redis过期时间只支持顶层key,且hset没有过期时间设置原子化操作，所以自己加入expire操作
        """
        k = self._wrap_key(k)
        set_result = self._cache.hset(k, n, v)
        if ex:
            ex_result = self._cache.expire(k, ex)
        else:
            ex_result = None
        return set_result, ex_result

    def hget(self, k, n):
        k = self._wrap_key(k)
        return self._cache.hget(k, n)

    def hset_json(self, k, n, v, ex=None, encoder=None):
        k = self._wrap_key(k)
        if v is None:
            nv = None
        else:
            nv = json.dumps(v, ensure_ascii=False, cls=encoder)
        return self.hset(k, n, nv, ex=ex)

    def hget_json(self, k, n, decoder=None):
        jsn_str = self.hget(k, n)
        if jsn_str is None:
            return None
        else:
            return json.loads(jsn_str, cls=decoder)

    def get_list(self, k, sep='\x01'):
        k = self._wrap_key(k)
        v = self._cache.get(k)
        if v is None:
            return None
        return v.split(sep)

    def set_list(self, k, v, sep='\x01', ex=None):
        k = self._wrap_key(k)
        if v is None:
            nv = None
        else:
            nv = sep.join(v)
        if ex is None:
            ex = self._expire
        return self._cache.set(k, nv, ex=ex)

    def get_json(self, k, decoder=None):
        k = self._wrap_key(k)
        jsn_str = self._cache.get(k)
        if jsn_str is None:
            return None
        else:
            return json.loads(jsn_str, cls=decoder)

    def set_json(self, k, v, ex=None, encoder=None):
        k = self._wrap_key(k)
        if v is None:
            nv = None
        else:
            nv = json.dumps(v, ensure_ascii=False, cls=encoder)
        if ex is None:
            ex = self._expire
        return self._cache.set(k, nv, ex=ex)

    def get_obj(self, k):
        k = self._wrap_key(k)
        s = self._cache.get(k)
        if s is None:
            return None
        else:
            return pickle.loads(s)

    def set_obj(self, k, v, ex=None):
        k = self._wrap_key(k)
        if v is None:
            nv = None
        else:
            nv = pickle.dumps(v, protocol=2)
        if ex is None:
            ex = self._expire
        return self._cache.set(k, nv, ex=ex)

    def delete(self, *ks):
        """
        ks: one or list of keys
        """
        return self._cache.delete(*ks)
