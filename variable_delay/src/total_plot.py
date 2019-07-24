#!/usr/bin/env python

from variable_delay.src.plot_type import PlotType
from variable_delay.src.metadata_fields import ALL_FLOWS

FLOW  = 'flow'
FLOWS = 'flows'


#
# Class of total plots/stats
#
class TotalPlot(PlotType):
    #
    # Constructor
    #
    def __init__(self):
        PlotType.__init__(self)
        self.name = 'total' # name of the type of plots/stats


    #
    # Method generates curves: flows merged into each curve and name of each curve.
    # param [in] metadata - metadata of flows
    # returns array of arrays of flows per curve, array of names of curves
    #
    def get_curves(self, metadata):
        flowsNumber = metadata[ALL_FLOWS]
        flowsWord   = FLOW if flowsNumber == 1 else FLOWS

        flows = [ list(range(0, flowsNumber)) ]
        names = [ 'Total: {:d} {}'.format(flowsNumber, flowsWord) ]

        return flows, names
