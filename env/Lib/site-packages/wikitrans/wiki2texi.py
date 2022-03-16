#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Sergey Poznyakoff
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Wiki markup to Texinfo translator.

Classes:

TexiWikiMarkup       -- Converts Wiki material to Texinfo.

"""

from wikitrans.wikimarkup import *
from wikitrans.wikitoken import *
from wikitrans.wikins import wiki_ns_re, wiki_ns
import re
import urllib


class Acc(list):
    def prepend(self, x):
        self.insert(0, x)

    def is_empty(self):
        return len(self) == 0

    def clear(self):
        self = []

    def tail(self, n = 1):
        s = Acc()
        i = len(self)
        while i > 0 and n > 0:
            elt = self[i-1]
            l = len(elt)
            if l == 0:
                continue
            elif l > n:
                l = n
            s.prepend(elt[-n:])
            n -= l
            i -= 1
        return str(s)

    def trim(self, n):
        while len(self) and n > 0:
            elt = self.pop()
            l = len(elt)
            if l == 0:
                continue
            elif l > n:
                self += elt[0:-n]
                break
            n -= l

    def trimnl(self):
        if self.endswith('\n'):
            self.trim(1)

    def trimpara(self):
        if self.endswith('\n\n'):
            self.trim(2)

    def endswith(self, x):
        return self.tail(len(x)) == x

    def in_new_para(self):
        return self.is_empty() or self.endswith('\n\n')

    def __str__(self):
        return ''.join(self)


class TexiTextNode(WikiTextNode):
    def format(self):
        parser = self.parser
        if isinstance(self.content, list):
            for s in self.content:
                parser._print(s)
        else:
            parser._print(self.content)


class TexiTagNode(WikiTagNode):
    def format(self):
        parser = self.parser
        if self.tag in ['code', 'tt']:
            save = parser._begin_print()
            parser.nested += 1
            self.content.format()
            parser.nested -= 1
            s = parser._end_print(save)
            if self.isblock:
                parser._print('@example', nl=True, escape=False)
                parser._print(s, escape=False)
                parser._print('@end example\n', nl=True, escape=False)
            else:
                parser._print('@code{%s}' % s, escape=False)
        elif self.tag == 'div':
            if self.args and 'id' in self.args:
                parser._print("@anchor{%s}\n" % self.args['id'],
                              nl=True, escape=False)
            self.content.format()
        elif self.tag == 'ref':
            parser._print('@footnote{', escape=False);
            self.content.format();
            parser._print('}', escape=False)
        elif self.tag == 'references':
            pass
        else:
            parser._print('<' + self.tag)
            if self.args:
                parser._print(' ' + self.args)
            parser._print('>');
            self.content.format()
            parser._print('</' + self.tag + '>')


class TexiParaNode(WikiSeqNode):
    def format(self):
        parser = self.parser
        if not parser.acc.in_new_para():
            parser._print('\n', nl=True)
        for x in self.content:
            x.format()
        if not parser.acc.in_new_para():
            parser._print('\n', nl=True)


class TexiPreNode(WikiSeqNode):
    def format(self):
        parser = self.parser
        if not parser.nested:
            parser._print('@example\n', nl=True, escape=False)
        for x in self.content:
            x.format()
        if not parser.nested:
            parser._print('@end example\n', nl=True, escape=False)


class TexiFontNode(WikiSeqNode):
    def format(self):
        parser = self.parser
        comm = { 'IT': 'i',
                 'BOLD': 'b' }
        parser._print('@%s{' % comm[self.type], escape=False)
        for x in self.content:
            x.format()
        parser._print('}', escape=False)


class TexiHdrNode(WikiHdrNode):
    def format(self):
        parser = self.parser
        level = self.level
        # FIXME
        if level > len(parser.sectcomm[parser.sectioning_model]) - 1 - parser.sectioning_start:
            parser._print("@* ", nl=True, escape=False)
            self.content.format()
        else:
            parser._print(parser.sectcomm[parser.sectioning_model][level - parser.sectioning_start] + " ", nl=True, escape=False)
            self.content.format()
            parser._print(None, nl=True)
            if parser.sectcomm[parser.sectioning_model][0] == '@top':
                parser._print('@node ', nl=True, escape=False)
                self.content.format()
                parser._print('\n')
        parser._print(None, nl=True)


class TexiBarNode(WikiNode):
    def format(self):
        self.parser._print("\n-----\n")


class TexiIndNode(WikiIndNode):
    def format(self):
        parser = self.parser
        parser._print("@w{ }" * self.level, nl=True, escape=False)
        self.content.format()
        parser._print(None, nl=True)


class TexiEnvNode(WikiEnvNode):
    def format(self):
        parser = self.parser
        if self.envtype == 'unnumbered':
            parser._print('@itemize @bullet\n', nl=True, escape=False)
            for s in self.content:
                parser._print('@item ', nl=True, escape=False)
                s.content.format()
                parser._print(None, nl=True)
                parser._print('\n')
            parser._print('@end itemize\n', nl=True, escape=False)
        elif self.envtype == 'numbered':
            parser._print('@enumerate\n', nl=True, escape=False)
            for s in self.content:
                parser._print('@item ', nl=True, escape=False)
                s.content.format()
                parser._print(None, nl=True)
                parser._print('\n')
            parser._print('@end enumerate\n', nl=True, escape=False)
        elif self.envtype == 'defn':
            parser._print('@table @asis\n', nl=True, escape=False)
            for s in self.content:
                if s.subtype == 0:
                    parser._print('@item ', nl=True, escape=False)
                    s.content.format()
                    parser._print(None, nl=True)
                else:
                    s.content.format()
                    parser._print(None, nl=True)
                    parser._print('\n')
            parser._print('@end table\n', nl=True, escape=False)


class TexiLinkNode(WikiSeqNode):
    def format(self):
        parser = self.parser
        save = parser._begin_print()
        self.content[0].format()
        arg = parser._end_print()
        if len(self.content) > 1:
            s = []
            for x in self.content[0:2]:
                parser._begin_print()
                x.format()
                s.append(parser._end_print())
            text = s[1]
        else:
            s = None
            text = None

        parser._end_print(save)

        if s:
            if s[0] == 'disambigR' or s[0] == 'wikiquote':
                return
            if len(s) > 1 and s[1] == 'thumb':
                return

        (qual, sep, tgt) = arg.partition(':')
        if text:
            parser._print("@ref{%s,%s}" % (qual, text), escape=False)
        else:
            parser._print("@ref{%s}" % qual, escape=False)


class TexiRefNode(WikiRefNode):
    def format(self):
        parser = self.parser
        target = self.ref
        save = parser._begin_print()
        self.content.format()
        text = parser._end_print(save)
        if text and text != '':
            parser._print("@uref{%s,%s}" % (target, text), escape=False)
        else:
            parser._print("@uref{%s}" % target, escape=False)


class TexiWikiMarkup(WikiMarkup):
    """Wiki markup to Texinfo translator class.

    Usage:

      x = TexiWikiMarkup(file="input.wiki")
      # Parse the input:
      x.parse()
      # Print it as Texi:
      print(str(x))

    """

    nested = 0
    sectcomm = {
        'numbered': [
            '@top',
            '@chapter',
            '@section',
            '@subsection',
            '@subsubsection'
        ],
        'unnumbered': [
            '@top',
            '@unnumbered',
            '@unnumberedsec',
            '@unnumberedsubsec',
            '@unnumberedsubsubsec'
        ],
        'appendix': [
            '@top',
            '@appendix',
            '@appendixsec',
            '@appendixsubsec',
            '@appendixsubsubsec'
        ],
        'heading': [
            '@majorheading'
            '@chapheading',
            '@heading',
            '@subheading',
            '@subsubheading'
        ]
    }

    sectioning_model = 'numbered'
    sectioning_start = 0

    def __init__(self, *args, **keywords):
        """Create a TexiWikiMarkup object.

        TexiWikiMarkup([filename=FILE],[file=FD],[text=STRING],[lang=CODE],
                       [html_base=URL],[image_base=URL],[media_base=URL],
                       [sectioning_model=MODEL],[sectioning_start=N])

        For a discussion of generic arguments, see the constructor of
        the WikiMarkup class.

        Additional arguments:

        sectioning_model=MODEL
          Select the Texinfo sectioning model for the output document. Possible
          values are:

          'numbered'
             Top of document is marked with "@top". Headings ("=", "==",
             "===", etc) produce "@chapter", "@section", "@subsection", etc.
          'unnumbered'
             Unnumbered sectioning: "@top", "@unnumbered", "@unnumberedsec",
             "@unnumberedsubsec".
          'appendix'
             Sectioning suitable for appendix entries: "@top", "@appendix",
             "@appendixsec", "@appendixsubsec", etc.
          'heading'
             Use heading directives to reflect sectioning: "@majorheading",
             "@chapheading", "@heading", "@subheading", etc.
        sectioning_start=N
          Shift resulting heading level by N positions. For example, supposing
          "sectioning_model='numbered'", "== A ==" normally produces
          "@section A" on output. Now, if given "sectioning_start=1", this
          directive will produce "@subsection A" instead.
        """

        super(TexiWikiMarkup, self).__init__(*args, **keywords)

        self.token_class['TEXT'] = TexiTextNode
        self.token_class['TAG']  = TexiTagNode
        self.token_class['PARA'] = TexiParaNode
        self.token_class['PRE']  = TexiPreNode
        self.token_class['IT']   = TexiFontNode
        self.token_class['BOLD'] = TexiFontNode
        self.token_class['HDR']  = TexiHdrNode
        self.token_class['BAR']  = TexiBarNode
        self.token_class['IND']  = TexiIndNode
        self.token_class['ENV']  = TexiEnvNode
        self.token_class['LINK'] = TexiLinkNode
        self.token_class['REF']  = TexiRefNode

        if "sectioning_model" in keywords:
            val = keywords["sectioning_model"]
            if val in self.sectcomm:
                self.sectioning_model = val
            else:
                raise ValueError("Invalid value for sectioning model: %s" % val)
        if "sectioning_start" in keywords:
            val = keywords["sectioning_start"]
            if val < 0 or val > 4:
                raise ValueError("Invalid value for sectioning start: %s" % val)
            else:
                self.sectioning_start = val

    replchars = re.compile(r'([@{}])')
    acc = Acc()

    def _print(self, text, **kw):
        nl = kw.pop('nl', False)
        escape = kw.pop('escape', True)
        if nl and not self.acc.endswith('\n'):
            self.acc += '\n'
        if text:
            if escape:
                self.acc += self.replchars.sub(r'@\1', text)
            else:
                self.acc += text

    def _begin_print(self):
        s = self.acc
        self.acc = Acc()
        return s

    def _end_print(self, val = None):
        s = self.acc
        self.acc = val
        return str(s)

    def __str__(self):
        self._begin_print()
        for elt in self.tree:
            elt.format()
        self.acc.trimpara()
        return self._end_print()
