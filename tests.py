#!/usr/bin/env python

import os
import sys
import tempfile
import json
from pathlib import Path

from biggusdictus import isdict, uint, Or, Isodate, Https, Uri, Url

import rule34xxx


def intemp(func):
    prev = os.getcwd()

    with tempfile.TemporaryDirectory() as dir:
        os.chdir(dir)

        func()

    os.chdir(prev)


def post_verify(data):
    isdict(
        data,
        ("image", Or, Https, (str, 0, 0)),
        ("original", Https),
        ("id", uint, 1, 10700013),
        ("date", Isodate),
        ("uploader_link", Https),
        ("uploader", str, 3, 11),
        ("rating", str, 8, 8),
        ("sources", list, Https, 0, 1),
        ("sizex", uint, 640, 3275),
        ("sizey", uint, 480, 4096),
        ("score", uint, 15, 8029),
        ("copyright", list, (str, 6, 22), 0, 4),
        ("character", list, (str, 6, 19), 1, 4),
        ("artist", list, (str, 7, 12), 0, 1),
        ("general", list, (str, 2, 29), 25, 320),
        ("metadata", list, (str, 2, 22), 0, 30),
        ("comments_count", uint, 0, 3000),
        ("url", Https),
        (
            "comments",
            list,
            (
                dict,
                ("user_link", Https),
                ("user", str, 4, 56),
                ("id", uint),
                ("date", Isodate),
                ("score", uint, 0, 2009),
                ("text", str, 0, 189858),
            ),
            0,
            2015,
        ),
    )


def item_test(p_id):
    def t():
        rl34 = rule34xxx.rule34xxx(wait=1.2, wait_random=0.4)

        rl34.save_post(".", "", p_id=p_id)

        path = Path(str(p_id))
        data = path.read_text()

        js = json.loads(data)
        post_verify(js)

    intemp(t)


def test_posts_1():
    item_test(949847)


def test_posts_deleted():
    def t():
        rl34 = rule34xxx.rule34xxx()
        rl34.save_post(".", "", p_id=2)
        assert Path("2_e").read_text() == "\n"

    intemp(t)


def test_posts_2():
    item_test(7131283)


def test_posts_3():
    item_test(8008010)


def test_posts_4():
    item_test(8509057)


def test_posts_5():
    item_test(10700013)


def test_posts_6():
    item_test(9380191)


def test_posts_7():
    item_test(1)
