#!/usr/bin/env python

from variable_delay.src.plot.plot_type import PlotType
from variable_delay.src.plot.curve import Curve

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
        self.name     = 'total'                             # name of the type of plots/stats
        self.notation = 'Total: <total flows number> flows' # curve's label prefix notation


    #
    # Method generates curves: flows merged into each curve and name of each curve.
    # param [in] layout - layout of flows
    # param [in] flows  - flows to divide into curves
    # returns curves
    #
    def get_curves(self, layout, flows):
        flowsWord = FLOW if len(flows) == 1 else FLOWS

        name      = 'Total: {:d} {}'.format(len(flows), flowsWord)
        flowsList = flows

        return [ Curve(flowsList, name) ]
