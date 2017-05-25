#    This file is part of cfelpyutils.
#
#    cfelpyutils is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    cfelpyutils is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with cfelpyutils.  If not, see <http://www.gnu.org/licenses/>.
"""
Utilities for CrystFEL-style geometry files.

This module contains utilities for the processing of CrystFEL-style geometry
files.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy
from cfelpyutils.cfel_crystfel import load_crystfel_geometry


def apply_geometry_from_file(data_as_slab, geometry_filename):
    """Parses a geometry file and applies the geometry to data.

    Parses a geometry file and applies the geometry to detector data in 'slab' format. Turns a 2d array of pixel
    values into an array containing a representation of the physical layout of the detector, keeping the origin of
    the reference system at the beam interaction point.

    Args:

        data_as_slab (numpy.ndarray): the pixel values to which geometry is to be applied.

        geometry_filename (str): geometry filename.

    Returns:

        im_out (numpy.ndarray data_as_slab.dtype): Array containing a representation of the physical layout of the
        detector, with the origin of the  reference system at the beam interaction point.
    """

    yx, slab_shape, img_shape = pixel_maps_for_image_view(geometry_filename)
    im_out = numpy.zeros(img_shape, dtype=data_as_slab.dtype)

    im_out[yx[0], yx[1]] = data_as_slab.ravel()
    return im_out


def apply_geometry_from_pixel_maps(data_as_slab, yx, im_out=None):
    """Applies geometry in pixel map format to data.

    Applies geometry, in the form of pixel maps, to detector data in 'slab' format. Turns a 2d array of pixel values
    into an array containing a representation of the physical layout of the detector, keeping the origin of the
    reference system at the beam interaction point.

    Args:

        data_as_slab (numpy.ndarray): the pixel values to which geometry is to be applied.

        yx (tuple): the yx pixel maps describing the geometry of the detector; each map is a numpy.ndarray.

        im_out (Optional[numpy.ndarray]): array to hold the output; if not provided, one will be generated
        automatically.

    Returns:

        im_out (numpy.ndarray data_as_slab.dtype): Array containing a representation of the physical layout of the
        detector, with the origin of the  reference system at the beam interaction point.
    """

    if im_out is None:
        im_out = numpy.zeros(data_as_slab.shape, dtype=data_as_slab.dtype)

    im_out[yx[0], yx[1]] = data_as_slab.ravel()
    return im_out


def pixel_maps_for_image_view(geometry_filename):
    """Parses a geometry file and creates pixel maps for pyqtgraph visualization.

    Parse the geometry file and creates pixel maps for an  array in 'slab' format containing pixel values. The pixel
    maps can be used to create a representation of the physical layout of the detector in a pyqtgraph ImageView
    widget (i.e. they apply the detector geometry setting the origin of the reference system is in the top left corner
    of the output array).

    Args:

        geometry_filename (str): geometry filename.

    Returns:

        (y, x) (numpy.ndarray int, numpy.ndarray int): pixel maps

        slab_shape tuple (int, int): shape of the original geometry uncorrected array (the pixel values in "slab"
        format).

        img_shape tuple (int, int): shape of the array needed to contain the representation of the physical layout
        of the detector.
    """

    pixm = pixel_maps_from_geometry_file(geometry_filename)
    x, y = pixm[0], pixm[1]
    slab_shape = x.shape

    # find the smallest size of cspad_geom that contains all
    # xy values but is symmetric about the origin
    n = 2 * int(max(abs(y.max()), abs(y.min()))) + 2
    m = 2 * int(max(abs(x.max()), abs(x.min()))) + 2

    # convert y x values to i j values
    i = numpy.array(y, dtype=numpy.int) + n//2 - 1
    j = numpy.array(x, dtype=numpy.int) + m//2 - 1

    yx = (i.flatten(), j.flatten())
    img_shape = (n, m)
    return yx, slab_shape, img_shape


def pixel_maps_from_geometry_file(fnam):
    """Parses a geometry file and creates pixel maps.

    Extracts pixel maps from a CrystFEL-style geometry file. The pixel maps can be used to create a representation of
    the physical layout of the detector, keeping the origin of the  reference system at the beam interaction
    point.

    Args:

        fnam (str): geometry filename.

    Returns:

        x,y,r (numpy.ndarray float, numpy.ndarray float, numpy.ndarray float): slab-like pixel maps with
        respectively x, y coordinates of the pixel and distance of the pixel from the center of the reference system.
    """

    detector = load_crystfel_geometry(fnam)

    max_slab_fs = numpy.array([detector['panels'][k]['max_fs'] for k in detector['panels']]).max()
    max_slab_ss = numpy.array([detector['panels'][k]['max_ss'] for k in detector['panels']]).max()

    x = numpy.zeros((max_slab_ss+1, max_slab_fs+1), dtype=numpy.float32)
    y = numpy.zeros((max_slab_ss+1, max_slab_fs+1), dtype=numpy.float32)

    for p in detector['panels']:
        # get the pixel coords for this asic
        i, j = numpy.meshgrid(numpy.arange(detector['panels'][p]['max_ss'] - detector['panels'][p]['min_ss'] + 1),
                              numpy.arange(detector['panels'][p]['max_fs'] - detector['panels'][p]['min_fs'] + 1),
                              indexing='ij')

        # make the y-x ( ss, fs ) vectors, using complex notation
        dx = detector['panels'][p]['fsy'] + 1J * detector['panels'][p]['fsx']
        dy = detector['panels'][p]['ssy'] + 1J * detector['panels'][p]['ssx']
        r_0 = detector['panels'][p]['cny'] + 1J * detector['panels'][p]['cnx']
        #
        r = i * dy + j * dx + r_0
        #
        y[detector['panels'][p]['min_ss']: detector['panels'][p]['max_ss'] + 1,
            detector['panels'][p]['min_fs']: detector['panels'][p]['max_fs'] + 1] = r.real

        x[detector['panels'][p]['min_ss']: detector['panels'][p]['max_ss'] + 1,
            detector['panels'][p]['min_fs']: detector['panels'][p]['max_fs'] + 1] = r.imag

    r = numpy.sqrt(numpy.square(x) + numpy.square(y))

    return x, y, r

