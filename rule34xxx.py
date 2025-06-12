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

# from curl_cffi import requests
import requests
from reliq import RQ
import treerequests

reliq = RQ(cached=True)


class rule34xxx:
    def __init__(self, **kwargs):
        self.ses = treerequests.Session(
            requests,
            requests.Session,
            lambda x, y: treerequests.reliq(x, y, obj=reliq),
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

    def get_comments(self, rq):
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
            rq = self.ses.get_html(nexturl)

        for i in ret:
            i["date"] = self.conv_date(i["date"])

        return ret

    def get_post(self, url, p_id=0):
        if p_id != 0:
            url = "https://rule34.xxx/index.php?page=post&s=view&id={}".format(p_id)

        rq = self.ses.get_html(url)

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
        r["comments"] = self.get_comments(rq)

        r["date"] = self.conv_date(r["date"])

        return r

    def get_lastpost_id(self):
        rq = self.ses.get_html("https://rule34.xxx/index.php?page=post&s=list&tags=all")

        return int(rq.search(r'span .thumb; [0] a href | "%(href)v\n" sed "s/.*=//"'))

    def get_page_posts(self, rq):
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
        rq = self.ses.get_html(url)

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
            "posts": self.get_page_posts(rq),
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


rl34 = rule34xxx(
    wait=2,
    wait_random=0,
    retries=0,
    retry_wait=0,
    logger=treerequests.simple_logger(sys.stdout),
)


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
    except treerequests.RedirectionError:
        with open(nonexisiting_path, "w") as f:
            f.write("\n")
        return
    except requests.RequestsException:
        print("{} failed".format(p_id))
        return

    with open(fname, "w") as f:
        json.dump(r, f, separators=(",", ":"))
        f.write("\n")


lastpost = rl34.get_lastpost_id()

# post_get(717)

for i in range(1, lastpost + 1):
    post_get(i)
