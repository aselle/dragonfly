#
# This file is part of Dragonfly.
# (c) Copyright 2007, 2008 by Christo Butcher
# Licensed under the LGPL.
#
#   Dragonfly is free software: you can redistribute it and/or modify it 
#   under the terms of the GNU Lesser General Public License as published 
#   by the Free Software Foundation, either version 3 of the License, or 
#   (at your option) any later version.
#
#   Dragonfly is distributed in the hope that it will be useful, but 
#   WITHOUT ANY WARRANTY; without even the implied warranty of 
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public 
#   License along with Dragonfly.  If not, see 
#   <http://www.gnu.org/licenses/>.
#

"""
Dictation formatting for Natlink
============================================================================

This module implements dictation formatting for the Natlink and Dragon
NaturallySpeaking engine.

"""


# Attempt to import Natlink.  If this fails, Natlink is probably
#  not available and the dictation container implemented here
#  cannot be used.  However, we don't raise an exception because
#  this file should still be importable for documentation purposes.
try:
    import natlink
except ImportError:
    natlink = None

import logging


#===========================================================================

class FlagContainer(object):
    """ Container for a predefined set of boolean flags. """

    flag_names = ()

    def __init__(self, *names):
        self._flags_true = set()
        for name in names:
            setattr(self, name, True)

    def __unicode__(self):
        flags_true_names = []
        for flag in self.flag_names:
            if flag in self._flags_true:
                flags_true_names.append(flag)
        return u", ".join(flags_true_names)

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __getattr__(self, name):
        if name not in self.flag_names:
            raise AttributeError("Invalid flag name: %r" % (name,))
        return (name in self._flags_true)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            return object.__setattr__(self, name, value)
        if name not in self.flag_names:
            raise AttributeError("Invalid flag name: received %r, expected"
                                 " one of %r" % (name, self.flag_names))
        if value:
            self._flags_true.add(name)
        else:
            self._flags_true.discard(name)

    def clone(self):
        clone = self.__class__()
        for name in self._flags_true:
            setattr(clone, name, True)
        return clone


#---------------------------------------------------------------------------

class WordFlags(FlagContainer):
    """
        Container for formatting flags associated with DNS words.

        The flags defined by this class are closely related to the
        formatting information provided by DNS.

    """

    flag_names = (
        # Flags related to spacing
        "no_space_before",     # No space before this word (like right-paren)
        "no_space_after",      # No space after this word (like left-paren)
        "two_spaces_after",    # Two spaces after this word (like full-stop)
        "no_space_mode",       # Activate no-spacing mode (like No-Space-On)
        "reset_no_space",      # Reset spacing mode (like No-Space-Off)
        "no_space_reset",      # Don't reset spacing state (like Cap)
        "spacebar",            # Extra space after this word (like spacebar)
        "no_space_between",    # No spaces between adjacent words with this flag (like numbers)

        # Flags related to newlines
        "newline_after",       # One newline after this word (like New-Line)
        "two_newlines_after",  # Two newlines after this word (like New-Paragraph)

        # Flags related to capitalization
        "cap_next",            # Normally capitalize next word (eg full-stop)
        "cap_next_force",      # Always capitalize next word (eg Cap-Next)
        "lower_next",          # Lowercase next word (eg No-Caps-Next)
        "upper_next",          # Uppercase next word (eg All-Caps-Next)
        "cap_mode",            # Activate capitalization mode (like Caps-On)
        "lower_mode",          # Activate lowercase mode (like No-Caps-On)
        "upper_mode",          # Activate uppercase mode (like All-Caps-On)
        "reset_cap",           # Reset capitalization mode (like Caps-Off)
        "no_cap_reset",        # Don't reset the capitalization state (like left-paren)
        "no_title_cap",        # Don't capitalize in title (like and)

        # Miscellaneous flags
        "no_format",           # Don't apply formatting (like Cap)
        "not_after_period",    # Suppress this word after a word ending in period (like full-stop after etc.)
    )


#---------------------------------------------------------------------------

class StateFlags(FlagContainer):
    """
        Container for keeping state for inter-word formatting.

        The flags defined by this class are used by Dragonfly to store
        formatting state between words as a formatter consumes
        consecutive words.

    """

    flag_names = (
        # Flags related to spacing
        "no_space_before",       # No space before next word
        "two_spaces_before",     # Two spaces before next word
        "no_space_mode",         # No-spacing mode is active
        "no_space_between",      # No space before next word if it has no_space_between flag

        # Flags related to capitalization
        "cap_next",              # Normally capitalize next word
        "cap_next_force",        # Always capitalize next word
        "lower_next",            # Lowercase next word
        "upper_next",            # Uppercase next word
        "cap_mode",              # Capitalization mode is active
        "lower_mode",            # Lowercase mode is active
        "upper_mode",            # Uppercase mode is active

        # Miscellaneous flags
        "prev_ended_in_period",  # Previous word ended in period
    )


#===========================================================================

