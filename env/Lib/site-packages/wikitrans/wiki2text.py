#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2008-2018 Sergey Poznyakoff
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
Wiki markup to plain text translator.

Classes:

TextWikiMarkup       -- Converts Wiki material to plain text.
TextWiktionaryMarkup -- Reserved for future use. Currently does the same as
                        TextWikiMarkup.

"""

from wikitrans.wikitoken import *
from wikitrans.wikimarkup import *
from wikitrans.wikins import wiki_ns_re, wiki_ns
import re
try:
    from urllib import quote as url_quote
except ImportError:
    from urllib.parse import quote as url_quote


class TextSeqNode(WikiSeqNode):
    def format(self):
        string = ""
        for x in self.content:
            if len(string) > 1 and not string[-1].isspace():
                string += ' '
            string += x.format()
        return string


class TextTextNode(WikiTextNode):
    def format(self):
        if isinstance(self.content, list):
            string = ""
            for s in self.content:
                if string:
                    if string.endswith("."):
                        string += "  "
                    else:
                        string += " "
                string += s
        else:
            string = self.content
        return string


class TextPreNode(WikiSeqNode):
    def format(self):
        string = ""
        for x in self.content:
            string += x.format()
        string += '\n'
        return string


class TextParaNode(WikiSeqNode):
    def format(self):
        string = ""
        for x in self.content:
            string += x.format()
        string = self.parser.fmtpara(string) + '\n\n'
        return string


class TextItNode(WikiSeqNode):
    def format(self):
        string = ""
        for x in self.content:
            s = x.format()
            if s:
                string += " " + s
        return "_" + string.lstrip(" ") + "_"


class TextBoldNode(WikiSeqNode):
    def format(self):
        string = ""
        for x in self.content:
            if string.endswith("."):
                string += "  "
            else:
                string += " "
            string += x.format()
        return string.upper()


class TextLinkNode(WikiSeqNode):
    def format(self):
        arg = self.content[0].format()
        if len(self.content) > 1:
            s = [x for x in map(lambda x: x.format(), self.content)]
            text = s[1]
        else:
            s = None
            text = None

        if s:
            if s[0] == 'disambigR' or s[0] == 'wikiquote':
                return ""
            if len(s) > 1 and s[1] == 'thumb':
                return ""
        (qual, sep, tgt) = arg.partition(':')
        if tgt != '':
            ns = self.parser.wiki_ns_name(qual)
            if ns:
                if ns == 'NS_IMAGE':
                    if not self.parser.show_urls:
                        return ""
                    text = "[%s: %s]" % (qual, text if text else arg)
                    tgt = "%s/%s/250px-%s" % (self.image_base,
                                              url_quote(tgt),
                                              url_quote(tgt))
                elif ns == 'NS_MEDIA':
                    text = "[%s]" % (qual)
                else:
                    tgt = self.parser.mktgt(tgt)
            elif self.type == 'LINK' and qual in self.parser.langtab:
                text = self.parser.langtab[qual] + ": " + tgt
                tgt = self.parser.mktgt(tgt, qual)
            else:
                tgt = self.parser.mktgt(tgt)
        else:
            tgt = self.parser.mktgt(arg)
        if self.parser.show_urls:
            return "%s (see %s) " % (text, tgt)
        elif not text or text == '':
            return arg
        else:
            return text


class TextTmplNode(TextLinkNode):
    def format(self):
        return '[' + super(TextTmplNode, self).format() + ']'


class TextBarNode(WikiNode):
    def format(self):
        w = self.parser.width
        if w < 5:
            w = 5
        return "\n" + ("-" * (w - 5)).center(w - 1) + "\n"


class TextHdrNode(WikiHdrNode):
    def format(self):
        return ("\n"
                + ("*" * self.level)
                + " "
                + self.content.format().lstrip(" ")
                + "\n\n")


class TextRefNode(WikiRefNode):
    def format(self):
        text = self.content.format()
        if text:
            return "%s (see %s) " % (text, self.ref)
        else:
            return "see " + self.ref


class TextEnvNode(WikiEnvNode):
    def format(self):
        type = self.envtype
        lev = self.level
        if lev > self.parser.width - 4:
            lev = 1
        string = ""
        n = 1
        for s in self.content:
            if not string.endswith("\n"):
                string += "\n"
            x = s.content.format()
            if type == "unnumbered":
                string += self.parser.indent(lev, "- " + x.lstrip(" "))
            elif type == "numbered":
                string += self.parser.indent(lev, "%d. %s" % (n, x))
                n += 1
            elif type == "defn":
                if s.subtype == 0:
                    string += self.parser.indent(lev-1, x)
                else:
                    string += self.parser.indent(lev+3, x)
            if not string.endswith("\n"):
                string += "\n"
        return string


class TextIndNode(WikiIndNode):
    def format(self):
        return (" " * self.level) + self.content.format() + '\n'


class TextTagNode(WikiTagNode):
    def format(self):
        if self.tag == 'code':
            self.parser.nested += 1
            s = self.content.format()
            self.parser.nested -= 1
        elif self.tag == 'ref':
            s = '[%d]' % (self.idx+1)
        elif self.tag == 'references':
            s = '\nReferences:\n'
            for ref in self.parser.references:
                s += ('[%d]. ' % (ref.idx+1))  + ref.content.format() + '\n'
        else:
            s = '<' + self.tag
            if self.args:
                s += ' ' + str(self.args)
            s += '>' + self.content.format() + '</' + self.tag + '>'
        return s


class TextWikiMarkup(WikiMarkup):
    """A Wiki markup to plain text translator.

    Usage:

      x = TextWikiMarkup(file="input.wiki")
      # Parse the input:
      x.parse()
      # Print it as plain text:
      print(str(x))

    """

    # Output width
    width = 78
    # Do not show references.
    show_urls = False
    # Provide a minimum markup
    markup = True

    # Number of current element in the environment
    num = 0

    # Array of footnote references
    references = []

    def __init__(self, *args, **keywords):
        """Create a TextWikiMarkup object.

        TextWikiMarkup([filename=FILE],[file=FD],[text=STRING],[lang=CODE],
                       [html_base=URL],[image_base=URL],[media_base=URL],
                       [width=N],[show_urls=False])

        Most arguments have the same meaning as in the WikiMarkup constructor.

        Class-specific arguments:

        width=N
          Limit output width to N columns. Default is 78.
        show_urls=False
          By default, the link URLs are displayed in parentheses next to the
          link text. If this argument is given, only the link text will be
          displayed.
        """

        super(TextWikiMarkup, self).__init__(*args, **keywords)
        if 'width' in keywords:
            self.width = keywords['width']
        if 'show_urls' in keywords:
            self.show_urls = keywords['show_urls']
        self.token_class['SEQ'] = TextSeqNode
        self.token_class['TEXT'] = TextTextNode
        self.token_class['PRE'] = TextPreNode
        self.token_class['PARA'] = TextParaNode
        self.token_class['SEQ'] = TextSeqNode
        self.token_class['IT'] = TextItNode
        self.token_class['BOLD'] = TextBoldNode
        self.token_class['LINK'] = TextLinkNode
        self.token_class['TMPL'] = TextTmplNode
        self.token_class['BAR'] = TextBarNode
        self.token_class['HDR'] = TextHdrNode
        self.token_class['REF'] = TextRefNode
        self.token_class['ENV'] = TextEnvNode
        self.token_class['IND'] = TextIndNode
        self.token_class['TAG'] = TextTagNode

    def wiki_ns_name(self, str):
        if str in wiki_ns[self.lang]:
            return wiki_ns[self.lang][str]
        elif str in wiki_ns_re[self.lang]:
            for elt in wiki_ns_re[self.lang][str]:
                if str.beginswith(elt[0]) and str.endswith(elt[1]):
                    return elt[2]
        return None

    def mktgt(self, tgt, lang = None):
        if not lang:
            lang = self.lang
        return self.html_base % { 'lang' : lang } + url_quote(tgt)

    def indent(self, lev, text):
        if text.find('\n') == -1:
            s = (" " * lev) + text
        else:
            s = ""
            for elt in text.split('\n'):
                if elt:
                    s += (" " * lev) + elt + '\n'
            if not text.endswith('\n'):
                s = s.rstrip('\n')
        return s

    def fmtpara(self, input):
        output = ""
        linebuf = ""
        length = 0
        for s in input.split():
            wlen = len(s)
            if len(linebuf) == 0:
                wsc = 0
            elif linebuf.endswith("."):
                wsc = 2
            else:
                wsc = 1
            if length + wsc + wlen > self.width:
                # FIXME: fill out linebuf
                output += linebuf + '\n'
                wsc = 0
                length = 0
                linebuf = ""
            linebuf += " " * wsc + s
            length += wsc + wlen
        return output + linebuf

    def __str__(self):
        str = ""
        for elt in self.tree:
            str += elt.format()
        return str


class TextWiktionaryMarkup(TextWikiMarkup):
    """A class for translating Wiktionary articles into plain text.

    Reserved for future use. Currently does the same as TextWikiMarkup.
    """

    html_base='http://%(lang)s.wiktionary.org/wiki/'
