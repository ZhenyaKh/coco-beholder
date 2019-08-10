#!/usr/bin/env python

PERCENTS = 100.0

#
# Class the instance of which allows to make loss stats
#
class Loss(object):
    #
    # Constructor
    # param [in] curves - the curves loss stats of which should be computed
    #
    def __init__(self, curves):
        self.lossStats = { } # per curve: loss stats

        self.compute_stats(curves)


    #
    # Method gets the statistics string of the curve's loss
    # param [in] curve - the curve whose loss stats string is queried
    # returns the loss statistics string
    #
    def get_stats_string(self, curve):
        curveLoss = self.lossStats[curve]

        if curveLoss is None:
            valueStr = 'N/A as no bytes were sent by the curve\'s senders'
        else:
            valueStr = '{:f} %'.format(curveLoss)

        return 'Loss                  : {}'.format(valueStr)


    #
    # Method computes loss stats of the curves
    # param [in] curves - the curves whose loss stats should be computed
    #
    def compute_stats(self, curves):
        for curve in curves:
            curveLoss = None

            if curve.allSentBytes != 0:
                curveLoss = float(curve.lostSentBytes) / curve.allSentBytes * PERCENTS

            self.lossStats[curve] = curveLoss
