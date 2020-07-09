#!/usr/bin/env python
# coding=utf-8

import os
import sys

sys.path.insert(0, '.')
from huoutil.util import ConfigBase
from huoutil.util import file2dictlist, file2list, file2set, load_python_conf
from huoutil.uni import standard_string_format
import pytest
TESTDATA = './tests/testdata/'


class Config(ConfigBase):
    def __init__(self, path=None):
        super(Config, self).__init__()
        self.NAME = 'Tom'
        self.AGE = 12
        self.LOVE = ['apple', 'banana']
        if path:
            self.load_conf(path)


def test_config():
    conf_path = os.path.join(TESTDATA, 'test.conf')
    cfg = Config(conf_path)
    assert cfg.NAME == 'Tian'
    assert cfg.AGE == 32
    assert cfg.LOVE == ['apple', 'banana']


def test_file2dictlist():
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=1)
    assert data[u'胰岛素'] == [u'低血糖', u'呕吐']
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=None, dup=False)
    assert data[u'胰岛素'] == [u'低血糖', u'呕吐', u'子宫收缩']
    assert data[u'泻药'] == []
    assert data[u'催吐药'] == [u'呕吐 排尿困难']
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=None)
    assert data[u'胰岛素'] == [u'低血糖', u'呕吐', u'子宫收缩', u'子宫收缩', u'子宫收缩']
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=None, skip_line=1)
    assert data.get(u'利尿药', '') == ''
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=None)
    assert data.get(u'利尿药', '') == [u'脱水']
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=None, skip_line=7)
    assert data == {}
    data = file2dictlist('./tests/testdata/test_file2dictlist', kn=0, vn=None, skip_line=8)
    assert data == {}
    data = file2list('./tests/testdata/test_file2dictlist', n=0, skip_line=4)
    assert data == [u'子宫平滑肌抑制药', u'胰岛素', u'胰岛素']
    data = file2set('./tests/testdata/test_file2dictlist', n=0, skip_line=4)
    assert data == set(['子宫平滑肌抑制药', '胰岛素'])


def test_cleandata():
    s = '贫血，头晕？【】［伯格］eN^? Ⅵ腹痛Ⅹ'
    tmp = 'Ⅰ、Ⅱ、Ⅲ、Ⅳ、Ⅴ、Ⅵ、Ⅶ、Ⅷ、Ⅸ、Ⅹ、Ⅺ、Ⅻ'
    clean_s = standard_string_format(s, upper=1)
    assert clean_s == '贫血,头晕?[][伯格]ENVI腹痛X'
    s = 'Ⅰ、Ⅱ、Ⅲ、Ⅳ、Ⅴ、Ⅵ、Ⅶ、Ⅷ、Ⅸ、Ⅹ、Ⅺ、Ⅻ'
    clean_s = standard_string_format(s, lower=1)
    assert clean_s == 'i、ii、iii、iv、v、vi、vii、viii、ix、x、xi、xii'


def test_load_python_conf():
    conf_path = os.path.join(TESTDATA, 'test_python.conf')
    newconfig = load_python_conf(conf_path, default_property=True)
    assert newconfig.bf_fpmutual_manrule == True
    assert newconfig.askdjsldlk == None
    newconfig.bf_fpmutual_manrule = "OK平"
    assert newconfig.bf_fpmutual_manrule == "OK平"
    assert newconfig.askdjsldlk == None

    newconfig = load_python_conf(conf_path, default_property=False)
    with pytest.raises(AttributeError):
        assert newconfig.sd23sdfsd == None
