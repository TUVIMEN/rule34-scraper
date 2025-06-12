#!/usr/bin/env python
# by Dominik Stanisław Suchora <hexderm@gmail.com>
# License: GNU GPLv3

import time
import random
import os
import sys
import re
import json
from typing import Optional, Tuple, Generator, Callable
from datetime import datetime
from pathlib import Path

from reliq import RQ

# from curl_cffi import requests
import requests

reliq = RQ(cached=True)


class RequestLError(Exception):
    pass


class RequestCError(Exception):
    pass


class RequestBadError(Exception):
    pass


class RequestError(Exception):
    pass


def bool_get(obj: dict, name: str, otherwise: bool = False) -> bool:
    x = obj.get(name)
    if x is None:
        return otherwise
    return bool(x)


def int_get(obj: dict, name: str, otherwise: int = 0) -> int:
    x = obj.get(name)
    if x is None:
        return otherwise
    return int(x)


def float_get(obj: dict, name: str, otherwise: float = 0) -> float:
    x = obj.get(name)
    if x is None:
        return otherwise
    return float(x)


def dict_get(obj: dict, name: str) -> dict:
    x = obj.get(name)
    if not isinstance(x, dict):
        return {}
    return x


class Session:
    def __init__(self, **kwargs):
        super().__init__()

        self.proxies = {}
        self.headers = {}
        self.cookies = {}

        self.proxies.update(dict_get(kwargs, "proxies"))
        self.headers.update(dict_get(kwargs, "headers"))
        self.cookies.update(dict_get(kwargs, "cookies"))

        self.timeout = int_get(kwargs, "timeout", 30)
        self.verify = bool_get(kwargs, "verify", True)
        self.allow_redirects = bool_get(kwargs, "allow_redirects", False)

        t = kwargs.get("user_agent")
        self.user_agent = (
            t
            if t is not None
            else "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
        )

        self.headers.update({"User-Agent": self.user_agent})

        self.retries = int_get(kwargs, "retries", 3)
        self.retry_wait = float_get(kwargs, "retry_wait", 60)
        self.wait = float_get(kwargs, "wait")
        self.wait_random = int_get(kwargs, "wait_random")

        self.logger = kwargs.get("logger")

        self.ses = self.session()

    def session(self):
        ret = requests.Session()

        ret.proxies.update(self.proxies)
        ret.headers.update(self.headers)
        ret.cookies.update(self.cookies)

        ret.verify = self.verify
        ret.user_agent = self.user_agent

        return ret

    def r_req_try(self, url: str, method: str, retry: bool = False, **kwargs):
        if not retry:
            if self.wait != 0:
                time.sleep(self.wait)
            if self.wait_random != 0:
                time.sleep(random.randint(0, self.wait_random + 1) / 1000)

        if self.logger is not None:
            print(url, file=self.logger)

        nargs = {"allow_redirects": self.allow_redirects, "timeout": self.timeout}
        nargs.update(kwargs)

        if method == "get":
            return self.ses.get(url, **nargs)
        elif method == "post":
            return self.ses.post(url, **nargs)
        elif method == "delete":
            return self.ses.delete(url, **nargs)
        elif method == "put":
            return self.ses.put(url, **nargs)

    def r_req(self, url: str, method: str = "get", **kwargs):
        tries = self.retries
        retry_wait = self.retry_wait

        instant_end_code = [404]

        i = 0
        while True:
            try:
                resp = self.r_req_try(url, method, retry=(i != 0), **kwargs)
                self.ses = self.session()
            except (
                requests.ConnectTimeout,
                requests.ConnectionError,
                requests.ReadTimeout,
                requests.exceptions.ChunkedEncodingError,
                RequestError,
            ):
                resp = None

            if resp is None or not (
                resp.status_code >= 200 and resp.status_code <= 299
            ):
                if resp is not None and resp.status_code in instant_end_code:
                    raise RequestCError(
                        "failed completely {} {}".format(resp.status_code, url)
                    )
                if resp is not None and resp.status_code == 302:
                    raise RequestLError
                if i >= tries:
                    if resp is None:
                        raise RequestError
                    else:
                        raise RequestBadError(
                            "failed {} {}".format(
                                "connection" if resp is None else resp.status_code, url
                            )
                        )
                i += 1
                if retry_wait != 0:
                    time.sleep(retry_wait)
            else:
                return resp

    def get_html(
        self, url: str, return_cookies: bool = False, **kwargs
    ) -> Tuple[reliq, str] | Tuple[reliq, str, dict]:
        resp = self.r_req(url, **kwargs)

        rq = reliq(resp.text, ref=url)
        ref = rq.ref

        if return_cookies:
            return (rq, ref, resp.cookies.get_dict())
        return (rq, ref)

    def get_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, **kwargs)
        return resp.json()

    def post_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, method="post", **kwargs)
        return resp.json()

    def delete_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, method="delete", **kwargs)
        return resp.json()

    def put_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, method="put", **kwargs)
        return resp.json()


