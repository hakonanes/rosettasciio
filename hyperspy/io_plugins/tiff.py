# -*- coding: utf-8 -*-
# Copyright 2007-2011 The Hyperspy developers
#
# This file is part of  Hyperspy.
#
#  Hyperspy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  Hyperspy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with  Hyperspy.  If not, see <http://www.gnu.org/licenses/>.

import warnings

import numpy as np
import traits.api as t
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from hyperspy.misc.io.tifffile import imsave, TiffFile 
from hyperspy.misc import rgb_tools

# Plugin characteristics
# ----------------------
format_name = 'TIFF'
description = 'Import/Export standard image formats Christoph Gohlke\'s tifffile library'
full_suport = False
file_extensions = ['tif', 'tiff']
default_extension = 0 # tif


# Writing features
writes = [(2,0), (2,1)]
# ----------------------

axes_label_codes = {
        'X' : "width",
        'Y' : "height",
        'S' : "sample",
        'P' : "plane",
        'I' : "image series",         
        'Z' : "depth",
        'C' : "color|em-wavelength|channel",
        'E' : "ex-wavelength|lambda",   
        'T' : "time",
        'R' : "region|tile",
        'A' : "angle",
        'F' : "phase",
        'H' : "lifetime",
        'L' : "exposure",
        'V' : "event",
        'Q' : t.Undefined,
        '_' : t.Undefined}

def file_writer(filename, signal, **kwds):
    '''Writes data to tif using Christoph Gohlke's tifffile library
        
        Parameters
        ----------
        filename: str
        signal: a Signal instance

    '''
    data = signal.data
    if signal.is_rgbx is True:
        data = rgb_tools.rgbx2regular_array(data)
        photometric = "rgb"
    else:
        photometric = "minisblack"
    if description not in kwds:
        if signal.mapped_parameters.title:
            kwds['description'] = signal.mapped_parameters.title

    imsave(filename, data,
            software="hyperspy",
            photometric=photometric,
            **kwds)
    
def file_reader(filename, record_by='image',**kwds):
    '''Read data from tif files using Christoph Gohlke's tifffile
    library
    
    Parameters
    ----------
    filename: str
    record_by: {'image'}
        Has no effect because this format only supports recording by
        image.
    
    '''
    with TiffFile(filename, **kwds) as tiff:
        dc = tiff.asarray()
        axes = tiff.series[0]['axes']
        if tiff.is_rgb:
            dc = rgb_tools.regular_array2rgbx(dc)
            axes = axes[:-1]
        op = {}
        names =  [axes_label_codes[axis] for axis in axes]
        axes=[{'size' : size,                                                                
               'name' : unicode(name),                                          
               #'scale': scales[i],                                                  
               #'offset' : origins[i],                                               
               #'units' : unicode(units[i]),
               }
              for size, name in zip(dc.shape, names)]
        op = {}
        for key, tag in tiff[0].tags.iteritems():
            op[key] = tag.value
        mp =  { 'original_filename' : filename,
                'record_by': "image",
                'signal_type' : "",}
        return [{'data' : dc, 
                 'axes' : axes,
                 'original_parameters' : op,
                 'mapped_parameters' : mp,
                 }]

