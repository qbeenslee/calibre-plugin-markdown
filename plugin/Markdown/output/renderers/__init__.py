# -*- coding: utf-8 -*-
"""XHTML -> Markdown renderer mixins, one module per rendering domain.

The class itself lives in ..markdownml_enhanced; each module here holds
the methods of one domain and is mixed into it. Cross-domain calls go
through self., so these modules never import each other - only
.primitives (shared constants and free functions) and ..utils.helpers.
"""

__license__ = 'GPL 3'