class Word(object):
    """ Word storing written and spoken forms with formatting flags. """

    def __init__(self, written, spoken, flags):
        self.written = written
        self.spoken = spoken
        self.flags = flags

    def __unicode__(self):
        info = [repr(self.written)]
        if self.spoken and self.spoken != self.written:
            info.append(repr(self.spoken))
        flags_string = unicode(self.flags)
        if flags_string:
            info.append(flags_string)
        return u"%s(%s)" % (self.__class__.__name__, ", ".join(info))

    def __str__(self):
        return unicode(self).encode("utf-8")


#===========================================================================

class WordParserBase(object):
    """ Base class for parsing dictation results into Word objects. """

    _log = logging.getLogger("dictation.word_parser")

    def parse_word(self, input):
        raise NotImplementedError


#---------------------------------------------------------------------------

class WordParserDns10(WordParserBase):
    """
        Dictation results parser for DNS v10 and lower.

        DNS v10 and lower provide word formatting information as a 32-bit
        value returned by `natlink.getWordInfo()`.

    """

    flags = [
        (0x00000001, None),  # Added by user
        (0x00000002, None),  # Internal use
        (0x00000004, None),  # Internal usu
        (0x00000008, None),  # Undeletable
        (0x00000010, "cap_next"),
        (0x00000020, "cap_next_force"),
        (0x00000040, "upper_next"),
        (0x00000080, "lower_next"),
        (0x00000100, "no_space_after"),
        (0x00000200, "two_spaces_after"),
        (0x00000400, "no_space_between"),
        (0x00000800, "cap_mode"),
        (0x00001000, "upper_mode"),
        (0x00002000, "lower_mode"),
        (0x00004000, "no_space_mode"),
        (0x00008000, "reset_no_space"),
        (0x00010000, None),  # Internal use
        (0x00020000, "not_after_period"),
        (0x00040000, "no_format"),
        (0x00080000, "no_space_reset"),
        (0x00100000, "no_cap_reset"),
        (0x00200000, "no_space_before"),
        (0x00400000, "reset_cap"),
        (0x00800000, "newline_after"),
        (0x01000000, "two_newlines_after"),
        (0x02000000, "no_title_cap"),
        (0x04000000, None),  # Internal use
        (0x08000000, "spacebar"),
        (0x10000000, None),  # Internal use
        (0x20000000, None),  # Internal use
        (0x40000000, None),  # Added by vocabulary builder
        (0x80000000, None),
    ]

    def create_word_flags(self, info):
        if info == None:
            # None indicates the word is not in DNS' vocabulary.
            return WordFlags()

        flag_names = []
        for bit, name in self.flags:
            if (info & bit) != 0:
                if name:
                    flag_names.append(name)
        return WordFlags(*flag_names)

    def parse_input(self, input):
        if isinstance(input, str):
            # DNS and Natlink provide recognized words as "Windows-1252"
            # encoded strings. Here we convert them to Unicode for internal
            # processing.
            input = unicode(input, "windows-1252")

        # The written and spoken forms of a word are separated by a "\"
        # character.
        index = input.find("\\")
        if index == -1:
            # Input doesn't contain a backslash, so written and spoken forms
            # are the same as the input.
            written = input
            spoken = input
        else:
            # Input contains one or more backslashes, so written and spoken
            # forms are separated by the first backslash.
            written = input[:index]
            spoken = input[index+1:]

        info = natlink.getWordInfo(input.encode("windows-1252"))
        word_flags = self.create_word_flags(info)

        word = Word(written, spoken, word_flags)
        self._log.debug("Parsed input {0!r} -> {1}".format(input, word))
#        print ("Parsed input {0!r} -> {1}".format(input, word))
        return word


#===========================================================================

