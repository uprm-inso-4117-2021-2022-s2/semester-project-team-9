# Wiki tokens. -*- coding: utf-8 -*-
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
Wiki markup tokens and associated classes.

This module defines classes for the basic nodes of the Wiki markup parse tree:

WikiNode        -- Abstract parse tree node.
WikiContentNode -- A node associated with some content.
WikiSeqNode     -- A sequence of nodes.
WikiTextNode    -- Textual content.
WikiDelimNode   -- Delimiter.
WikiTagNode     -- Tag (e.g. <tt>, </tt>, <tt />, etc.)
WikiRefNode     -- Wiki reference (e.g. [target|name])
WikiHdrNode     -- Heading (e.g. == Section ==)
WikiEltNode     -- Environment element.
WikiEnvNode     -- Environment (numbered or unnumbered list, definition, etc.)
WikiIndNode     -- Indent node.

Auxiliary classes:

WikiNodeEncoder -- Custom JSONEncoder subclass for serializing objects of the
                   above classes.
"""

from __future__ import print_function
import re
import json


class WikiNodeEncoder(json.JSONEncoder):
    """Custom JSONEncoder subclass for serializing WikiNode and its subclasses."""

    def default(self, obj):
        if isinstance(obj, WikiNode):
            return obj.json_encode()
        return json.JSONEncoder.default(self, obj)


def jsonencoder(func):
    def _mkencoder(self):
        json = func(self)
        json['wikinode'] = self.__class__.__name__
        json['type'] = self.type
        return json

    return _mkencoder


class WikiNode(object):
    """Generic parse tree node.

    Attributes:

      type   -- actual type of this object (string)
      parser -- parser instance that owns this node
    """

    type = 'UNDEF'
    parser = None

    def __init__(self, parser, **kwargs):
        self.parser = parser
        for key in kwargs:
            if hasattr(self, key):
                self.__dict__[key] = kwargs[key]
            else:
                raise AttributeError("'%s' has no attribute '%s'" % (self.__class__.__name__, key))

    def __str__(self):
        return json.dumps(self, cls=WikiNodeEncoder, sort_keys=True)

    @jsonencoder
    def json_encode(self):
        ret = {}
        for x in dir(self):
            if x == 'parser' or x.startswith('_') or type(x) == 'function':
                continue
            if x in self.__dict__:
                ret[x] = self.__dict__[x]
        return ret

    def format(self):
        """Abstract formatting function.

           Derived classes must override it.
        """
        pass


class WikiContentNode(WikiNode):
    """Generic content node.

    Attributes:

    content   --   Actual content
    """

    content = None

    def format(self):
        pass

    @jsonencoder
    def json_encode(self):
        ret = {}
        if self.content:
            if self.type == 'TEXT':
                ret['content'] = self.content
            elif isinstance(self.content, list):
                ret['content'] = [x for x in
                                  map(lambda x: x.json_encode(), self.content)]
            elif isinstance(self.content, WikiNode):
                ret['content'] = self.content.json_encode()
            else:
                ret['content'] = self.content
        else:
            ret['content'] = None
        return ret


class WikiSeqNode(WikiContentNode):
    """Generic sequence of nodes.

    Attributes:

    content  -- list of nodes.
    """

    def format(self):
        for x in self.content:
            x.format()

    @jsonencoder
    def json_encode(self):
        ret = {}
        if not self.content:
            ret['content'] = None
        elif isinstance(self.content, list):
            ret['content'] = [x for x in map(lambda x: x.json_encode(), self.content)]
        elif isinstance(self.content, WikiNode):
            ret['content'] = self.content.json_encode()
        else:
            ret['content'] = self.content
        return ret


# ##############

class WikiTextNode(WikiContentNode):
    """Text node.

    Attributes:

    type     -- 'TEXT'
    content  -- string
    """

    type = 'TEXT'

    @jsonencoder
    def json_encode(self):
        return {
            'content': self.content
        }


class WikiDelimNode(WikiContentNode):
    """Delimiter node.

    Attributes:

    type         -- 'DELIM'
    content      -- actual delimiter string
    isblock      -- boolean indicating whether it is a block delimiter
    continuation -- True if continuation is expected
    """

    type = 'DELIM'
    isblock=False
    continuation = False


class WikiTagNode(WikiContentNode):
    """A Wiki tag.

    Attributes:

    tag      -- actual tag name (with '<', '>', and eventual '/' stripped)
    isblock  -- True if this is a block tag
    args     -- List of tag arguments
    idx      -- If this is a "see also" reference, index of this ref in the
                list of references.
                FIXME: Perhaps this merits a subclass?
    """

    tag = None
    isblock = False
    args = None
    idx = None

    def __init__(self, *args, **keywords):
        super(WikiTagNode, self).__init__(*args, **keywords)
        if (self.type == 'TAG'
            and self.tag == 'ref'
            and hasattr(self.parser, 'references')):
            self.idx = len(self.parser.references)
            self.parser.references.append(self)

    @jsonencoder
    def json_encode(self):
        return {
            'tag': self.tag,
            'isblock': self.isblock,
            'args': self.args.tab if self.args else None,
            'content': self.content.json_encode() if self.content else None,
            'idx': self.idx
        }


class WikiRefNode(WikiContentNode):
    """Reference node.

    This class represents a wiki reference, such as "[ref|content]".

    Attributes:

    ref        -- actual reference
    content    -- content string
    """

    type = 'REF'
    ref = None
    @jsonencoder
    def json_encode(self):
        return {
            'ref': self.ref,
            'content': self.content.json_encode()
        }


class WikiHdrNode(WikiContentNode):
    """A wiki markup header class.

    Attributes:

    level    --  header level
    content  --  header content (WikiNode subclass object)
    """

    type = 'HDR'
    level = None

    @jsonencoder
    def json_encode(self):
        return {
            'level': self.level,
            'content': self.content.json_encode()
        }


class WikiEltNode(WikiContentNode):
    """Environment element node.

    Attributes:

    subtype    -- type of the environment (numbered, unnumbered, defn)
    content    -- content of the element (WikiNode subclass object)
    """

    type = 'ELT'
    subtype = None

    @jsonencoder
    def json_encode(self):
        return {
            'subtype': self.subtype,
            'content': self.content.json_encode()
        }


class WikiEnvNode(WikiContentNode):
    """Wiki Environment Node

    Attributes:

    envtype    -- type of the environment (numbered, unnumbered, defn)
    level      -- nesting level of the environment
    """

    type = 'ENV'
    envtype = None
    level = None

    @jsonencoder
    def json_encode(self):
        return {
            'envtype': self.envtype,
            'level': self.level,
            'content': [x for x in map(lambda x: x.json_encode(), self.content)]
        }


class WikiIndNode(WikiContentNode):
    """Indented block node.

    Attributes:

    level   -- Indentation level.
    content -- Indented content (WikiNode subclass object).
    """

    type = 'IND'
    level = None

    @jsonencoder
    def json_encode(self):
        return {
            'level': self.level,
            'content': self.content.json_encode()
        }
