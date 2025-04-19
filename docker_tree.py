#!/usr/bin/env python3

import sys
import re
import json
from subprocess import check_output, CalledProcessError, PIPE
from functools import reduce
from collections.abc import Iterator
from argparse import ArgumentParser, ArgumentError
from itertools import chain
import datetime as dt

class AppError(Exception):
    pass

class LookAheadIterator(Iterator):
    """
    >>> from util import LookAheadIterator
    >>> for s, is_first, is_last in LookAheadIterator(['first', 'middle', 'last']):
    ...     print(f'{is_first}\t{is_last}\t{s}')
    True    False   first
    False   False   middle
    False   True    last
    """
    def __init__(self, a_iterable):
        cargo_iterator = iter(a_iterable)
        try:
            self._cargo_next = next(cargo_iterator)
            self._cargo_iterator = cargo_iterator
            self._exhausted = False
            self._virgin = True
        except StopIteration:
            self._exhausted = True

    def __iter__(self):
        return self

    def __next__(self):
        if self._exhausted:
            raise StopIteration
        cargo = self._cargo_next
        try:
            self._cargo_next = next(self._cargo_iterator)
        except StopIteration:
            self._cargo_next = None
            self._exhausted = True
            self._cargo_iterator = None
        if self._virgin:
            self._virgin = False
            return (
                    cargo,
                    True,
                    self._exhausted,
                    )
        else:
            return (
                    cargo,
                    False,
                    self._exhausted,
                    )

class ThrowingArgumentParser(ArgumentParser):
    def error(self, message):
        raise ArgumentError(None, message)

def singleton(a_class):
    setattr(a_class, 'instance', a_class())
    return a_class

def adapt_subprocess_error(with_message='Subprocess ended with non-zero exit code'):
    def adaptor(err):
        msg = '\n  '.join(err.stderr.rstrip().splitlines())
        raise AppError(f'{with_message}:\n  {msg}')
    def decorator(*dargs):
        if len(dargs) == 1:
            def function_wrapper(*args, **kwargs):
                try:
                    return dargs[0](*args, **kwargs)
                except CalledProcessError as err:
                    adaptor(err)
            return function_wrapper
        else:
            def method_wrapper(*args, **kwargs):
                try:
                    return dargs[1](dargs[0], *args, **kwargs)
                except CalledProcessError as err:
                    adaptor(err)
            return method_wrapper
    return decorator

@singleton
class Docker:
    _LIST_IDS = ('docker', 'image', 'ls', '-a', '--no-trunc', '--format', '{{.ID}}',)
    _INSPECT = ('docker', 'inspect',)
    _GET_IDS = ('docker', 'inspect', '-f', '{{.Id}}',)

    @adapt_subprocess_error('Problem getting the list of images')
    def id_list(self):
        """
        List of all local images' id's as iterable of str's.
        """
        return set(Image.remove_sha256(s) for s in check_output(
                Docker._LIST_IDS,
                universal_newlines=True,
                stderr=PIPE,
                ).splitlines()
                )

    @adapt_subprocess_error('Problem inspecting id(s) / tag(s)')
    def inspect(self, a_image_tags_or_ids):
        """
        Calls 'docker inspect' on given image(s).

        Args:
            a_image_tags_or_ids:
                Single str or iterable of str's with image id's or tags.

        Returns:
            List of dict's.
        """
        return json.loads(
                check_output(
                        (*self._INSPECT, a_image_tags_or_ids) if type(a_image_tags_or_ids) == str \
                            else (*self._INSPECT, *a_image_tags_or_ids),
                        universal_newlines=True,
                        stderr=PIPE,
                        ))

    @adapt_subprocess_error('Problem getting id(s) / tag(s)')
    def ids(self, a_image_tags_or_ids):
        """
        Verifies image id's / tags.

        Args:
            a_image_tags_or_ids:
                Single str or iterable of str's with image id's or tags.

        Returns:
            List of id's as str's.
        """
        return (id.rstrip() for id in map(
                Image.remove_sha256,
                check_output(
                        (*self._GET_IDS, a_image_tags_or_ids) if type(a_image_tags_or_ids) == str \
                            else (*self._GET_IDS, *a_image_tags_or_ids) ,
                        universal_newlines=True,
                        stderr=PIPE,
                        ).splitlines(),
                        ))

    def get_images(self):
        return ImagesFactory.instance.build_from_metadata(self.inspect(self.id_list()))

def _to_k(i, exp, letter):
    v = i / exp
    if v < 10:
        return f'{round(i / (exp / 10)) / 10}{letter}'
    if v < 20:
        return f'{round(i / (exp / 5)) / 5}{letter}'
    if v < 1024:
        return f'{round(v)}{letter}'
    return None

