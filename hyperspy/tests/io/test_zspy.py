# -*- coding: utf-8 -*-
# Copyright 2007-2021 The HyperSpy developers
#
# This file is part of  HyperSpy.
#
#  HyperSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
#  HyperSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with  HyperSpy.  If not, see <http://www.gnu.org/licenses/>.

import gc
import os.path
import sys
import tempfile
import time
from os import remove

import dask.array as da
import h5py
import lmdb
import numpy as np
import pytest
import zarr

from hyperspy._signals.signal1d import Signal1D
from hyperspy._signals.signal2d import Signal2D
from hyperspy.datasets.example_signals import EDS_TEM_Spectrum
from hyperspy.exceptions import VisibleDeprecationWarning
from hyperspy.axes import AxesManager
from hyperspy.io import load
from hyperspy.misc.test_utils import assert_deep_almost_equal
from hyperspy.misc.test_utils import sanitize_dict as san_dict
from hyperspy.roi import Point2DROI
from hyperspy.signal import BaseSignal
from hyperspy.utils import markers
import hyperspy.api as hs

my_path = os.path.dirname(__file__)

data = np.array([4066., 3996., 3932., 3923., 5602., 5288., 7234., 7809.,
                 4710., 5015., 4366., 4524., 4832., 5474., 5718., 5034.,
                 4651., 4613., 4637., 4429., 4217.])
example1_original_metadata = {
    'BEAMDIAM -nm': 100.0,
    'BEAMKV   -kV': 120.0,
    'CHOFFSET': -168.0,
    'COLLANGLE-mR': 3.4,
    'CONVANGLE-mR': 1.5,
    'DATATYPE': 'XY',
    'DATE': '01-OCT-1991',
    'DWELLTIME-ms': 100.0,
    'ELSDET': 'SERIAL',
    'EMISSION -uA': 5.5,
    'FORMAT': 'EMSA/MAS Spectral Data File',
    'MAGCAM': 100.0,
    'NCOLUMNS': 1.0,
    'NPOINTS': 20.0,
    'OFFSET': 520.13,
    'OPERMODE': 'IMAG',
    'OWNER': 'EMSA/MAS TASK FORCE',
    'PROBECUR -nA': 12.345,
    'SIGNALTYPE': 'ELS',
    'THICKNESS-nm': 50.0,
    'TIME': '12:00',
    'TITLE': 'NIO EELS OK SHELL',
    'VERSION': '1.0',
    'XLABEL': 'Energy',
    'XPERCHAN': 3.1,
    'XUNITS': 'eV',
    'YLABEL': 'Counts',
    'YUNITS': 'Intensity'}


class Example1:
    "Used as a base class for the TestExample classes below"

    def test_data(self):
        assert (
                [4066.0,
                 3996.0,
                 3932.0,
                 3923.0,
                 5602.0,
                 5288.0,
                 7234.0,
                 7809.0,
                 4710.0,
                 5015.0,
                 4366.0,
                 4524.0,
                 4832.0,
                 5474.0,
                 5718.0,
                 5034.0,
                 4651.0,
                 4613.0,
                 4637.0,
                 4429.0,
                 4217.0] == self.s.data.tolist())

    def test_original_metadata(self):
        assert (
                example1_original_metadata ==
                self.s.original_metadata.as_dictionary())

    @pytest.mark.xfail(
        reason="dill is not guaranteed to load across Python versions")
    def test_binary_string(self):
        import dill
        # apparently pickle is not "full" and marshal is not
        # backwards-compatible
        f = dill.loads(self.s.metadata.test.binary_string)
        assert f(3.5) == 4.5


