#!/usr/bin/env python

import jsonlines

WRITE_MODE  = 'w'
APPEND_MODE = 'a'


#
# Custom Exception class for errors connected to reading and writing of jsonl data
#
class DataError(Exception):
    pass


#
# Function writes data to a file in the jsonl format
# param [in] filePath - the full path of the output jsonl file
# param [in] data     - data to write as jsonl
# param [in] mode     - mode in which to write the data
# throws DataError
#
def save_data(filePath, data, mode):
    try:
        if mode != WRITE_MODE and mode != APPEND_MODE:
            raise DataError('Unsupported mode "%s" of writing data to jsonl-file' % mode)

        with jsonlines.open(filePath, mode=mode) as writer:
            writer.write(data)
    except IOError:
        raise DataError('Failed to write jsonl data to the file %s' % filePath)