def pretty_size(i):
    if i < 100:
        return f'{i}B'
    e = 1
    for l in ('K', 'M', 'G', 'T', 'P',):
        e *= 1024
        r = _to_k(i, e, l)
        if r is not None:
            return r
    return f'{round(i / e)}P'

class Image(object):
    @staticmethod
    def _sort_tags(a_tags):
        return sorted(
                a_tags,
                key=lambda t: f'{"A" if t[-7:] == ":latest" else "B"}{t}'
                )

    @staticmethod
    def sorted(a_imgs):
        return sorted(
                a_imgs,
                key=lambda i: i._sorting_str
                )

    @staticmethod
    def remove_sha256(s):
        return s[7:]

    def _has_key(self, a_key):
        return a_key in self.metadata and self.metadata[a_key]

    @staticmethod
    def _parse_dt(a_str):
        for fmt,pre_pr in (
                (
                    '%Y-%m-%dT%H:%M:%S.%f',
                    lambda s: \
                        s[:-4],
                ),
                (
                    '%Y-%m-%dT%H:%M:%S',
                    lambda s: \
                        s[:-1],
                ),
                (
                    '%Y-%m-%dT%H:%M:%S.%f%z',
                    lambda s: \
                        re.sub(
                            r'(\.\d{6})\d*([+\-]\d{2}):(\d{2})$',
                            r'\1\2\3',
                            s,
                            ),
                ),):
            try:
                return dt.datetime.strptime(
                    a_str if pre_pr is None \
                        else pre_pr(a_str),
                    fmt,
                    )
            except ValueError:
                continue
        raise Exception

    def __init__(self, *, id=None, metadata=None):
        if (not id and not metadata) or (id and metadata):
            raise AppError('Image constructor requires either id or metadata')
        self.metadata = metadata if metadata \
            else Docker.instance.inspect(id)[0]
        self.id = Image.remove_sha256(self.metadata['Id'])
        self.has_tags = self._has_key('RepoTags')
        self.has_parent = self._has_key('Parent')
        self.parent_id = self.remove_sha256(self.metadata['Parent']) if self.has_parent \
            else None
        self._hash = int(self.id, base=16)
        self.size = int(self.metadata["Size"])
        self.ctime = self._parse_dt(self.metadata['Created'])
        self._sorting_str = f'A{",".join(self._sort_tags(self.metadata["RepoTags"]))}' if self.has_tags \
            else f'B{self.ctime.strftime("%Y%m%d%H%M%S%f")}'

    def is_child_of(self, a_image):
        return self.parent_id == a_image.id

    def find_immediate_family(self, a_images):
        self.children = Image.sorted(filter(
                lambda i: i.is_child_of(self),
                a_images,
                ))
        self.has_children = bool(self.children)
        self.parent = a_images[self.parent_id] if self.has_parent \
            else None
        self.size_delta = (self.size - self.parent.size) if self.has_parent \
            else None
        self.time_delta = (self.ctime - self.parent.ctime) if self.has_parent \
            else None

    @property
    def clone(self):
        return Image(metadata=self.metadata)

    @property
    def ancestors(self):
        if self.has_parent:
            store = (self.parent, None,)
            while store[0].has_parent:
                store = (store[0].parent, store,)
            while store:
                yield store[0]
                store = store[1]

    @property
    def descendants(self):
        if self.has_children:
            for child in self.children:
                yield child
                for descendant in child.descendants:
                    yield descendant

    def sprint_children(self, a_prefix='', a_branch='', a_dotted=()):
        middle_sub_prefix = f'{a_prefix}│   '
        last_sub_prefix = f'{a_prefix}    '
        buffer = f'{a_branch}{self}'
        for child, _, is_last in LookAheadIterator(self.children):
            if child.id in a_dotted:
                middle_sub_branch = '├─• '
                last_sub_branch = '└─• '
            else:
                middle_sub_branch = '├───'
                last_sub_branch = '└───'
            s = child.sprint_children(
                    last_sub_prefix, 
                    last_sub_branch, 
                    a_dotted,
                    ) if is_last \
                else child.sprint_children(
                        middle_sub_prefix, 
                        middle_sub_branch, 
                        a_dotted,
                        )
            buffer += f'\n{a_prefix}{s}'
        return buffer

    def sprint_tree(self):
        if self.has_parent:
            ai = iter(self.ancestors)
            buffer = f'┌─{next(ai)}'
            while p := next(ai, None):
                buffer += f'\n├─{p}'
            return f'{buffer}\n└─• {self.sprint_children(a_prefix="    ")}'
        else:
            return f'• {self.sprint_children(a_prefix="  ")}'

    @property
    def _formatted_ctime(self):
        return self.ctime.strftime("%Y.%m.%d %H:%M:%S")

    _time_show_delta_threshold = dt.timedelta(hours=1, seconds=0.499999)
    _time_dont_show_threshold = dt.timedelta(seconds=0.999999)
    _time_1_min = dt.timedelta(seconds=60.499999)
    _time_1_hour = dt.timedelta(minutes=60, seconds=0.499999)

    @property
    def pretty_time(self):
        if not self.has_parent \
                or CLArgs.instance.no_tree:
            return self._formatted_ctime
        if self.time_delta < self._time_show_delta_threshold:
            if self.time_delta < self._time_1_min:
                return f'+{round(self.time_delta.total_seconds())}s'
            elif self.time_delta < self._time_1_hour:
                m,s = divmod(round(self.time_delta.total_seconds()), 60)
                return f'+{m}:{s:02d}'
            else:
                return f'+{dt.timedelta(seconds=round(self.time_delta.total_seconds()))}'
        else:
            return self._formatted_ctime

    def __repr__(self):
        id_str = ','.join(self._sort_tags(self.metadata['RepoTags'])) if self.has_tags \
            else self.id if CLArgs.instance.no_trunc \
            else self.id[:12]
        acc = []
        if not self.has_parent \
                or self.time_delta > self._time_dont_show_threshold \
                or CLArgs.instance.no_tree:
            acc.append(self.pretty_time)
        if not self.has_parent \
                or CLArgs.instance.no_tree:
            acc.append(pretty_size(self.size))
        elif self.size_delta:
            acc.append(f'+{pretty_size(self.size_delta)}')
        if acc:
            return f'{id_str}: {", ".join(acc)}'
        else:
            return id_str

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return self._hash

