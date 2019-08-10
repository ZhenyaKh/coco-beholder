#!/usr/bin/env python

from variable_delay.src.metadata import metadata_fields
from variable_delay.src.layout import layout_fields

# common data
RUNTIME   = metadata_fields.RUNTIME
ALL_FLOWS = metadata_fields.ALL_FLOWS

# per flow data
SCHEME    = layout_fields.SCHEME
DIRECTION = layout_fields.DIRECTION
ARRIVALS  = 'arrivals'
DELAYS    = 'delays'
SIZES     = 'sizes'
