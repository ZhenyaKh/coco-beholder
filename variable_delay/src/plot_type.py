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
        self.name = None # name of the type of plots/stats
        pass


    #
    # Method generates curves: flows merged into each curve and name of each curve.
    # param [in] metadata - metadata of flows
    # returns array of arrays of flows per curve, array of names of curves
    #
    def get_curves(self, metadata):
        raise NotImplementedError


    #
    # Method returns prefix for names of plots and stats of the type.
    # returns filename prefix
    #
    def get_filename_prefix(self):
        return self.name