@singleton
class ImagesFactory:
    def build_from_metadata(self, a_metadata_iter):
        return Images(Image(metadata=m) for m in a_metadata_iter)

class Images:
    def __init__(self, a_image_iterable):
        self._id2img = {i.id: i for i in a_image_iterable}
        for img in self:
            img.find_immediate_family(self)

    def __iter__(self):
        return iter(self._id2img.values())

    @property
    def orphans(self):
        return Image.sorted(filter(
                lambda i: not i.has_parent,
                self,
                ))

    @property
    def spinsters(self):
        return Image.sorted(filter(
                lambda i: not i.has_children,
                self,
                ))

    def __getitem__(self, a_id):
        return self._id2img[a_id]

    def sprint_tree(self, a_dotted=()):
        return '\n'.join((
                i.sprint_children('  ', '• ', a_dotted) if i.id in a_dotted \
                    else i.sprint_children('', '', a_dotted)
                ) for i in self.orphans)

    def cook_subimages(self, a_id_iterable):
        return Images(i.clone for i in set(
                chain.from_iterable(
                    chain((i,), i.ancestors, i.descendants) for i in (
                            self[id] for id in a_id_iterable
                    ))))
@singleton
class CLArgs:
    def __init__(self):
        p = ThrowingArgumentParser(
                description='Shows docker image family tree.',
                )
        g = p.add_mutually_exclusive_group()
        g.add_argument(
                '-r',
                '--roots',
                dest='show_orphans',
                action='store_true',
                default=False,
                help='Show only "root" images',
                )
        g.add_argument(
                '-l',
                '--leafs',
                dest='show_spinsters',
                action='store_true',
                default=False,
                help='Show only "leaf" images',
                )
        g.add_argument(
                '-I',
                '--always-indent',
                dest='always_indent',
                action='store_true',
                default=False,
                help='Always show indented tree',
                )
        p.add_argument(
                '-N',
                '--no-trunc',
                dest='no_trunc',
                action='store_true',
                default=False,
                help="Do NOT truncate image id's to 12 chars",
                )
        p.add_argument(
                'target_images',
                nargs='*',
                metavar='<image id or tag>',
                action='store',
                help='Show the family tree of a particular image',
                )
        try:
            p.parse_args(namespace=self)
            self.no_tree = self.show_orphans or self.show_spinsters
        except ArgumentError as err:
            raise AppError(str(err))

def print_results(a_images, a_target_ids=()):
    if (CLArgs.instance.show_orphans):
        print('\n'.join(str(i) for i in a_images.orphans))
    elif (CLArgs.instance.show_spinsters):
        print('\n'.join(str(i) for i in a_images.spinsters))
    else:
        if (not CLArgs.instance.always_indent and len(a_target_ids) == 1):
            print(a_images[a_target_ids[0]].sprint_tree())
        else:
            print(a_images.sprint_tree(a_target_ids))

def main():
    images = Docker.instance.get_images()
    if CLArgs.instance.target_images:
        target_ids = tuple(Docker.instance.ids(CLArgs.instance.target_images))
        print_results(
                images.cook_subimages(target_ids), 
                target_ids,
                )
    else:
        print_results(images)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except AppError as err:
        print(f'Error: {err}', file=sys.stderr)
        sys.exit(1)
