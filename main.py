#! ./bin/python
# -*- coding: utf-8 -*-
"""
Generate content

Usage:
  main.py generate <structure>
  main.py -h | --help
  main.py --version

Options:
  -h --help     Show this screen.
  --version     Show version.
  -v --verbose  Print more informations
"""

from datetime import datetime
from docopt import docopt
from progress.bar import FillingSquaresBar
from timeit import default_timer

import asyncio
import chardet
import concurrent.futures
import os
import pprint
import random
import requests
import simplejson as json

START_TIME = default_timer()


class ContentGenerator(object):
    def __init__(self, **kwargs):
        self._parameters = {}
        self._cached_values = {}
        self.set_parameters(kwargs)

    def set_parameters(self, kwargs):
        for key, value in list(kwargs.items()):
            if key.startswith("--"):
                key = key[2:]
                self._parameters[key] = value
            else:
                if key.startswith("<") and key.endswith(">"):
                    key = key[1:-1]
                setattr(self, key, value)

    def execute(self):
        for k, v in self.__dict__.items():
            attr = getattr(self, "_{0}".format(k), None)
            if v is True and callable(attr):
                return attr()
        raise ValueError("Missing method")

    def _print(self, value):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(value)

    def _parse_structure(self):
        with open(self.structure, "r") as f:
            self._structure = json.loads(f.read())

    def _initialize_content(self):
        self._content = {"files": []}
        directory = "./data"
        for f in os.listdir(directory):
            with open(os.path.join(directory, f), "rb") as f:
                content = f.read()
                encoding = chardet.detect(content)
                content = content.decode(encoding["encoding"])
                self._content["files"].append(
                    {"length": len(content), "content": content}
                )

    @staticmethod
    def _random_element(elements):
        return elements[random.randint(0, len(elements) - 1)]

    def _generate_content(self, length):
        file_info = self._random_element(self._content["files"])
        start = random.randint(0, file_info["length"] - length)
        return file_info["content"][start : start + length].replace("\n", "")

    def _generate_text(self):
        return self._generate_content(500)

    def _generate_sentence(self):
        return self._generate_content(100)

    @property
    def random_data(self):
        return {
            k: v[random.randint(0, len(v) - 1)]
            for k, v in self._structure["data"].items()
        }

    def _get_vocabulary(self, url):
        if url not in self._cached_values:
            r = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                auth=("admin", "admin"),
            )
            self._cached_values[url] = r.json()
        return self._cached_values[url]

    @property
    def random_body(self):
        # XXX Should be improved
        body = {}
        for k, v in self._structure["template"].items():
            if isinstance(v, list):
                body[k] = v[random.randint(0, len(v) - 1)]
            elif isinstance(v, dict):
                if v["type"] == "vocabulary":
                    voc = self._get_vocabulary(v["url"])
                    terms = voc["terms"]
                    body[k] = terms[random.randint(0, len(terms) - 1)]["token"]
            elif v == "paragraph":
                body[k] = self._generate_text()
            elif v == "richtext":
                body[k] = {
                    "data": "<p>{0}</p>".format(self._generate_text()),
                    "content-type": "text/html",
                }
            elif v == "line":
                body[k] = self._generate_sentence()
            elif v == "today":
                body[k] = datetime.now().strftime("%Y-%m-%dT%H:%M")
            elif v == "empty_list":
                body[k] = []
            else:
                body[k] = v
        return body

    def _generate_request(self, progress_bar):
        url = self._structure["url"].format(**self.random_data)
        body = {"data": [self.random_body for i in range(0, 10)]}
        requests.post(
            url,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            auth=("admin", "admin"),
            data=json.dumps(body),
        )
        progress_bar.next()

    async def _generate_async(self, progress_bar):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(executor, self._generate_request, progress_bar)
                for i in range(0, self._structure["number"])
            ]
            for response in await asyncio.gather(*futures):
                pass

    def _generate(self):
        self._initialize_content()
        self._parse_structure()
        start_time = default_timer()
        progress_bar = FillingSquaresBar(
            "Generate content", max=self._structure["number"]
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._generate_async(progress_bar))
        progress_bar.finish()
        elapsed = default_timer() - start_time
        print("{:5.2f}s elapsed".format(elapsed))


if __name__ == "__main__":
    arguments = docopt(__doc__, version="Generate content")
    ContentGenerator(**arguments).execute()
