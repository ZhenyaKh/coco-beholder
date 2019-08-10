#!/usr/bin/env python

import sys
import time

SECOND   = 1.0
PERCENTS = 100.0


#
# Class the instance of which is a progress bar
#
class ProgressBar(object):
    #
    # Constructor
    # param [in] name     - name of the progress bar
    # param [in] capacity - capacity of the progress bar
    #
    def __init__(self, name, capacity):
        self.name     = name
        self.capacity = capacity
        self.toErase  = 0

        self.draw(0, 0)

        self.startTime = time.time()
        self.lastTime  = self.startTime


    #
    # Method updates the current state of the progress bar
    # param [in] value - the current value out of the full capacity
    #
    def update(self, value):
        newTime = time.time()

        if newTime - self.lastTime > SECOND:
            self.draw(float(value) / self.capacity * PERCENTS,  int(newTime - self.startTime))
            self.lastTime = newTime


    #
    # Method completes the progress bar
    #
    def finish(self):
        self.draw(PERCENTS, time.time() - self.startTime)
        sys.stdout.write('\n\n')
        sys.stdout.flush()


    #
    # Method prints out the current state of the progress bar to terminal
    # param [in] percentage - progress to print
    # param [in] timestamp  - timestamp to print
    #
    def draw(self, percentage, timestamp):
        toPrint = '{}: {:5.1f}% in {:.2f}s'.format(self.name, percentage, timestamp)

        sys.stdout.write('\b' * self.toErase)
        sys.stdout.write(toPrint)
        sys.stdout.flush()

        self.toErase = len(toPrint)