class WordFlagFactory(object):

    _log = logging.getLogger("dictation.format")

    property_map = {
        "space-bar":        WordFlags("spacebar", "no_space_after",
                                      "no_format", "no_cap_reset",
                                      "no_space_before"),
        "period":           WordFlags("two_spaces_after", "cap_next",
                                      "no_space_before"),
        "question-mark":    WordFlags("two_spaces_after", "cap_next",
                                      "no_space_before"),
        "exclamation-mark": WordFlags("two_spaces_after", "cap_next",
                                      "no_space_before"),
        "point":            WordFlags("no_space_after", "no_space_between",
                                      "no_space_before"),
        "dot":              WordFlags("no_space_after", "no_space_between",
                                      "no_space_before"),
        "comma":            WordFlags("no_space_before"),
        "hyphen":           WordFlags("no_space_before", "no_space_after"),
        "at-sign":          WordFlags("no_space_before", "no_space_after"),
        "colon":            WordFlags("no_space_before"),
        "semicolon":        WordFlags("no_space_before"),
        "apostrophe-ess":   WordFlags("no_space_before"),
        "left-*":           WordFlags("no_cap_reset", "no_space_after"),
        "right-*":          WordFlags("no_cap_reset", "no_space_before",
                                      "no_space_reset"),
        "new-line":         WordFlags("no_format", "no_space_after",
                                      "no_cap_reset", "newline_after"),
        "new-paragraph":    WordFlags("no_format", "no_space_after",
                                      "cap_next", "two_newlines_after"),
        "spelling-cap":     WordFlags("no_format", "no_space_reset", "cap_next_force"),
        "letter":           WordFlags("no_space_after"),
        "uppercase-letter": WordFlags("no_space_after"),
        "cap":              WordFlags("no_format", "no_space_reset",
                                      "cap_next_force"),
        "caps-on":          WordFlags("no_format", "no_space_reset",
                                      "cap_mode"),
        "caps-off":         WordFlags("no_format", "no_space_reset",
                                      "reset_cap"),
        "all-caps":         WordFlags("no_format", "no_space_reset",
                                      "upper_next"),
        "all-caps-on":      WordFlags("no_format", "no_space_reset",
                                      "upper_mode"),
        "all-caps-off":     WordFlags("no_format", "no_space_reset",
                                      "reset_cap"),
        "no-caps":          WordFlags("no_format", "no_space_reset",
                                      "lower_next"),
        "no-caps-on":       WordFlags("no_format", "no_space_reset",
                                      "lower_mode"),
        "no-caps-off":      WordFlags("no_format", "no_space_reset",
                                      "reset_cap"),
        "no-space":         WordFlags("no_format", "no_cap_reset",
                                      "no_space_after"),
        "no-space-on":      WordFlags("no_format", "no_cap_reset",
                                      "no_space_mode"),
        "no-space-off":     WordFlags("no_format", "no_cap_reset",
                                      "reset_no_space"),
    }

    def get_word_flags(self, word):
        parts = word.split("\\")
        if len(parts) != 3:
            # Word doesn't have "written\property\spoken" form, so
            # return empty flags.
            return WordFlags()

        written, property, spoken = parts
        if property in self.property_map:
            flags = self.property_map[property].clone()
        else:
            self._log.warning("Unknown word property: %r" % (word,))
            flags = WordFlags()
        return (written, spoken, flags)


#===========================================================================

class WordFormatter(object):

    _log = logging.getLogger("dictation.format")

    def __init__(self, state=None, two_spaces_after_period=False):
        if state:  self.state = state
        else:      self.state = StateFlags("no_space_before")
        self.two_spaces_after_period = two_spaces_after_period
        self.parser = WordParserDns10()

    def format_input(self, input_words):
        formatted_words = []
        for input_word in input_words:
            word = self.parser.parse_input(input_word)
            formatted_words.append(self.apply_formatting(word))
            self.update_state(word)
        return "".join(formatted_words)

    def apply_formatting(self, word):
        state = self.state

        # Determine prefix.
        if   word.flags.no_format:         prefix = ""
        elif word.flags.no_space_before:   prefix = ""
        elif state.no_space_before:        prefix = ""
        elif state.no_space_mode:          prefix = ""
        elif state.no_space_between and word.flags.no_space_between: prefix = ""
        elif state.two_spaces_before:      prefix = "  " if self.two_spaces_after_period else " "
        else:                              prefix = " "

        # Determine formatted written form.
        if   word.flags.no_format:         written = word.written
        elif state.cap_next:               written = word.written.capitalize()
        elif state.cap_next_force:         written = word.written.capitalize()
        elif state.upper_mode:             written = word.written.upper()
        elif state.lower_mode:             written = word.written.lower()
        elif state.upper_next:             written = word.written.upper()
        elif state.lower_next:             written = word.written.lower()
        elif state.cap_mode and not word.flags.no_title_cap: written = word.written.capitalize()
        else:                              written = word.written

        # Remove first period character if needed.
        if state.prev_ended_in_period and word.flags.not_after_period and written.startswith("."):
            written = written[1:]

        # Determine suffix.
        if   word.flags.newline_after:       suffix = "\n"
        elif word.flags.two_newlines_after:  suffix = "\n\n"
        elif word.flags.spacebar:            suffix = " "
        else:                                suffix = ""

        return prefix + written + suffix

    def update_state(self, word_object):
        word = word_object.flags
        prev = self.state
        state = StateFlags()

        # Update capitalization state.
        state.cap_next_force = word.cap_next_force or (word.no_cap_reset and prev.cap_next_force)
        state.cap_next       = word.cap_next or word.cap_mode or (word.no_cap_reset and prev.cap_next)
        state.upper_next     = word.upper_next     or (word.no_cap_reset and prev.upper_next)
        state.lower_next     = word.lower_next     or (word.no_cap_reset and prev.lower_next)
        state.cap_mode       = word.cap_mode       or (prev.cap_mode   and not word.reset_cap)
        state.upper_mode     = word.upper_mode     or (prev.upper_mode and not word.reset_cap)
        state.lower_mode     = word.lower_mode     or (prev.lower_mode and not word.reset_cap)

        # Update spacing state.
        state.no_space_before   = word.no_space_after   or (prev.no_space_before and word.no_space_reset and word.no_format)
        state.two_spaces_before = word.two_spaces_after or (prev.two_spaces_before and word.no_space_reset and word.no_format)
        state.no_space_between  = word.no_space_between

        # Record whether this word ended in a period.
        state.prev_ended_in_period = word_object.written.endswith(".")

        # Replace own state with newly created state.
        self.state = state
