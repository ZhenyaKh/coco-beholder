#!/usr/bin/env python

CURVE  = 'curve'
CURVES = 'curves'


#
# Class the instance of which generates plotting data and stats for average Jain index
#
class JainIndex(object):
    #
    # Constructor
    # param[in] curves - curves over which the index is computed
    #
    def __init__(self, curves):
        self.curves  = curves # curves over which the index is computed
        self.avgJain = None   # average Jain index


    #
    # Method computes slotted Jain index data to plot
    # param [in] slotsNumber - number of slots
    # param [in] slotSec     - float slot size in seconds
    # returns x-data and y-data
    #
    def get_data(self, slotsNumber, slotSec):
        xData = []
        yData = []

        for slotId in range(slotsNumber):
            curvesNumber  = 0
            sumRate       = 0.0
            sumSquareRate = 0.0

            for curve in self.curves:
                if curve.slottedRates[slotId] is not None:
                    curvesNumber  += 1
                    sumRate       += curve.slottedRates[slotId]
                    sumSquareRate += curve.slottedRates[slotId]**2

            if curvesNumber != 0 and sumSquareRate != 0.0:
                xData.append(slotSec * slotId)
                yData.append(sumRate**2 / (float(curvesNumber) * sumSquareRate))

        return xData, yData


    #
    # Method generates the label for the curve of the graph of the averaged Jain index
    # returns the label
    #
    def get_label(self):
        self.compute_jain_index_stats()

        if self.avgJain is None:
            valueStr = 'no overall average throughputs'
        else:
            valueStr = '{:f}'.format(self.avgJain)

        curvesWord = CURVE if len(self.curves) == 1 else CURVES

        curvesName = 'All {:d} {}'.format(len(self.curves), curvesWord)

        return '{} ({})'.format(curvesName, valueStr)


    #
    # Method computes average Jain index stats
    #
    def compute_jain_index_stats(self):
        curvesNumber  = 0
        sumRate       = 0.0
        sumSquareRate = 0.0

        for curve in self.curves:
            if curve.curveAvgRate is not None:
                curvesNumber  += 1
                sumRate       += curve.curveAvgRate
                sumSquareRate += curve.curveAvgRate**2

        if curvesNumber != 0 and sumSquareRate != 0.0:
            self.avgJain = sumRate**2 / (float(curvesNumber) * sumSquareRate)
