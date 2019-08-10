#!/usr/bin/env python

from variable_delay.src.plot.plot_type import PlotType
from variable_delay.src.layout.layout import compute_per_flow
from variable_delay.src.layout.layout_fields import SCHEME, DIRECTION
from variable_delay.src.plot.curve import Curve

#
# Class of per-flow plots/stats
#
class PerFlowPlot(PlotType):
    #
    # Constructor
    #
    def __init__(self):
        PlotType.__init__(self)
        # name of the type of plots/stats
        self.name = 'per-flow'

        # curve's label prefix notation
        self.notation = 'Label notation: Flow <flow id>: <scheme> <direction>'


    #
    # Method generates curves: flows merged into each curve and name of each curve.
    # param [in] layout - layout of flows
    # param [in] flows  - flows to divide into curves
    # returns curves
    #
    def get_curves(self, layout, flows):
        schemes    = compute_per_flow(SCHEME,    layout)
        directions = compute_per_flow(DIRECTION, layout)
        template   = 'Flow {:d}: {} {}'

        curves = []

        for flow in flows:
            name      = template.format(flow.id + 1, schemes[flow.id], directions[flow.id])
            flowsList = [ flow ]

            curves.append(Curve(flowsList, name))

        return curves
