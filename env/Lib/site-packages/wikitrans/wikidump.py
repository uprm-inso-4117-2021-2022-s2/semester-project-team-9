# Wiki "dump" format. -*- coding: utf-8 -*-
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
Print Wiki parse tree as JSON.

Classes:

DumpWikiMarkup

"""

from __future__ import print_function
from wikitrans.wikitoken import *
import json
from wikitrans.wikimarkup import WikiMarkup


class DumpReferences(object):
    idx = 0
    def __len__(self):
        return self.idx + 1
    def append(self, obj):
        self.idx += 1

class DumpWikiMarkup(WikiMarkup):
    """Produce a JSON dump of the Wiki markup parse tree.

    Usage:

      x = DumpWikiMarkup(file="input.wiki")
      # Parse the input:
      x.parse()
      # Print a JSON dump of the parse tree
      print(str(x))

    """

    indent = None
    references = DumpReferences()

    def __init__(self, **kwarg):
        """Create a DumpWikiMarkup object.

        Arguments:

        filename=FILE
          Read Wiki material from the file named FILE.
        file=FD
          Read Wiki material from file object FD.
        text=STRING
          Read Wiki material from STRING.
        indent=N
          Basic indent offset for JSON objects.
        """
        n = kwarg.pop('indent', None)
        if n != None:
            self.indent = int(n)
        super(DumpWikiMarkup, self).__init__(self, **kwarg)

    def __str__(self):
        return json.dumps(self.tree,
                          cls=WikiNodeEncoder,
                          indent=self.indent,
                          separators=(',', ': '),
                          sort_keys=True)
