#!/usr/bin/env python

#
# Custom Exception class for errors connected to plots/stats types
#
class PlotTypeError(Exception):
    pass


#
# Base class for types of plots/stats
#
class PlotType(object):
    #
    # Constructor
    #
    def __init__(self):
        self.name     = None # name of the type of plots/stats
        self.notation = None # curve's label prefix notation
        pass


    #
    # Method generates curves: flows merged into each curve and name of each curve.
    # param [in] layout - layout of flows
    # param [in] flows  - flows to divide into curves
    # returns curves
    #
    def get_curves(self, layout, flows):
        raise NotImplementedError


    #
    # Method returns prefix for names of plots and stats of the type.
    # returns filename prefix
    #
    def get_filename_prefix(self):
        return self.name


    #
    # Method returns the prefix of the label notation of curves in plots of the type.
    # returns prefix of the label notation
    #
    def get_label_notation_prefix(self):
        return self.notation
