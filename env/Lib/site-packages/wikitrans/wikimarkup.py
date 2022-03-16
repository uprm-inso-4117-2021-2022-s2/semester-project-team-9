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
Wiki markup parser.

This module provides two class:

WikiMarkupParser:
   An abstract parser class, which serves as a base class for all markup
   classes in this package.

WikiMarkup
   A subclass of the above, providing basic input method.

"""

from __future__ import print_function
import sys
import re
from types import *
from wikitrans.wikitoken import *

__all__ = [ "WikiMarkupParser", "WikiMarkup",
            "TagAttributes", "TagAttributeSyntaxError" ]


class UnexpectedTokenError(Exception):
    def __init__(self, value):
        self.value = value


class TagAttributeSyntaxError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class TagAttributes(object):
    """A dictionary-like collection of tag attributes.

    Example:

      attr = TagAttributes('href="foo" length=2')
      if 'href' in attr:
          print(x['href'])   # returns "foo"
      for a in attr:
          ...
    """

    attrstart = re.compile("^(?P<attr>[a-zA-Z0-9_-]+)(?P<eq>=\")?")
    valseg = re.compile("^[^\\\"]+")
    tab = {}
    printable = None
    def __init__(self, string):
        if not string:
            self.printable = ''
            return
        self.printable = string
        s = string
        self.tab = {}
        while s != '':
            s = s.strip()
            m = self.attrstart.match(s)
            if m:
                name = m.group('attr')
                val = ''
                s = s[m.end(0):]
                if m.group('eq'):
                    while 1:
                        m = self.valseg.match(s)
                        val += m.group(0)
                        s = s[m.end(0):]
                        if s[0] == '\\':
                            val += s[1]
                            s += 2
                        elif s[0] == '"':
                            s = s[1:]
                            break
                else:
                    val = 1
                self.tab[name] = val
            else:
                raise TagAttributeSyntaxError(s)

    def __len__(self):
        return len(self.tab)

    def __getitem__(self, key):
        return self.tab[key]

    def __contains__(self, key):
        return key in self.tab

    def __iter__(self):
        for key in self.tab:
            yield(key)

    def has_key(self, key):
        return self.__contains__(key)

    def __setitem__(self, key, value):
        self.tab[key] = value

    def __delitem__(self, key):
        del self.tab[key]

    def __str__(self):
        return self.printable

    def __repr__(self):
        return self.printable


class WikiMarkupParser(object):
    """Parser for Wiki markup language.

    Given input in Wiki markup language creates an abstract parse tree for it.
    This is a base class for actual parsers. The subclasses must provide the
    input method.

    Public methods:

    parse()  --  parse the input.

    Abstract methods (must be overridden by the subclass):

    input()  --  returns next physical line from the input material.

    Public attributes:

    Input:
    debug_level -- debug verbosity level (0 - no debug info, 100 - excessively
                   copious debug messages). Default is 0.
    strict      -- if True, parser will throw exception upon encountering
                   invalid markup tag (mostly for future use)

    Output:
    tree     --  constructed parse tree (a subclass of WikiNode)

    """

    delim = re.compile("^==+[ \t]*|[ \t]*==+[ \t]*$|(^----$)|^\\*+|^#+|^[;:]+|(\\[\\[)|\\[|(\\{\\{)|(\\]\\])|\\]|(\\}\\})|\\||(\\'\\'\\'?)|<")
    otag = re.compile("<(?P<tag>[a-zA-Z0-9_]+)(?:\s+(?P<args>[^/][^>]+))?\s*(?P<closed>/)?>")
    ctag = re.compile("</(?P<tag>[a-zA-Z0-9_]+)\s*>")
    refstart = re.compile("^https?://")

    close_delim = {
        '[': ']',
        '[[': ']]',
        '{{': '}}'
    }

    # Environment types:
    envtypes = { "*": [ "unnumbered", 0 ],
                 "#": [ "numbered", 0 ],
                 ";": [ "defn", 0 ],
                 ":": [ "defn", 1 ]
    }

    toklist = None
    tokind = 0
    newline = 0
    tree = None

    tags = [ 'code', 'nowiki', 'tt', 'div', 'ref', 'references' ]

    debug_level = 0
    strict = False

    def dprint(self, lev, fmt, *argv):
        """If current debug level is greater than or equal to lev, print *argv
        according to format.
        """
        if self.debug_level >= lev:
            for l in (fmt % argv).split('\n'):
                print("[DEBUG] %s" % l)

    inline_delims = [ "''", "'''", "[", "]", "[[", "]]", "{{", "}}", "|" ]

    token_class = {}

    def _new_node(self, **kwarg):
        return self.token_class[kwarg['type']](self, **kwarg)

    def tokread(self):
        """Read next token from the input. Return it as a subclass of WikiNode."""
        line = None
        pos = 0
        while 1:
            if (not line or pos == len(line)):
                try:
                    line = self.input()
                    pos = 0
                except StopIteration:
                    line = u''

            if not line or line == "":
                yield(self._new_node(type='NIL'))
                break

            if line == '\n':
                yield(self._new_node(type='NL'))
                line = None
                continue

            self.dprint(100, "LINE: %s", line[pos:])
            m = self.delim.search(line, pos)

            if m:
                if (pos < m.start(0)):
                    yield(self._new_node(type='TEXT',
                                         content=line[pos:m.start(0)]))
                pos = m.start(0)
                t = None

                if line[m.start(0)] == '<':
                    m = self.otag.match(line, pos)
                    if m:
                        pos = m.end(0)
                        if m.group('tag') == 'nowiki':
                            if not m.group('closed'):
                                while 1:
                                    try:
                                        m = self.ctag.search(line, pos)
                                        if m and m.group('tag') == 'nowiki':
                                            yield(self._new_node(type='TEXT',
                                                                 content=line[pos:m.start(0)] ))
                                            pos = m.end(0)
                                            break

                                        yield(self._new_node(type='TEXT',
                                                             content=line[pos:]))

                                        line = self.input()
                                        pos = 0
                                    except StopIteration:
                                        break
                            continue
                        elif m.group('tag') in self.tags:
                            try:
                                yield(self._new_node(type='OTAG',
                                                  tag=m.group('tag'),
                                                  isblock=(line[pos] == '\n'),
                                                  args=TagAttributes(m.group('args'))))
                                if m.group('closed'):
                                    yield(self._new_node(type='CTAG',
                                                         tag=m.group('tag')))
                            except TagAttributeSyntaxError:
                                yield(self._new_node(type='TEXT',
                                                     content=m.group(0)))
                            continue
                        else:
                            yield(self._new_node(type='TEXT',
                                                 content=m.group(0)))
                            continue
                    else:
                        m = self.ctag.match(line, pos)
                        if m:
                            if m.group('tag') in self.tags:
                                yield(self._new_node(type='CTAG',
                                                     tag=m.group('tag')))
                            else:
                                yield(self._new_node(type='TEXT',
                                                     content=m.group(0)))
                            pos = m.end(0)
                            continue
                        else:
                            yield(self._new_node(type='TEXT',
                                                 content=line[pos:pos+1]))
                            pos += 1
                            continue
                else:
                    pos = m.end(0)
                    content = m.group(0)
                    if content[0] in self.envtypes:
                        node = self._new_node(type='DELIM',
                                              content=content,
                                              isblock=True,
                                              continuation=pos < len(line) and line[pos] == ":")
                        if node.continuation:
                            node.content += node.content[0]
                            pos += 1

                        yield(node)

                        while pos < len(line) and line[pos] in [' ', '\t']:
                            pos += 1
                    else:
                        yield(self._new_node(type='DELIM',
                                             isblock=(content.strip() not in self.inline_delims),
                                             content=content.strip()))
                    continue

            if line:
                if line[-1] == '\n':
                    if line[pos:-1] != '':
                        yield(self._new_node(type='TEXT', content=line[pos:-1]))
                    yield(self._new_node(type='NL'))
                else:
                    yield(self._new_node(type='TEXT', content=line[pos:]))
                line = None

    def input(self):
        """Return next physical line from the input.

        This method must be overridden by the subclass.
        """
        return None

    def swaptkn(self, i, j):
        """Swap tokens at indices i and j in toklist."""
        self.dprint(80, "SWAPPING %s <-> %s", i, j)
        x = self.toklist[i]
        self.toklist[i] = self.toklist[j]
        self.toklist[j] = x

    def tokenize(self):
        """Tokenize the input.

        Read tokens from the input (supplied by the input() method). Place the
        obtained tokens in the toklist array.
        """
        self.toklist = []
        for tok in self.tokread():
            self.dprint(100, "TOK: %s", tok)
            self.toklist.append(tok)
        # Determine and fix up the ordering of bold and italic markers
        # There are three possible cases:
        #
        # 1a. '''a b ''c'' d'''
        # 1b. ''a b '''c''' d''
        #
        # 2a. '''''a b'' c d'''
        # 2b. '''''a b''' c d''
        #
        # 3a. '''a b ''c d'''''
        # 3b. ''a b '''c d'''''
        stack = []
        for i in range(0, len(self.toklist)):
            if (self.toklist[i].type == 'DELIM'
                and (self.toklist[i].content == "''"
                     or self.toklist[i].content == "'''")):
                if len(stack) > 0:
                    if self.toklist[stack[-1]].content == self.toklist[i].content:
                        # Case 1: just pop the matching delimiter off the stack
                        stack.pop()
                    elif len(stack) == 2 and stack[-2] + 1 == stack[-1]:
                        # Case 2: swap delimiters saved on stack ...
                        self.swaptkn(stack[-2], stack[-1])
                        #         and pop off the matching one
                        stack.pop()
                    elif (i < len(self.toklist)
                          and self.toklist[i+1].type == 'DELIM'
                          and self.toklist[stack[-1]].content
                                      == self.toklist[i+1].content):
                        # Case 3: swap current and next tokens
                        self.swaptkn(i, i+1)
                        #         and pop off the matching one
                        stack.pop()
                    else:
                        # Push the token on stack
                        stack.append(i)
                else:
                    # Push the token on stack
                    stack.append(i)
        # Redefine all non-matched tokens as TEXT
        for i in stack:
            # FIXME: How to convert node to TEXT?
            self.toklist[i] = self._new_node(type='TEXT',
                                             content=str(self.toklist[i]))

    mark = []

    def push_mark(self):
        """Save the current token index on stack."""
        self.mark.append(self.tokind)

    def pop_mark(self):
        """Restore the token index from top of stack."""
        self.tokind = self.mark.pop()

    def clear_mark(self):
        """Forget the last mark."""
        self.mark.pop()

    def lookahead(self, off=0):
        """Peek a token at index (tokind+off)."""
        tok = self.toklist[self.tokind+off]
        self.dprint(20, "lookahead(%s): %s", off, tok)
        return tok

    def setkn(self, val):
        """Store token val at the current token index."""
        self.toklist[self.tokind] = val

    def getkn(self):
        """Get next token from the toklist. Advance tokind."""
        self.newline = self.tokind == 0 or self.toklist[self.tokind-1].type == 'NL'
        if self.tokind == len(self.toklist):
            return self._new_node(type='NIL')
        tok = self.toklist[self.tokind]
        self.tokind = self.tokind + 1
        self.dprint(20, "getkn: %s", tok)
        return tok

    def ungetkn(self, tok=None):
        """Unget the last read token.

        Decrease the tokind by one, so the last read token will be read again.
        If optional argument is supplied and is not None, store it in the toklist
        in place of the current token.
        """
        self.tokind = self.tokind - 1
        self.newline = self.tokind == 0 or self.toklist[self.tokind-1].type == 'NL'
        if tok:
             self.toklist[self.tokind] = tok
        self.dprint(20, "ungetkn: %s", tok)
        return self.toklist[self.tokind]

    def fixuptkn(self, tok):
        """Replace the recently read token by tok."""
        if self.tokind == 0:
            raise IndexError('WikiMarkupParser.fixuptkn called at start of input')
        self.toklist[self.tokind-1] = tok
        return tok

    def dump(self, tree, file=sys.stdout):
        """Dump the tree to file, node by node."""
        for node in tree:
            file.write(str(node))
            file.write('\n')

    def is_block_end(self, tok):
        """Return True if tok ends a block environment."""
        if tok.type == 'NIL':
            return True
        elif tok.type == 'NL':
            if self.lookahead().type == 'NIL':
                return True
            elif self.lookahead().type == 'NL':
                self.getkn()
                return True
        elif tok.type in ['DELIM', 'CTAG', 'TAG']:
            if tok.isblock:
                self.ungetkn(tok)
                return True
        return False

    def parse_para(self, tok):
        """Read paragraph starting at tok."""
        self.dprint(80, "ENTER parse_para: %s", tok)

        acc = { 'seq': [],
                'textlist': [] }

        def flush():
            if acc['textlist']:
                acc['seq'].append(self._new_node(type='TEXT',
                                                 content=''.join(acc['textlist'])))
                acc['textlist'] = []

        if (isinstance(tok, WikiContentNode)
            and isinstance(tok.content, str)
            and re.match("^[ \t]", tok.content)):
            type = 'PRE'
            rx = re.compile("^\S")
        else:
            type = 'PARA'
            rx = re.compile("^[ \t]")

        while not self.is_block_end(tok):
            if tok.type == 'TEXT':
                if rx and self.newline and rx.match(tok.content):
                    self.ungetkn()
                    break
                acc['textlist'].append(tok.content)
            elif tok.type == 'NL':
                acc['textlist'].append('\n')
            elif tok.type == 'OTAG':
                flush()
                acc['seq'].append(self.parse_tag(tok))
            elif tok.type == 'DELIM':
                flush()
                acc['seq'].append(self.parse_inline_delim(tok))
            else:
                if self.strict:
                    raise UnexpectedTokenError(tok)
                # FIXME: Another possible variant of handling this case is to
                # convert tok to TEXT node and append it to acc['seq']
            tok = self.getkn()
        flush()
        if acc['seq']:
            tok = self._new_node(type=type, content=acc['seq'])
        else:
            tok = None
        self.dprint(80, "LEAVE parse_para=%s", tok)
        return tok

    def parse_block_delim(self, tok):
        """Parse block environment starting at tok."""
        self.dprint(80, "ENTER parse_block_delim")
        assert(tok.type == 'DELIM')
        if tok.content == "----":
            node = self._new_node(type = 'BAR')
        elif tok.content[0:2] == "==":
            node = self.parse_header(tok)
            if not node:
                tok = self.ungetkn(self._new_node(type='TEXT',
                                                  content=tok.content))
        elif tok.content[0] in self.envtypes:
            node = None
            if tok.content[0] == ':':
                t = self.lookahead(-2)
                if not (t.type == 'DELIM' and t.content == ';'):
                    node = self.parse_indent(tok)
            if not node:
                node = self.parse_env(tok)
        else:
            self.ungetkn(tok)
            node = None
        self.dprint(80, "LEAVE parse_block_delim=%s", node)
        return node

    def parse_line(self):
        """Parse the input line."""
        self.dprint(80, "ENTER parse_line")
        list = []
        while True:
            tok = self.getkn()
            if tok.type == 'NL' or tok.type == 'NIL':
                break
            elif tok.type == 'TEXT':
                list.append(tok)
            elif tok.type == 'DELIM':
                if tok.isblock:
                    tok = self._new_node(type = 'TEXT', content = tok.content)
                    self.fixuptkn(tok)
                    list.append(tok)
                elif tok.content[0] == ":":
                    # FIXME
                    list.append(self.parse_indent(tok))
                    break
                else:
                    x = self.parse_inline_delim(tok)
                    if x:
                        list.append(x)
                    else:
                        list.append(self.fixuptkn(self._new_node(type = 'TEXT',
                                                                 content = tok.content)))
            elif tok.type == 'OTAG':
                if tok.isblock:
                    self.ungetkn()
                    break
                list.append(self.parse_tag(tok))
            else:
                list.append(tok)
        ret = self._new_node(type='SEQ', content=list)
        self.dprint(80, "LEAVE parse_line=%s", ret)
        return ret

    def parse_indent(self, tok):
        """Parse indented block starting at tok."""
        lev = len(tok.content)
        self.dprint(80, "ENTER parse_indent(%s)", lev)
        x = self._new_node(type='IND', level=lev, content=self.parse_line())
        self.dprint(80, "LEAVE parse_indent=%s", x)
        return x

    def parse_fontmod(self, delim, what):
        """Parse font modification directive (bold or italics).

        Arguments:

        delim    --  starting delimiter ("''" or "'''")
        what     --  'IT' or 'BOLD'
        """
        self.dprint(80, "ENTER parse_fontmod(%s,%s), tok %s",
                    delim, what, self.lookahead())
        seq = []
        text = ''
        while True:
            tok = self.getkn()
            if tok.type == 'TEXT':
                text += tok.content
            elif self.is_block_end(tok):
                self.dprint(80, "LEAVE parse_fontmod=%s", "None")
                return None
            elif tok.type == 'DELIM':
#                self.dprint(80, "got %s, want %s", tok.content, delim)
                if tok.content == delim:
                    break
                else:
                    if text:
                        seq.append(self._new_node(type='TEXT', content=text))
                        text = ''
                    x = self.parse_inline_delim(tok)
                    if x:
                        seq.append(x)
                    else:
                        self.dprint(80, "LEAVE parse_fontmod=%s", "None")
                        return None
            elif tok.type == 'NL':
                seq.append(self._new_node(type='TEXT', content='\n'))
            else:
                self.dprint(80, "LEAVE parse_fontmod=None")
                return None
        if text:
            seq.append(self._new_node(type='TEXT', content=text))
        res = self._new_node(type=what, content=seq)
        self.dprint(80, "LEAVE parse_fontmod=%s", res)
        return res

    def parse_ref(self):
        """Parse a reference block ([...])"""
        self.dprint(80, "ENTER parse_ref")
        tok = self.getkn()
        if not (tok.type == 'TEXT' and self.refstart.match(tok.content)):
            self.dprint(80, "LEAVE parse_ref=None")
            return None

        seq = []
        (ref, sep, text) = tok.content.partition(' ')
        if text:
            seq.insert(0, self._new_node(type='TEXT', content=text))

        while True:
            tok = self.getkn()
            if tok.type == 'NIL':
                self.dprint(80, "LEAVE parse_ref=None")
                return None
            elif self.is_block_end(tok):
                self.dprint(80, "LEAVE parse_ref=None")
                return None
            elif tok.type == 'DELIM':
                if tok.content == ']':
                    break
                else:
                    tok = self.parse_inline_delim(tok)
                    if tok:
                        seq.append(tok)
                    else:
                        self.dprint(80, "LEAVE parse_ref=None")
                        return None
            elif tok.type == 'OTAG':
                list.append(self.parse_tag(tok))
            else:
                seq.append(tok)

        ret = self._new_node(type='REF', ref=ref,
                             content=self._new_node(type='SEQ', content=seq))
        self.dprint(80, "LEAVE parse_ref= %s", ret)
        return ret

    def parse_link(self, type, delim):
        """Parse an external link ([[...]]).

        In this implementation, it is also used to parse template
        references ({{...}}).

        Arguments:

        type   -- 'LINK' or 'TMPL'
        delim  -- expected closing delimiter.
        """
        self.dprint(80, "ENTER parse_link(%s,%s)", type, delim)
        subtree = []
        list = []
        while True:
            tok = self.getkn()
            if tok.type == 'NIL':
                self.dprint(80, "LEAVE parse_link=None [EOF]")
                return None
            if tok.type == 'DELIM':
                if tok.content == delim:
                    if list:
                        subtree.append(self._new_node(type='SEQ',
                                                      content=list))
                    break
                elif tok.content == "|":
                    if len(list) > 1:
                        subtree.append(self._new_node(type='SEQ',
                                                      content=list))
                    elif list:
                        subtree.append(list[0])
                    list = []
                else:
                    x = self.parse_inline_delim(tok)
                    if x:
                        list.append(x)
                    else:
                        self.dprint(80, "LEAVE parse_link=None [bad inline]")
                        return None
            elif tok.type == 'TEXT':
                list.append(tok)
            else:
                self.dprint(80, "LEAVE parse_link=None [unexpected token]")
                return None
        ret = self._new_node(type=type, content=subtree)
        self.dprint(80, "LEAVE parse_link=%s", ret)
        return ret

    def parse_inline_delim(self, tok):
        """Parse an inline block."""
        self.dprint(80, "ENTER parse_inline_delim")
        assert(tok.type == 'DELIM')
        self.push_mark()
        if tok.content == "''":
            x = self.parse_fontmod(tok.content, 'IT')
        elif tok.content == "'''":
            x = self.parse_fontmod(tok.content, 'BOLD')
        elif tok.content == "[":
            x = self.parse_ref()
        elif tok.content == "[[":
            x = self.parse_link('LINK', "]]")
        elif tok.content == "{{":
            x = self.parse_link('TMPL', "}}")
        else:
            x = None

        if x:
            self.clear_mark()
        else:
            self.dprint(80, "BEGIN DELIMITER RECOVERY: %s", tok)
            self.pop_mark()
            x = self.fixuptkn(self._new_node(type='TEXT', content=tok.content))
            od = tok.content
            if od in self.close_delim:
                cd = self.close_delim[od]
                lev = 0
                for i, tok in enumerate(self.toklist[self.tokind+1:]):
                    if tok.type == 'NIL':
                        break
                    elif tok.type == 'DELIM':
                        if tok.content == od:
                            lev += 1
                        elif tok.content == cd:
                            if lev == 0:
                                tok = self._new_node(type='TEXT',
                                                     content=tok.content)
                                self.toklist[self.tokind+1+i] = tok
                            lev -= 1
                            break
            self.dprint(80, "END DELIMITER RECOVERY: %s", tok)

        self.dprint(80, "LEAVE parse_inline_delim=%s", x)
        return x

    def parse_tag(self, tag):
        """Parse an xml-like tag (such as, e.g. "<tt>...</tt>")."""
        self.dprint(80, "ENTER parse_tag")
        list = []
        self.push_mark()
        while True:
            tok = self.getkn()
            if tok.type == 'NIL':
                self.pop_mark()
                s = '<' + tag.tag
                if tag.args:
                    s += ' ' + str(tag.args)
                s += '>'
                node = self._new_node(type='TEXT', content=s)
                if tag.content:
                    self.tree[self.tokind:self.tokind] = tag.content
                self.dprint(80, "LEAVE parse_tag = %s (tree modified)", node)
                return node
            elif tok.type == 'DELIM':
                if tok.isblock:
                    tok = self.parse_block_delim(tok)
                else:
                    tok = self.parse_inline_delim(tok)
                if not tok:
                    tok = self.getkn()
            elif tok.type == 'CTAG':
                if tag.tag == tok.tag:
                    break
                s = '</' + tag.tag + '>'
                tok = self.fixuptkn(self._new_node(type='TEXT', content=s))
            elif tok.type == 'NL':
                tok = self._new_node(type = 'TEXT', content = '\n')
            list.append(tok)
        self.clear_mark()
        ret = self._new_node(type = 'TAG',
                             tag  = tag.tag,
                             args = tag.args,
                             isblock = tag.isblock,
                             content = self._new_node(type = 'SEQ',
                                                      content = list))
        self.dprint(80, "LEAVE parse_tag = %s", ret)
        return ret

    def parse_env(self, tok):
        """Parse a block environment (numbered, unnumbered, or definition list)."""
        type = self.envtypes[tok.content[0]][0]
        lev = len(tok.content)
        self.dprint(80, "ENTER parse_env(%s,%s)", type, lev)
        list = []
        while True:
            if (tok.type == 'DELIM'
                and tok.content[0] in self.envtypes
                and type == self.envtypes[tok.content[0]][0]):
                if len(tok.content) < lev:
                    self.ungetkn()
                    break
                elif len(tok.content) > lev:
                    elt = self.parse_env(tok)
                else:
                    elt = self.parse_line()
                    if not tok.continuation:
                        list.append(self._new_node(type='ELT',
                                        subtype=self.envtypes[tok.content[0]][1],
                                        content=elt))
                        tok = self.getkn()
                        continue

                if list:
                    if list[-1].content.type != 'SEQ':
                        x = list[-1].content.content
                        # FIXME:
                        list[-1].content = self._new_node(type='SEQ', content=[x])
                    list[-1].content.content.append(elt)
            else:
                self.ungetkn()
                break

            tok = self.getkn()
        ret = self._new_node(type='ENV',
                             envtype=type,
                             level=lev,
                             content=list)
        self.dprint(80, "LEAVE parse_env=%s", ret)
        return ret

    def parse_header(self, tok):
        """Parse a Wiki header."""
        self.dprint(80, "ENTER parse_header")
        self.push_mark()
        list = []
        delim = tok.content
        while True:
            tok = self.getkn()
            if tok.type == 'NL':
                self.pop_mark()
                self.dprint(80, "LEAVE parse_header=None")
                return None
            elif tok.type == 'TEXT':
                list.append(tok)
            elif tok.type == 'DELIM':
                if tok.content == delim:
                    if self.lookahead().type == 'NL':
                        self.getkn()
                        if self.lookahead().type == 'NL':
                            self.getkn()
                        break
                    else:
                        self.pop_mark()
                        self.dprint(80, "LEAVE parse_header=None")
                        return None
                elif tok.isblock:
                    self.pop_mark()
                    self.dprint(80, "LEAVE parse_header=None")
                    return None
                else:
                    list.append(self.parse_inline_delim(tok))
            elif tok.type == 'OTAG':
                if tok.isblock:
                    self.pop_mark()
                    self.dprint(80, "LEAVE parse_header=None")
                    return None
                list.append(self.parse_tag(tok))
        self.clear_mark()
        ret = self._new_node(type='HDR',
                             level=len(delim),
                             content=self._new_node(type='SEQ', content=list))
        self.dprint(80, "LEAVE parse_header=%s", ret)
        return ret

    def parse_block(self):
        """Parse next block: newline, delimiter, tag, or paragraph."""
        tok = self.getkn()
        while tok.type == 'NL':
            tok = self.getkn()
        if tok == None or tok.type == 'NIL':
            return None
        elif tok.type == 'DELIM':
            tok = self.parse_block_delim(tok)
            if tok:
                return tok
            else:
                tok = self.getkn()
        elif tok.type == 'OTAG' and tok.isblock:
            return self.parse_tag(tok)

        return self.parse_para(tok)

    def parse(self):
        """Parse Wiki material supplied by the input() method.

        Store the resulting abstract parsing tree in the tree attribute.
        """
        if not self.toklist:
            self.tokenize()
        if self.debug_level >= 90:
            print("TOKEN DUMP BEGIN")
            self.dump(self.toklist)
            print("TOKEN DUMP END")
        self.tokind = 0
        self.tree = []
        while 1:
            subtree = self.parse_block()
            if subtree == None:
                break
            self.tree.append(subtree)
        if self.debug_level >= 70:
            print("TREE DUMP BEGIN")
            self.dump(self.tree)
            print("TREE DUMP END")

    def __str__(self):
        return str(self.tree)


class WikiMarkup(WikiMarkupParser):
    """
    A derived parser class that supplies a basic input method.

    Three types of inputs are available:

    1. filename=<file>
    The file <file> is opened and used for input.
    2. file=<file>
    The already opened file <file> is used for input.
    3. text=<string>
    Input is taken from <string>, line by line.

    Usage:

    obj = WikiMarkup(arg=val)
    obj.parse
    ... Do whatever you need with obj.tree ...

    """

    file = None
    text = None
    lang = 'en'
    html_base = 'http://%(lang)s.wikipedia.org/wiki/'
    image_base = 'http://upload.wikimedia.org/wikipedia/commons/thumb/a/bf'
    media_base = 'http://www.mediawiki.org/xml/export-0.3'

    def __init__(self, *args, **keywords):
        """Create a WikiMarkup object.

        Arguments:

        filename=FILE
          Read Wiki material from the file named FILE.
        file=FD
          Read Wiki material from file object FD.
        text=STRING
          Read Wiki material from STRING.
        lang=CODE
          Specifies source language. Default is 'en'. This variable can be
          referred to as '%(lang)s' in the keyword arguments below.
        html_base=URL
          Base URL for cross-references. Default is
              'http://%(lang)s.wikipedia.org/wiki/'
        image_base=URL
          Base URL for images. Default is
              'http://upload.wikimedia.org/wikipedia/commons/thumb/a/bf'
        media_base=URL
          Base URL for media files. Default is
              'http://www.mediawiki.org/xml/export-0.3'

        debug_level=INT
          debug verbosity level (0 - no debug info, 100 - excessively
                                 copious debug messages). Default is 0.
        strict=BOOL
          Strict parsing mode. Throw exceptions on syntax errors. Default
          is False.
        """
        self.token_class = {
            'NIL':   WikiNode,
            'NL':    WikiNode,
            'OTAG':  WikiTagNode,
            'CTAG':  WikiTagNode,
            'TAG':   WikiTagNode,
            'DELIM': WikiDelimNode,
            'TEXT':  WikiTextNode,
            'PRE':   WikiContentNode,
            'PARA':  WikiSeqNode,
            'BAR':   WikiNode,
            'SEQ':   WikiSeqNode,
            'IND':   WikiIndNode,
            'REF':   WikiRefNode,
            'TMPL':  WikiSeqNode,
            'IT':    WikiSeqNode,
            'BOLD':  WikiSeqNode,
            'ELT':   WikiEltNode,
            'ENV':   WikiEnvNode,
            'LINK':  WikiSeqNode,
            'HDR':   WikiHdrNode
        }

        for kw in keywords:
            if kw == 'file':
                self.file = keywords[kw]
            elif kw == 'filename':
                self.file = open(keywords[kw])
            elif kw == 'text':
                if sys.version_info[0] > 2:
                    self.text = keywords[kw].decode('utf-8').split("\n")
                else:
                    self.text = keywords[kw].split("\n")
            elif kw == 'lang':
                self.lang = keywords[kw]
            elif kw == 'html_base':
                self.html_base = keywords[kw]
            elif kw == 'image_base':
                self.image_base = keywords[kw]
            elif kw == 'media_base':
                self.media_base = keywords[kw]
            elif kw == 'strict':
                self.strict = keywords[kw]
            elif kw == 'debug_level':
                self.debug_level = keywords[kw]

    def __del__(self):
        if self.file:
            self.file.close()

    def input(self):
        if self.file:
            return self.file.readline()
        elif self.text:
            return self.text.pop(0) + '\n'
        else:
            return None

    # ISO 639
    langtab = {
        "aa": "Afar",            # Afar
        "ab": "Аҧсуа",           # Abkhazian
        "ae": None,              # Avestan
        "af": "Afrikaans",       # Afrikaans
        "ak": "Akana",           # Akan
        "als": "Alemannisch",
        "am": "አማርኛ",            # Amharic
        "an": "Aragonés",        # Aragonese
        "ang": "Englisc",
        "ar": "العربية" ,        # Arabic
        "arc": "ܐܪܡܝܐ",
        "as": "অসমীয়া",         # Assamese
        "ast": "Asturian",
        "av": "Авар",            # Avaric
        "ay": "Aymara",           # Aymara
        "az": "Azərbaycan" ,     # Azerbaijani

        "ba": "Башҡорт",         # Bashkir
        "bar": "Boarisch",
        "bat-smg": "Žemaitėška",
        "bcl": "Bikol",
        "be": "Беларуская",      # Byelorussian; Belarusian
        "be-x-old": "Беларуская (тарашкевіца)",
        "bg": "Български",       # Bulgarian
        "bh": "भोजपुरी",  # Bihari
        "bi": "Bislama",         # Bislama
        "bm": "Bamanankan",      # Bambara
        "bn": "বাংলা" ,          # Bengali; Bangla
        "bo": "བོད་སྐད",         # Tibetan
        "bpy": "ইমার ঠার/বিষ্ণুপ্রিয়া মণিপুরী" ,
        "br": "Brezhoneg" ,      # Breton
        "bs": "Bosanski" ,       # Bosnian
        "bug": "Basa Ugi",
        "bxr": "Буряад",

        "ca": "Català" ,         # Catalan
        "cbk-zam": "Chavacano de Zamboanga",
        "cdo": "Mìng-dĕ̤ng-ngṳ̄",
        "cho": "Choctaw",
        "ce": "Нохчийн",         # Chechen
        "ceb": "Sinugboanong Binisaya" , # Cebuano
        "ch": "Chamor",          # Chamorro
        "chr": "ᏣᎳᎩ",
        "chy": "Tsetsêhestâhese",
        "co": "Cors",            # Corsican
        "cr": "Nehiyaw",         # Cree
        "crh": "Qırımtatarca",
        "cs": "Česky" ,          # Czech
        "csb": "Kaszëbsczi",
        "c": "Словѣньскъ",       # Church Slavic
        "cv": "Чăваш",           # Chuvash
        "cy": "Cymraeg" ,        # Welsh

        "da": "Dansk" ,          # Danish
        "de": "Deutsch" ,        # German
        "diq": "Zazaki",         # Dimli (Southern Zazaki)
        "dsb": "Dolnoserbski",
        "dv": "ދިވެހިބަސް",      # Divehi
        "dz": "ཇོང་ཁ",           # Dzongkha; Bhutani

        "ee": "Eʋegbe",          # Ewe
        "el": "Ελληνικά" ,       # Greek
        "eml": "Emiliàn e rumagnòl",
        "en": "English" ,        # English
        "eo": "Esperanto" ,
        "es": "Español" ,        # Spanish
        "et": "Eesti" ,          # Estonian
        "eu": "Euskara" ,         # Basque
        "ext": "Estremeñ",

        "fa": "فارسی" ,          # Persian
        "ff": "Fulfulde",        # Fulah
        "fi": "Suomi" ,          # Finnish
        "fiu-vro": "Võro",
        "fj": "Na Vosa Vakaviti",# Fijian; Fiji
        "fo": "Føroyskt" ,       # Faroese
        "fr": "Français" ,       # French
        "frp": "Arpitan",
        "fur": "Furlan",
        "fy": "Frysk",           # Frisian

        "ga": "Gaeilge",         # Irish
        "gan": "贛語 (Gànyŭ)",
        "gd": "Gàidhlig",        # Scots; Gaelic
        "gl": "Gallego" ,        # Gallegan; Galician
        "glk": "گیلکی",
        "got": "𐌲𐌿𐍄𐌹𐍃𐌺𐍉𐍂𐌰𐌶𐌳𐌰",
        "gn": "Avañe'ẽ",         # Guarani
        "g": "ગુજરાતી",          # Gujarati
        "gv": "Gaelg",           # Manx

        "ha": "هَوُسَ",          # Hausa
        "hak": "Hak-kâ-fa / 客家話",
        "haw": "Hawai`i",
        "he": "עברית" ,          # Hebrew (formerly iw)
        "hi": "हिन्दी" ,   # Hindi
        "hif": "Fiji Hindi",
        "ho": "Hiri Mot",        # Hiri Motu
        "hr": "Hrvatski" ,       # Croatian
        "hsb": "Hornjoserbsce",
        "ht": "Krèyol ayisyen" , # Haitian; Haitian Creole
        "hu": "Magyar" ,         # Hungarian
        "hy": "Հայերեն",         # Armenian
        "hz": "Otsiherero",      # Herero

        "ia": "Interlingua",
        "ie": "Interlingue",
        "id": "Bahasa Indonesia",# Indonesian (formerly in)
        "ig": "Igbo",            # Igbo
        "ii": "ꆇꉙ     ",       # Sichuan Yi
        "ik": "Iñupiak",         # Inupiak
        "ilo": "Ilokano",
        "io": "Ido" ,
        "is": "Íslenska" ,       # Icelandic
        "it": "Italiano" ,       # Italian
        "i": "ᐃᓄᒃᑎᑐᑦ",           # Inuktitut

        "ja": "日本語",          # Japanese
        "jbo": "Lojban",
        "jv": "Basa Jawa",       # Javanese

        "ka": "ქართული" ,        # Georgian
        "kaa": "Qaraqalpaqsha",
        "kab": "Taqbaylit",
        "kg": "KiKongo",         # Kongo
        "ki": "Gĩkũyũ",          # Kikuyu
        "kj": "Kuanyama",        # Kuanyama
        "kk": "Қазақша",         # Kazakh
        "kl": "Kalaallisut",     # Kalaallisut; Greenlandic
        "km": "ភាសាខ្មែរ",       # Khmer; Cambodian
        "kn": "ಕನ್ನಡ",           # Kannada
        "ko": "한국어" ,         # Korean
        "kr": "Kanuri",          # Kanuri
        "ks": "कश्मीरी / كشميري", # Kashmiri
        "ksh": "Ripoarisch",
        "ku": "Kurdî / كوردی",   # Kurdish
        "kv": "Коми",            # Komi
        "kw": "Kernewek/Karnuack", # Cornish
        "ky": "Кыргызча",        # Kirghiz

        "la": "Latina" ,         # Latin
        "lad": "Dzhudezmo",
        "lb": "Lëtzebuergesch" , # Letzeburgesch
        "lbe": "Лакку",
        "lg": "Luganda",         # Ganda
        "li": "Limburgs",        # Limburgish; Limburger; Limburgan
        "lij": "Lígur",
        "ln": "Lingala",         # Lingala
        "lmo": "Lumbaart",
        "lo": "ລາວ",             # Lao; Laotian
        "lt": "Lietuvių" ,       # Lithuanian
        "lua": "Luba",           # Luba
        "lv": "Latvieš" ,        # Latvian; Lettish

        "map-bms": "Basa Banyumasan",
        "mdf": "Мокшень (Mokshanj Kälj)",
        "mg": "Malagasy",        # Malagasy
        "mh": "Ebon",            # Marshall
        "mi": "Māori",           # Maori
        "mk": "Македонски" ,     # Macedonian
        "ml": None,              # Malayalam
        "mn": "Монгол",          # Mongolian
        "mo": "Молдовеняскэ",    # Moldavian
        "mr": "मराठी" ,     # Marathi
        "ms": "Bahasa Melay" ,   # Malay
        "mt": "Malti",           # Maltese
        "mus": "Muskogee",
        "my": "မ္ရန္‌မာစာ",      # Burmese
        "myv": "Эрзянь (Erzjanj Kelj)",
        "mzn": "مَزِروني",

        "na": "dorerin Naoero",  # Nauru
        "nah": "Nāhuatl",
        "nap": "Nnapulitano",
        "nb": "Norsk (Bokmål)",  # Norwegian Bokm@aa{}l
        "nd": None,              # Ndebele, North
        "nds": "Plattdüütsch",
        "nds-nl": "Nedersaksisch",
        "ne": "नेपाली",    # Nepali
        "new": "नेपाल भाषा" , # Nepal Bhasa
        "ng": "Oshiwambo",       # Ndonga
        "nl": "Nederlands" ,     # Dutch
        "nn": "Nynorsk",         # Norwegian Nynorsk
        "no": "Norsk (Bokmål)" , # Norwegian
        "nov": "Novial",
        "nr": None,              # Ndebele, South
        "nrm": "Nouormand/Normaund",
        "nv": "Diné bizaad",     # Navajo
        "ny": "Chi-Chewa",       # Chichewa; Nyanja

        "oc": "Occitan",         # Occitan; Proven@,{c}al
        "oj": None,              # Ojibwa
        "om": "Oromoo",          # (Afan) Oromo
        "or": "ଓଡ଼ିଆ",           # Oriya
        "os": "Иронау",          # Ossetian; Ossetic

        "pa": "ਪੰਜਾਬੀ" ,         # Panjabi; Punjabi
        "pag": "Pangasinan",
        "pam": "Kapampangan",
        "pap": "Papiament",
        "pdc": "Deitsch",
        "pi": "पाऴि",        # Pali
        "pih": "Norfuk",
        "pl": "Polski" ,         # Polish
        "pms": "Piemontèis" ,
        "ps": "پښتو",            # Pashto, Pushto
        "pt": "Português" ,      # Portuguese

        "q": "Runa Simi" ,       # Quechua

        "rm": "Rumantsch",       # Rhaeto-Romance
        "rmy": "romani - रोमानी",
        "rn": "Kirundi",         # Rundi; Kirundi
        "ro": "Română" ,         # Romanian
        "roa-rup": "Armãneashce",
        "roa-tara": "Tarandíne",
        "ru": "Русский" ,        # Russian
        "rw": "Ikinyarwanda",    # Kinyarwanda

        "sa": "संस्कृतम्", # Sanskrit
        "sah": "Саха тыла (Saxa Tyla)",
        "sc": "Sardu",           # Sardinian
        "scn": "Sicilian",
        "sco": "Scots",
        "sd": "سنڌي، سندھی ، सिन्ध", # Sindhi
        "se": "Sámegiella",      # Northern Sami
        "sg": "Sängö",           # Sango; Sangro
        "sh": "Srpskohrvatski / Српскохрватски" ,
        "si": "සිංහල",
        "simple": "Simple English" ,
        "sk": "Slovenčina" ,     # Slovak
        "sl": "Slovenščina" ,    # Slovenian
        "sm": "Gagana Samoa",    # Samoan
        "sn": "chiShona",        # Shona
        "so": "Soomaaliga",      # Somali
        "sr": "Српски / Srpski", # Serbian
        "srn": "Sranantongo",
        "ss": "SiSwati",         # Swati; Siswati
        "st": "Sesotho",         # Sesotho; Sotho, Southern
        "stk": "Seeltersk",
        "s": "Basa Sunda",       # Sundanese
        "sq": "Shqip" ,          # Albanian
        "szl": "Ślůnski",
        "sv": "Svenska" ,        # Swedish
        "sw": "Kiswahili",       # Swahili

        "ta": "தமிழ்" ,          # Tamil
        "te": "తెలుగు" ,         # Telugu
        "tet": "Tetun",
        "tg": "Тоҷикӣ",          # Tajik
        "th": "ไทย" ,            # Thai
        "ti": "ትግርኛ",            # Tigrinya
        "tk": "تركمن / Туркмен", # Turkmen
        "tl": "Tagalog" ,        # Tagalog
        "tn": "Setswana",        # Tswana; Setswana
        "to": "faka Tonga",      # Tonga (?) # Also ZW ; MW
        "tokipona": "Tokipona",
        "tpi": "Tok Pisin",
        "tr": "Türkçe" ,         # Turkish
        "ts": "Xitsonga",        # Tsonga
        "tt": "Tatarça / Татарча", # Tatar
        "tum": "chiTumbuka",
        "tw": "Twi",             # Twi
        "ty": "Reo Mā`ohi",      # Tahitian

        "udm": "Удмурт кыл",
        "ug": "Oyghurque",       # Uighur
        "uk": "Українська" ,     # Ukrainian
        "ur": "اردو",            # Urdu
        "uz": "O‘zbek",          # Uzbek

        "ve": "Tshivenda",       # Venda
        "vec": "Vèneto",
        "vi": "Tiếng Việt" ,     # Vietnamese
        "vls": "West-Vlams",
        "vo": "Volapük" ,

        "wa": "Walon",           # Walloon
        "war": "Winaray",
        "wo": "Wolof",           # Wolof
        "w": "吴语",

        "xal": "Хальмг",
        "xh": "isiXhosa",        # Xhosa

        "yi": "ייִדיש",          # Yiddish
        "yo": "Yorùbá",          # Yoruba

        "za": "Cuengh",          # Zhuang
        "zea": "Zeêuws",
        "zh": "中文" ,           # Chinese
        "zh-classical": "古文 / 文言文",
        "zm-min-nan": "Bân-lâm-gú",
        "zh-yue": "粵語",
        "zu": "isiZulu"          # Zulu
    }