class TestSavingMetadataContainers:

    def setup_method(self, method):
        self.s = BaseSignal([0.1])

    def test_save_unicode(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', ['a', 'b', '\u6f22\u5b57'])
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        s.save("test.zspy")
        l = load(fname)
        assert isinstance(l.metadata.test[0], str)
        assert isinstance(l.metadata.test[1], str)
        assert isinstance(l.metadata.test[2], str)
        assert l.metadata.test[2] == '\u6f22\u5b57'

    def test_save_long_list(self, tmp_path):
        s = self.s
        s.metadata.set_item('long_list', list(range(10000)))
        start = time.time()
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        end = time.time()
        assert end - start < 1.0  # It should finish in less that 1 s.

    def test_numpy_only_inner_lists(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', [[1., 2], ('3', 4)])
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert isinstance(l.metadata.test, list)
        assert isinstance(l.metadata.test[0], list)
        assert isinstance(l.metadata.test[1], tuple)

    @pytest.mark.xfail(sys.platform == 'win32',
                       reason="randomly fails in win32")
    def test_numpy_general_type(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', np.array([[1., 2], ['3', 4]]))
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        np.testing.assert_array_equal(l.metadata.test, s.metadata.test)

    @pytest.mark.xfail(sys.platform == 'win32',
                       reason="randomly fails in win32")
    def test_list_general_type(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', [[1., 2], ['3', 4]])
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert isinstance(l.metadata.test[0][0], float)
        assert isinstance(l.metadata.test[0][1], float)
        assert isinstance(l.metadata.test[1][0], str)
        assert isinstance(l.metadata.test[1][1], str)

    @pytest.mark.xfail(sys.platform == 'win32',
                       reason="randomly fails in win32")
    def test_general_type_not_working(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', (BaseSignal([1]), 0.1, 'test_string'))
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert isinstance(l.metadata.test, tuple)
        assert isinstance(l.metadata.test[0], Signal1D)
        assert isinstance(l.metadata.test[1], float)
        assert isinstance(l.metadata.test[2], str)

    def test_unsupported_type(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', Point2DROI(1, 2))
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert 'test' not in l.metadata

    def test_date_time(self, tmp_path):
        s = self.s
        date, time = "2016-08-05", "15:00:00.450"
        s.metadata.General.date = date
        s.metadata.General.time = time
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert l.metadata.General.date == date
        assert l.metadata.General.time == time

    def test_general_metadata(self, tmp_path):
        s = self.s
        notes = "Dummy notes"
        authors = "Author 1, Author 2"
        doi = "doi"
        s.metadata.General.notes = notes
        s.metadata.General.authors = authors
        s.metadata.General.doi = doi
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert l.metadata.General.notes == notes
        assert l.metadata.General.authors == authors
        assert l.metadata.General.doi == doi

    def test_quantity(self, tmp_path):
        s = self.s
        quantity = "Intensity (electron)"
        s.metadata.Signal.quantity = quantity
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert l.metadata.Signal.quantity == quantity

    def test_title(self, tmp_path):
        s = self.s
        fname = tmp_path / 'test.zspy'
        s.metadata.General.title = '__unnamed__'
        s.save(fname)
        l = load(fname)
        assert l.metadata.General.title is ""

    def test_save_bytes(self, tmp_path):
        s = self.s
        byte_message = bytes("testing", 'utf-8')
        s.metadata.set_item('test', byte_message)
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        assert l.metadata.test == s.metadata.test.decode()

    def test_save_empty_tuple(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', ())
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        #strange becuase you need the encoding...
        assert l.metadata.test == s.metadata.test

    def test_save_axes_manager(self, tmp_path):
        s = self.s
        s.metadata.set_item('test', s.axes_manager)
        fname = tmp_path / 'test.zspy'
        s.save(fname)
        l = load(fname)
        #strange becuase you need the encoding...
        assert isinstance(l.metadata.test, AxesManager)

class TestLoadingOOMReadOnly:

    def setup_method(self, method):
        s = BaseSignal(np.empty((5, 5, 5)))
        s.save('tmp.zspy', overwrite=True)
        self.shape = (10000, 10000, 100)
        del s
        f = zarr.open('tmp.zspy', mode='r+')
        s = f['Experiments/__unnamed__']
        del s['data']
        s.create_dataset(
            'data',
            shape=self.shape,
            dtype='float64',
            chunks=True)

    def test_oom_loading(self):
        s = load('tmp.zspy', lazy=True)
        assert self.shape == s.data.shape
        assert isinstance(s.data, da.Array)
        assert s._lazy
        s.close_file()

    def teardown_method(self, method):
        gc.collect()  # Make sure any memmaps are closed first!
        try:
            remove('tmp.zspy')
        except BaseException:
            # Don't fail tests if we cannot remove
            pass


class TestPassingArgs:
    def test_compression_opts(self, tmp_path):
        self.filename = tmp_path / 'testfile.zspy'
        from numcodecs import Blosc
        comp = Blosc(cname='zstd', clevel=1, shuffle=Blosc.SHUFFLE)
        BaseSignal([1, 2, 3]).save(self.filename, compressor=comp)
        f = zarr.open(self.filename.__str__(), mode='r+')
        d = f['Experiments/__unnamed__/data']
        assert (d.compressor == comp)


class TestAxesConfiguration:

    def test_axes_configuration(self, tmp_path):
        self.filename = tmp_path / 'testfile.zspy'
        s = BaseSignal(np.zeros((2, 2, 2, 2, 2)))
        s.axes_manager.signal_axes[0].navigate = True
        s.axes_manager.signal_axes[0].navigate = True
        s.save(self.filename)
        s = load(self.filename)
        assert s.axes_manager.navigation_axes[0].index_in_array == 4
        assert s.axes_manager.navigation_axes[1].index_in_array == 3
        assert s.axes_manager.signal_dimension == 3


class TestAxesConfigurationBinning:
    def test_axes_configuration(self):
        self.filename = 'testfile.zspy'
        s = BaseSignal(np.zeros((2, 2, 2)))
        s.axes_manager.signal_axes[-1].is_binned = True
        s.save(self.filename)
        s = load(self.filename)
        assert s.axes_manager.signal_axes[-1].is_binned == True


class Test_permanent_markers_io:

    def test_save_permanent_marker(self):
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.point(x=5, y=5)
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/testsavefile.zspy'
        s.save(filename)

    def test_save_load_empty_metadata_markers(self):
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.point(x=5, y=5)
        m.name = "test"
        s.add_marker(m, permanent=True)
        del s.metadata.Markers.test
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/testsavefile.zspy'
        s.save(filename)
        s1 = load(filename)
        assert len(s1.metadata.Markers) == 0

    def test_save_load_permanent_marker(self):
        x, y = 5, 2
        color = 'red'
        size = 10
        name = 'testname'
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.point(x=x, y=y, color=color, size=size)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/testloadfile.zspy'
        s.save(filename)
        s1 = load(filename)
        assert s1.metadata.Markers.has_item(name)
        m1 = s1.metadata.Markers.get_item(name)
        assert m1.get_data_position('x1') == x
        assert m1.get_data_position('y1') == y
        assert m1.get_data_position('size') == size
        assert m1.marker_properties['color'] == color
        assert m1.name == name

    def test_save_load_permanent_marker_all_types(self):
        x1, y1, x2, y2 = 5, 2, 1, 8
        s = Signal2D(np.arange(100).reshape(10, 10))
        m0_list = [
            markers.point(x=x1, y=y1),
            markers.horizontal_line(y=y1),
            markers.horizontal_line_segment(x1=x1, x2=x2, y=y1),
            markers.line_segment(x1=x1, x2=x2, y1=y1, y2=y2),
            markers.rectangle(x1=x1, x2=x2, y1=y1, y2=y2),
            markers.text(x=x1, y=y1, text="test"),
            markers.vertical_line(x=x1),
            markers.vertical_line_segment(x=x1, y1=y1, y2=y2),
        ]
        for m in m0_list:
            s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/testallmarkersfile.zspy'
        s.save(filename)
        s1 = load(filename)
        markers_dict = s1.metadata.Markers
        m0_dict_list = []
        m1_dict_list = []
        for m in m0_list:
            m0_dict_list.append(san_dict(m._to_dictionary()))
            m1_dict_list.append(
                san_dict(markers_dict.get_item(m.name)._to_dictionary()))
        assert len(list(s1.metadata.Markers)) == 8
        for m0_dict, m1_dict in zip(m0_dict_list, m1_dict_list):
            assert m0_dict == m1_dict

    def test_save_load_horizontal_line_marker(self):
        y = 8
        color = 'blue'
        linewidth = 2.5
        name = "horizontal_line_test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.horizontal_line(y=y, color=color, linewidth=linewidth)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_horizontal_line_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_horizontal_line_segment_marker(self):
        x1, x2, y = 1, 5, 8
        color = 'red'
        linewidth = 1.2
        name = "horizontal_line_segment_test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.horizontal_line_segment(
            x1=x1, x2=x2, y=y, color=color, linewidth=linewidth)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_horizontal_line_segment_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_vertical_line_marker(self):
        x = 9
        color = 'black'
        linewidth = 3.5
        name = "vertical_line_test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.vertical_line(x=x, color=color, linewidth=linewidth)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_vertical_line_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_vertical_line_segment_marker(self):
        x, y1, y2 = 2, 1, 3
        color = 'white'
        linewidth = 4.2
        name = "vertical_line_segment_test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.vertical_line_segment(
            x=x, y1=y1, y2=y2, color=color, linewidth=linewidth)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_vertical_line_segment_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_line_segment_marker(self):
        x1, x2, y1, y2 = 1, 9, 4, 7
        color = 'cyan'
        linewidth = 0.7
        name = "line_segment_test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.line_segment(
            x1=x1, x2=x2, y1=y1, y2=y2, color=color, linewidth=linewidth)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_line_segment_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_point_marker(self):
        x, y = 9, 8
        color = 'purple'
        name = "point test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.point(
            x=x, y=y, color=color)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_point_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_rectangle_marker(self):
        x1, x2, y1, y2 = 2, 4, 1, 3
        color = 'yellow'
        linewidth = 5
        name = "rectangle_test"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.rectangle(
            x1=x1, x2=x2, y1=y1, y2=y2, color=color, linewidth=linewidth)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_rectangle_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_metadata_update_to_v3_1(self):
        md = {'Acquisition_instrument': {'SEM': {'Stage': {'tilt_alpha': 5.0}},
                                         'TEM': {'Detector': {'Camera': {'exposure': 0.20000000000000001}},
                                                 'Stage': {'tilt_alpha': 10.0},
                                                 'acquisition_mode': 'TEM',
                                                 'beam_current': 0.0,
                                                 'beam_energy': 200.0,
                                                 'camera_length': 320.00000000000006,
                                                 'microscope': 'FEI Tecnai'}},
              'General': {'date': '2014-07-09',
                          'original_filename': 'test_diffraction_pattern.dm3',
                          'time': '18:56:37',
                          'title': 'test_diffraction_pattern'},
              'Signal': {'Noise_properties': {'Variance_linear_model': {'gain_factor': 1.0,
                                                                        'gain_offset': 0.0}},
                         'quantity': 'Intensity',
                         'signal_type': ''},
              '_HyperSpy': {'Folding': {'original_axes_manager': None,
                                        'original_shape': None,
                                        'signal_unfolded': False,
                                        'unfolded': False}}}
        s = load(os.path.join(
            my_path,
            "hdf5_files",
            'example2_v3.1.hspy'))
        assert_deep_almost_equal(s.metadata.as_dictionary(), md)

    def test_save_load_text_marker(self):
        x, y = 3, 9.5
        color = 'brown'
        name = "text_test"
        text = "a text"
        s = Signal2D(np.arange(100).reshape(10, 10))
        m = markers.text(
            x=x, y=y, text=text, color=color)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_text_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())

    def test_save_load_multidim_navigation_marker(self):
        x, y = (1, 2, 3), (5, 6, 7)
        name = 'test point'
        s = Signal2D(np.arange(300).reshape(3, 10, 10))
        m = markers.point(x=x, y=y)
        m.name = name
        s.add_marker(m, permanent=True)
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/test_save_multidim_nav_marker.zspy'
        s.save(filename)
        s1 = load(filename)
        m1 = s1.metadata.Markers.get_item(name)
        assert san_dict(m1._to_dictionary()) == san_dict(m._to_dictionary())
        assert m1.get_data_position('x1') == x[0]
        assert m1.get_data_position('y1') == y[0]
        s1.axes_manager.navigation_axes[0].index = 1
        assert m1.get_data_position('x1') == x[1]
        assert m1.get_data_position('y1') == y[1]
        s1.axes_manager.navigation_axes[0].index = 2
        assert m1.get_data_position('x1') == x[2]
        assert m1.get_data_position('y1') == y[2]




@pytest.mark.parametrize("compressor", (None, "default", "blosc"))
def test_compression(compressor, tmp_path):
    if compressor is "blosc":
        from numcodecs import Blosc
        compressor = Blosc(cname='zstd', clevel=3, shuffle=Blosc.BITSHUFFLE)
    s = Signal1D(np.ones((3, 3)))
    s.save(tmp_path / 'test_compression.zspy',
           overwrite=True,
           compressor=compressor)
    load(tmp_path / 'test_compression.zspy')


def test_strings_from_py2():
    s = EDS_TEM_Spectrum()
    assert isinstance(s.metadata.Sample.elements, list)


def test_save_ragged_array(tmp_path):
    a = np.array([0, 1])
    b = np.array([0, 1, 2])
    s = BaseSignal(np.array([a, b], dtype=object)).T
    fname = tmp_path / 'test_save_ragged_array.zspy'
    s.save(fname)
    s1 = load(fname)
    for i in range(len(s.data)):
        np.testing.assert_allclose(s.data[i], s1.data[i])
    assert s.__class__ == s1.__class__


def test_save_chunks_signal_metadata():
    N = 10
    dim = 3
    s = Signal1D(np.arange(N ** dim).reshape([N] * dim))
    s.navigator = s.sum(-1)
    s.change_dtype('float')
    s.decomposition()
    with tempfile.TemporaryDirectory() as tmp:
        filename = os.path.join(tmp, 'test_save_chunks_signal_metadata.zspy')
    chunks = (5, 2, 2)
    s.save(filename, chunks=chunks)
    s2 = load(filename, lazy=True)
    assert tuple([c[0] for c in s2.data.chunks]) == chunks


def test_chunking_saving_lazy():
    s = Signal2D(da.zeros((50, 100, 100))).as_lazy()
    s.data = s.data.rechunk([50, 25, 25])
    with tempfile.TemporaryDirectory() as tmp:
        filename = os.path.join(tmp, 'test_chunking_saving_lazy.zspy')
        filename2 = os.path.join(tmp, 'test_chunking_saving_lazy_chunks_True.zspy')
        filename3 = os.path.join(tmp, 'test_chunking_saving_lazy_chunks_specified.zspy')
    s.save(filename)
    s1 = load(filename, lazy=True)
    assert s.data.chunks == s1.data.chunks

    s.save(filename2)
    s2 = load(filename2, lazy=True)
    assert tuple([c[0] for c in s2.data.chunks]) == (50, 25, 25)

    # specify chunks
    chunks = (50, 10, 10)
    s.save(filename3, chunks=chunks)
    s3 = load(filename3, lazy=True)
    assert tuple([c[0] for c in s3.data.chunks]) == chunks

def test_data_lazy():
    s = Signal2D(da.ones((5, 10, 10))).as_lazy()
    s.data = s.data.rechunk([5, 2, 2])
    with tempfile.TemporaryDirectory() as tmp:
        filename = os.path.join(tmp, 'test_chunking_saving_lazy.zspy')
    s.save(filename)
    s1 = load(filename)
    np.testing.assert_array_almost_equal(s1.data, s.data)


class TestZspy:
    @pytest.fixture
    def signal(self):
        data = np.ones((10,10,10,10))
        s = Signal1D(data)
        return s

    def test_save_load_model(self, signal):
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/testmodels.zspy'
        m = signal.create_model()
        m.append(hs.model.components1D.Gaussian())
        m.store("test")
        signal.save(filename)
        signal2 = hs.load(filename)
        m2 = signal2.models.restore("test")
        assert m.signal == m2.signal

    def test_save_N5_type(self,signal):
        with tempfile.TemporaryDirectory() as tmp:
            filename = tmp + '/testmodels.zspy'
        store = zarr.N5Store(path=filename)
        signal.save(store.path, write_to_storage=True)
        signal2 = hs.load(filename)
        np.testing.assert_array_equal(signal2.data, signal.data)

    @pytest.mark.skip(reason="lmdb must be installed to test")
    def test_save_lmdb_type(self, signal):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(tmp+"/testmodels.zspy")
            filename = tmp + '/testmodels.zspy/'
            store = zarr.LMDBStore(path=filename)
            signal.save(store.path, write_to_storage=True)
            signal2 = hs.load(store.path)
            np.testing.assert_array_equal(signal2.data, signal.data)