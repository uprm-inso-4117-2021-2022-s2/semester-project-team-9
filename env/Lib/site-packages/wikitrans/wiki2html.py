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
Wiki markup to HTML translator.

Classes:

HtmlWikiMarkup       -- Converts Wiki material to HTML.
HtmlWiktionaryMarkup -- Reserved for future use. Currently does the same as
                        HtmlWikiMarkup.

"""

from __future__ import print_function
from wikitrans.wikimarkup import *
from wikitrans.wikitoken import *
from wikitrans.wikins import wiki_ns_re, wiki_ns
import re
try:
    from urllib import quote as url_quote
except ImportError:
    from urllib.parse import quote as url_quote

try:
    from html import escape as html_escape
except ImportError:
    from cgi import escape as html_escape

__all__ = [ "HtmlWikiMarkup", "HtmlWiktionaryMarkup" ]


class HtmlSeqNode(WikiSeqNode):
    def format(self):
        s = ''
        for x in self.content:
            s += x.format()
        return s


class HtmlLinkNode(HtmlSeqNode):
    def format(self):
        arg = self.content[0].format()
        text = None
        if len(self.content) > 1:
            s = [x for x in map(lambda x: x.format(), self.content)]
            if s[0] == 'disambigR' or s[0] == 'wikiquote':
                return ""
            elif len(s) > 1 and s[1] == 'thumb':
                return ""
            text = '<span class="template">' + s[1] + '</span>'
            if self.type == 'TMPL':
                if re.match("t[+-]$", s[0]):
                    if len(s) > 2:
                        text = s[2]
                elif s[0] == "term":
                    text = self.parser.tmpl_term(s)
                elif s[0] == "proto":
                    text = self.parser.tmpl_proto(s)
                return text

        (qual, sep, tgt) = arg.partition(':')
        if tgt != '':
            ns = self.parser.wiki_ns_name(qual)
            if ns:
                if ns == 'NS_IMAGE':
                    return ''
                elif ns == 'NS_MEDIA':
                    tgt = self.parser.media_base + '/' + tgt
                else:
                    tgt = self.parser.mktgt(tgt)
            elif self.type == 'LINK' and qual in self.parser.langtab:
                tgt = self.parser.mktgt(tgt, qual)
                if not text or text == '':
                    text = self.parser.langtab[qual]
            else:
                tgt = self.parser.mktgt(tgt)
        else:
            tgt = self.parser.mktgt(arg)
        return "<a href=\"%s\">%s</a>" % (tgt,
                                          text if (text and text != '') else arg)


class HtmlRefNode(WikiRefNode):
    def format(self):
        target = self.ref
        text = self.content.format()
        return "<a href=\"%s\">%s</a>" % (
            target,
            text if (text and text != '') else target
        )


class HtmlFontNode(HtmlSeqNode):
    def format(self):
        comm = { 'IT': 'i',
                 'BOLD': 'b' }
        s = '<%s>' % comm[self.type]
        for x in self.content:
            s += x.format()
        s += '</%s>' % comm[self.type]
        return s


class HtmlTextNode(HtmlSeqNode):
    def format(self):
        if isinstance(self.content, list):
            s = ''.join(self.content)
        else:
            s = html_escape(self.content, quote=False)
        return s


class HtmlHdrNode(WikiHdrNode):
    def format(self):
        level = self.level
        if level > 6:
            level = 6
        return "<h%s>%s</h%s>\n\n" % (level, self.content.format(), level)


class HtmlBarNode(WikiNode):
    def format(self):
        return "<hr/>\n"


class HtmlEnvNode(WikiEnvNode):
    def format(self):
        type = self.envtype
        lev = self.level
        if lev > 4:
            lev = 2
        string = ""
        for s in self.content:
            n = s.subtype;
            string += "<%s>%s</%s>" % (self.parser.envt[type]["elt"][n],
                                       s.content.format(),
                                       self.parser.envt[type]["elt"][n])
        return "<%s>%s</%s>" % (self.parser.envt[type]["hdr"],
                                string,
                                self.parser.envt[type]["hdr"])
        return string


class HtmlTagNode(WikiTagNode):
    def format(self):
        if self.tag == 'code':
            self.parser.nested += 1
            s = self.content.format()
            self.parser.nested -= 1
            return '<pre><code>' + s + '</code></pre>' #FIXME
        elif self.tag == 'ref':
            n = self.idx+1
            return '<sup id="cite_ref-%d" class="reference"><a name="cite_ref-%d" href=#cite_note-%d">%d</a></sup>' % (n, n, n, n)
        elif self.tag == 'references':
            s = '<div class="references">\n'
            s += '<ol class="references">\n'
            n = 0
            for ref in self.parser.references:
                n += 1
                s += ('<li id="cite_note-%d">'
                      + '<span class="mw-cite-backlink">'
                      + '<b><a href="#cite_ref-%d">^</a></b>'
                      + '</span>'
                      + '<span class="reference-text">'
                      + ref.content.format()
                      + '</span>'
                      + '</li>\n') % (n, n)
            s += '</ol>\n</div>\n'
            return s
        else:
            s = '<' + self.tag
            if self.args:
                s += ' ' + str(self.args)
            s += '>'
            s += self.content.format()
            return s + '</' + self.tag + '>'


class HtmlParaNode(HtmlSeqNode):
    def format(self):
        return "<p>" + super(HtmlParaNode, self).format() + "</p>\n"


class HtmlPreNode(HtmlSeqNode):
    def format(self):
        s = super(HtmlPreNode, self).format()
        if self.parser.nested:
            return s
        else:
            return '<pre>' + s + '</pre>'


class HtmlIndNode(WikiIndNode):
    def format(self):
        return ("<dl><dd>" * self.level) + self.content.format() + "</dd></dl>" * self.level


class HtmlWikiMarkup(WikiMarkup):
    """A Wiki markup to HTML translator class.

    Usage:

      x = HtmlWikiMarkup(file="input.wiki")
      # Parse the input:
      x.parse()
      # Print it as HTML:
      print(str(x))

    Known bugs:
      * [[official position]]s
       Final 's' gets after closing </a> tag. Should be before.
    """

    nested = 0
    references = []
    def __init__(self, *args, **kwargs):
        """Create a HtmlWikiMarkup object.

        HtmlWikiMarkup([filename=FILE],[file=FD],[text=STRING],[lang=CODE],
                       [html_base=URL],[image_base=URL],[media_base=URL])

        The arguments have the same meaning as in the WikiMarkup constructor.

        """

        super(HtmlWikiMarkup, self).__init__(*args, **kwargs)
        self.token_class['LINK'] = HtmlLinkNode
        self.token_class['TMPL'] = HtmlLinkNode
        self.token_class['REF'] = HtmlRefNode
        self.token_class['IT'] = HtmlFontNode
        self.token_class['BOLD'] = HtmlFontNode
        self.token_class['HDR'] = HtmlHdrNode
        self.token_class['BAR'] = HtmlBarNode
        self.token_class['ENV'] = HtmlEnvNode
        self.token_class['TAG'] = HtmlTagNode
        self.token_class['PARA'] = HtmlParaNode
        self.token_class['PRE'] = HtmlPreNode
        self.token_class['IND'] = HtmlIndNode
        self.token_class['TEXT'] = HtmlTextNode
        self.token_class['SEQ'] = HtmlSeqNode

    def wiki_ns_name(self, str):
        if str in wiki_ns[self.lang]:
            return wiki_ns[self.lang][str]
        elif str in wiki_ns_re[self.lang]:
            for elt in wiki_ns_re[self.lang][str]:
                if str.beginswith(elt[0]) and str.endswith(elt[1]):
                    return elt[2]
        return None

    envt = { "unnumbered": { "hdr": "ul",
                             "elt": ["li"] },
             "numbered":   { "hdr": "ol",
                             "elt": ["li"] },
             "defn":       { "hdr": "dl",
                             "elt": ["dt","dd"] } }

    def mktgt(self, tgt, lang = None):
        if not lang:
            lang = self.lang
        return self.html_base % { 'lang' : lang } + url_quote(tgt)

    def tmpl_term(self, s):
        if len(s) == 2:
            return s[1]
        text = None
        trans = None
        for x in s[1:]:
            m = re.match('(\w+)=', x)
            if m:
                if m.group(1) == "tr":
                    trans = x[m.end(1)+1:]
            elif not text:
                text = x
        if text:
            if trans:
                text += ' <span class="trans">[' + trans + ']</span>'
        return text

    def tmpl_proto(self, s):
        text = '<span class="proto-lang">Proto-' + s[1] + '</span>'
        if len(s) >= 4:
            n = 0
            for x in s[2:-2]:
                if n > 0:
                    text += ','
                n += 1
                text += ' <span class="proto">' + x + '</span>'
                text += ' <span class="meaning">(' + s[-2] + ')</span>'
        return text

    def __str__(self):
        str = ""
        for elt in self.tree:
            str += elt.format()
        return str


class HtmlWiktionaryMarkup(HtmlWikiMarkup):
    """A class for translating Wiktionary articles into HTML.

    Reserved for future use. Currently does the same as HtmlWikiMarkup.
    """

    html_base='http://%(lang)s.wiktionary.org/wiki/'
