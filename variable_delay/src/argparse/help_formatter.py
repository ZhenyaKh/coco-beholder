#!/usr/bin/env python

import argparse

#
# Custom HelpFormatter class for argparse.ArgumentParser
#
class BlankLinesHelpFormatter (argparse.HelpFormatter):
    #
    # Method insert blank lines between entries of the help message of the program
    # param [in] text  - text of an entry of the help message
    # param [in] width - width of the help message
    # returns array of lines of an entry of the help message ending with the blank line
    #
    def _split_lines(self, text, width):
        return super(BlankLinesHelpFormatter, self)._split_lines(text, width) + ['']
