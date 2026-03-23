"""
text_backend.py

Text-based USDA manipulation utilities used by _text variant functions.

Currently, text manipulation utilities (regex-based prim replacement, string escaping)
are inlined in the modules that use them (question.py, transition.py, variant.py, signals.py).

This module is reserved for any shared text-backend utilities that may be extracted
in the future.
"""