class rule34xxx:
    def __init__(self, **kwargs):
        self.ses = Session(
            **kwargs,
        )

    def go_through_pages(self, url: str, func: Callable) -> Generator:
        nexturl = url
        page = 1
        while True:
            paged = func(nexturl, page)
            nexturl = paged["nexturl"]

            yield paged

            if nexturl is None or len(nexturl) == 0:
                break
            page += 1

    @staticmethod
    def conv_date(date):
        if len(date) == 0:
            return date

        return datetime.strptime(date, "%Y-%m-%d %H:%M:%S").isoformat()

    def get_comments(self, rq, ref):
        ret = []
        while True:
            r = json.loads(
                rq.search(
                    r"""
                    .comments div #comment-list; div #b>c child@; {
                        div .col1; {
                            [0] a child@; {
                                .user_link.U * self@ | "%(href)Dv" trim,
                                .user * self@ | "%Di" trim
                            },
                            .id.u span child@ | "%i",
                            b child@; {
                                .date * self@ | "%Dt" tr "\n\t\r" sed "s/.*Posted on //; s/Score:.*//" trim,
                                .score.u a id=b>s | "%i",
                            }
                        },
                        .text div .col2 | "%i" tr "\n\t\r" sed "s/<br *\/?>/\n/g" "E" decode trim
                    } |
            """
                )
            )
            ret += r["comments"]

            nexturl = rq.search(
                r""" div #paginator; a alt=next | "%(onclick)v" sed "s/.*location='//; s/'.*//" decode trim """
            )
            if len(nexturl) == 0:
                break
            nexturl = rq.ujoin(nexturl)
            rq, ref = self.ses.get_html(nexturl)

        for i in ret:
            i["date"] = self.conv_date(i["date"])

        return ret

    def get_post(self, url, p_id=0):
        if p_id != 0:
            url = "https://rule34.xxx/index.php?page=post&s=view&id={}".format(p_id)

        rq, ref = self.ses.get_html(url)

        r = json.loads(
            rq.search(
                r"""
                .image.U img #image src | "%(src)Dv" trim,
                .original.U div .link-list; a i@"Original image" | "%(href)Dv" trim,
                div #stats; {
                    .id.u li i@b>"Id: " | "%i" sed "s/^.*: //",
                    li i@"Posted: "; {
                        .date * self@  | "%i" sed "s/^[A-Za-z0-9]*: //; s/<.*//;q" trim,
                        * self@; [0] a; {
                            .uploader_link.U * self@ | "%(href)Dv" trim,
                            .uploader * self@  | "%Di" sed "/ /!p" "n" trim
                        }
                    },
                    .rating li i@"Rating: " | "%Di" / sed 's/.*: //' trim,
                    .sources.a.U li i@"Source:"; a | "%(href)v\n",
                   .sizex.u li i@b>"Size: " | "%i" sed "s/^.*: //; s/x.*//",
                   .sizey.u li i@b>"Size: " | "%i" sed "s/^.*: //; s/.*x//",
                   .score.u span #B>"psc[0-9]*" | "%i"
                },
                ul #tag-sidebar; {
                    .copyright.a li .tag-type-copyright .tag; a [-] | "%Di\n" / trim "\n",
                    .character.a li .tag-type-character .tag; a [-] | "%Di\n" / trim "\n",
                    .artist.a li .tag-type-artist .tag; a [-] | "%Di\n" / trim "\n",
                    .general.a li .tag-type-general .tag; a [-] | "%Di\n" / trim "\n",
                    .metadata.a li .tag-type-metadata .tag; a [-] | "%Di\n" / trim "\n",
                },
                .comments_count.u div #comment-list | "%t",
                """
            )
        )
        r["url"] = url
        r["comments"] = self.get_comments(rq, ref)

        r["date"] = self.conv_date(r["date"])

        return r

    def get_lastpost_id(self):
        rq, ref = self.ses.get_html(
            "https://rule34.xxx/index.php?page=post&s=list&tags=all"
        )

        return int(rq.search(r'span .thumb; [0] a href | "%(href)v\n" sed "s/.*=//"'))

    def get_page_posts(self, rq, ref):
        return json.loads(rq.search(r'.urls.a.U div .image-list; a id | "%(href)v\n"'))[
            "urls"
        ]

    @staticmethod
    def post_url_to_id(url):
        r = re.search(r"[?&]id=(\d+)", url)
        if r is None:
            return 0
        return int(r[1])

    def get_page(self, url: str, page: int = 1) -> dict:
        rq, ref = self.ses.get_html(url)

        nexturl = rq.search(r'div #paginator; [0] a alt=next | "%(href)Dv" trim')
        if len(nexturl) != 0:
            nexturl = rq.ujoin(nexturl)

        lastpage = rq.json(
            r'.u.u div #paginator; [0] a alt="last page" | "%(href)v" / sed "s/.*(\?|&|&amp;)pid=//;s/( |\?|&|&amp;).*//" "E"'
        )["u"]

        return {
            "url": url,
            "nexturl": nexturl,
            "page": page,
            "lastpage": lastpage,
            "posts": self.get_page_posts(rq, ref),
        }

    def get_pages(self):
        return self.go_through_pages(
            "https://rule34.xxx/index.php?page=post&s=list&tags=all", self.get_page
        )


