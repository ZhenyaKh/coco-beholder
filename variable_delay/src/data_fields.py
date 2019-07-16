#!/usr/bin/env python

from variable_delay.src import metadata_fields
from variable_delay.src import layout_fields

# general data kept in the first line
RUNTIME   = metadata_fields.RUNTIME
ALL_FLOWS = metadata_fields.ALL_FLOWS

# per flow data
SCHEME    = layout_fields.SCHEME
DIRECTION = layout_fields.DIRECTION
ARRIVALS  = 'arrivals'
DELAYS    = 'delays'
SIZES     = 'sizes'