if len(sys.argv) < 2:
    print("{} <DIR>".format(sys.argv[0]), file=sys.stderr)
    exit(1)

work_path = Path(sys.argv[1])
if not work_path.exists():
    os.mkdir(work_path)
elif not work_path.is_dir():
    print('{}: "{}" is not a directory'.format(sys.argv[0], work_path))


rl34 = rule34xxx(wait=2, wait_random=0, retries=0, retry_wait=0, logger=sys.stdout)


def _nans():
    def links_read():
        links = set()
        try:
            with open(work_path / "links", "r") as f:
                for i in f:
                    links.add(int(i.strip()))
        except FileNotFoundError:
            pass
        return links

    links = links_read()

    def links_save(links):
        with open(work_path / "links", "w") as f:
            for i in links:
                f.write(str(i).strip())
                f.write("\n")

    def links_update(links, maxrepeated=0):
        for i in rl34.get_pages():
            repeated = 0
            for j in i["posts"]:
                p_id = rl34.post_url_to_id(j)
                if p_id in links:
                    repeated += 1
                else:
                    links.add(p_id)

            if maxrepeated != 0 and repeated >= maxrepeated:
                break
            time.sleep(0.3)

    try:
        links_update(links, 0)
    except Exception as e:
        links_save(links)
        raise e

    links_save(links)

    for i in links:
        post_get(i)


def post_get(p_id):
    fname = work_path / str(p_id)

    nonexisiting_path = str(fname) + "_e"

    if os.path.exists(nonexisiting_path):
        return
    if fname.exists() and os.path.getsize(fname) > 10:
        return

    try:
        r = rl34.get_post(url="", p_id=p_id)
    except RequestLError:
        with open(nonexisiting_path, "w") as f:
            f.write("\n")
        return
    except (RequestError, RequestCError, RequestBadError):
        print("{} failed".format(p_id))
        return

    with open(fname, "w") as f:
        json.dump(r, f, separators=(",", ":"))
        f.write("\n")


lastpost = rl34.get_lastpost_id()

# post_get(717)

for i in range(1, lastpost + 1):
    post_get(i)
