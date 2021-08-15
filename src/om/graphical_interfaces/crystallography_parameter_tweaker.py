# This file is part of OM.
#
# OM is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# OM is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with OM.
# If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2020 -2021 SLAC National Accelerator Laboratory
#
# Based on OnDA - Copyright 2014-2019 Deutsches Elektronen-Synchrotron DESY,
# a research centre of the Helmholtz Association.
"""
OM's real-time Parameter Tweaker.

This module contains the implementation of a graphical interface that can be used in
crystallography experiments to test peak-finding parameters in real time.
"""
import collections
import copy
import signal
import sys
import time
from typing import Any, Deque, Dict, List, Tuple, Union

import click  # type: ignore
import numpy  # type: ignore

from om.algorithms import crystallography as cryst_algs
from om.graphical_interfaces import base as graph_interfaces_base
from om.utils import crystfel_geometry, exceptions, parameters
from om.utils.crystfel_geometry import TypePixelMaps

try:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
except ImportError:
    raise exceptions.OmMissingDependencyError(
        "The following required module cannot be imported: PyQt5"
    )

try:
    import pyqtgraph  # type: ignore
except ImportError:
    raise exceptions.OmMissingDependencyError(
        "The following required module cannot be imported: pyqtgraph"
    )


class CrystallographyParameterTweaker(graph_interfaces_base.OmGui):
    """
    See documentation of the `__init__` function.

    Base class: [`OmGui`][om.graphical_interfaces.base.OmGui]
    """

    def __init__(self, *, url: str, monitor_parameters: parameters.MonitorParams):
        """
        OM Parameter Tweaker for Crystallography.

        This class implements a graphical user interface that can be used to test new
        peak finding parameters in real time. It is a subclass of the [OmGui]
        [om.graphical_interfaces.base.OmGui] base class.

        This GUI receives detector frame data from an OndA Monitor for Crystallography
        when it is tagged with the 'omdetectordata' label.  The received data must
        include processed detector frames.

        The GUI allows the user to choose a set of peak-finding parameters. It then
        applies the [Peakfinder8PeakDetection]
        [om.algorithms.crystallography.Peakfinder8PeakDetection] algorithm on the fly
        to each received frame. FInally, it displays the frame together with the
        detected peaks. A data buffer allows the GUI to stop receiving data from the
        monitor but still keep in memory the last 10 received frames to inspect and
        operate on.

        Arguments:

            url (str): the URL at which the GUI will connect and listen for data. This
                must be a string in the format used by the ZeroMQ Protocol.
        """
        super(CrystallographyParameterTweaker, self).__init__(
            url=url,
            tag="view:omtweakingdata",
        )

        self._img: Union[numpy.array, None] = None
        self._frame_list: Deque[Dict[str, Any]] = collections.deque(maxlen=20)
        self._current_frame_index: int = -1
        self._monitor_params = monitor_parameters

        self._received_data: Dict[str, Any] = {}

        self._pixelmaps: TypePixelMaps = (
            crystfel_geometry.pixel_maps_from_geometry_file(
                filename=self._monitor_params.get_parameter(
                    group="crystallography",
                    parameter="geometry_file",
                    parameter_type=str,
                    required=True,
                )
            )
        )

        y_minimum: int = (
            2
            * int(max(abs(self._pixelmaps["y"].max()), abs(self._pixelmaps["y"].min())))
            + 2
        )
        x_minimum: int = (
            2
            * int(max(abs(self._pixelmaps["x"].max()), abs(self._pixelmaps["x"].min())))
            + 2
        )
        visual_img_shape: Tuple[int, int] = (y_minimum, x_minimum)
        self._img_center_x: int = int(visual_img_shape[1] / 2)
        self._img_center_y: int = int(visual_img_shape[0] / 2)
        self._visual_pixelmap_x: numpy.ndarray = (
            numpy.array(self._pixelmaps["x"], dtype=numpy.int)
            + visual_img_shape[1] // 2
            - 1
        ).flatten()
        self._visual_pixelmap_y: numpy.ndarray = (
            numpy.array(self._pixelmaps["y"], dtype=numpy.int)
            + visual_img_shape[0] // 2
            - 1
        ).flatten()
        self._assembled_img: numpy.ndarray = numpy.zeros(
            shape=visual_img_shape, dtype=numpy.float32
        )

        self._peak_detection: cryst_algs.Peakfinder8PeakDetection = (
            cryst_algs.Peakfinder8PeakDetection(
                parameters=self._monitor_params.get_parameter_group(
                    group="peakfinder8_peak_detection"
                ),
                radius_pixel_map=self._pixelmaps["radius"],
            )
        )

        pyqtgraph.setConfigOption("background", 0.2)

        self._ring_pen: Any = pyqtgraph.mkPen("r", width=2)
        self._peak_canvas: Any = pyqtgraph.ScatterPlotItem()

        self._image_view: Any = pyqtgraph.ImageView()
        self._image_view.ui.menuBtn.hide()
        self._image_view.ui.roiBtn.hide()
        self._image_view.getView().addItem(self._peak_canvas)

        self._back_button: Any = QtWidgets.QPushButton(text="Back")
        self._back_button.clicked.connect(self._back_button_clicked)

        self._forward_button: Any = QtWidgets.QPushButton(text="Forward")
        self._forward_button.clicked.connect(self._forward_button_clicked)

        self._play_pause_button: Any = QtWidgets.QPushButton(text="Pause")
        self._play_pause_button.clicked.connect(self._play_pause_button_clicked)

        self._float_regex: Any = QtCore.QRegExp(r"[0-9.,]+")
        self._float_validator: Any = QtGui.QRegExpValidator()
        self._float_validator.setRegExp(self._float_regex)

        self._int_regex: Any = QtCore.QRegExp(r"[0-9]+")
        self._int_validator: Any = QtGui.QRegExpValidator()
        self._int_validator.setRegExp(self._int_regex)

        self._param_label: Any = QtWidgets.QLabel(self)
        self._param_label.setText("<b>Peakfinder Parameters:</b>")

        self._adc_threshold_label: Any = QtWidgets.QLabel(self)
        self._adc_threshold_label.setText("adc_threshold")
        self._adc_threshold_lineedit: Any = QtWidgets.QLineEdit(self)
        self._adc_threshold_lineedit.setText(str(self._peak_detection.get_adc_thresh()))
        self._adc_threshold_lineedit.setValidator(self._float_validator)
        self._adc_threshold_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout2: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout2.addWidget(self._adc_threshold_label)
        self._horizontal_layout2.addWidget(self._adc_threshold_lineedit)

        self._min_snr_label: Any = QtWidgets.QLabel(self)
        self._min_snr_label.setText("minmum_snr")
        self._min_snr_lineedit: Any = QtWidgets.QLineEdit(self)
        self._min_snr_lineedit.setText(str(self._peak_detection.get_minimum_snr()))
        self._min_snr_lineedit.setValidator(self._float_validator)
        self._min_snr_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout3: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout3.addWidget(self._min_snr_label)
        self._horizontal_layout3.addWidget(self._min_snr_lineedit)

        self._min_pixel_count_label: Any = QtWidgets.QLabel(self)
        self._min_pixel_count_label.setText("min_pixel_count")
        self._min_pixel_count_lineedit: Any = QtWidgets.QLineEdit(self)
        self._min_pixel_count_lineedit.setText(
            str(self._peak_detection.get_min_pixel_count())
        )
        self._min_pixel_count_lineedit.setValidator(self._int_validator)
        self._min_pixel_count_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout4: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout4.addWidget(self._min_pixel_count_label)
        self._horizontal_layout4.addWidget(self._min_pixel_count_lineedit)

        self._max_pixel_count_label: Any = QtWidgets.QLabel(self)
        self._max_pixel_count_label.setText("max_pixel_count")
        self._max_pixel_count_lineedit: Any = QtWidgets.QLineEdit(self)
        self._max_pixel_count_lineedit.setText(
            str(self._peak_detection.get_max_pixel_count())
        )
        self._max_pixel_count_lineedit.setValidator(self._int_validator)
        self._max_pixel_count_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout5: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout5.addWidget(self._max_pixel_count_label)
        self._horizontal_layout5.addWidget(self._max_pixel_count_lineedit)

        self._local_bg_radius_label: Any = QtWidgets.QLabel(self)
        self._local_bg_radius_label.setText("local_bg_radius")
        self._local_bg_radius_lineedit: Any = QtWidgets.QLineEdit(self)
        self._local_bg_radius_lineedit.setText(
            str(self._peak_detection.get_local_bg_radius())
        )
        self._local_bg_radius_lineedit.setValidator(self._int_validator)
        self._local_bg_radius_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout6: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout6.addWidget(self._local_bg_radius_label)
        self._horizontal_layout6.addWidget(self._local_bg_radius_lineedit)

        self._min_res_label: Any = QtWidgets.QLabel(self)
        self._min_res_label.setText("min_res")
        self._min_res_lineedit: Any = QtWidgets.QLineEdit(self)
        self._min_res_lineedit.setText(str(self._peak_detection.get_min_res()))
        self._min_res_lineedit.setValidator(self._int_validator)
        self._min_res_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout7: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout7.addWidget(self._min_res_label)
        self._horizontal_layout7.addWidget(self._min_res_lineedit)

        self._max_res_label: Any = QtWidgets.QLabel(self)
        self._max_res_label.setText("max_res")
        self._max_res_lineedit: Any = QtWidgets.QLineEdit(self)
        self._max_res_lineedit.setText(str(self._peak_detection.get_max_res()))
        self._max_res_lineedit.setValidator(self._int_validator)
        self._max_res_lineedit.editingFinished.connect(
            self._update_peak_detection_parameters
        )
        self._horizontal_layout8: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout8.addWidget(self._max_res_label)
        self._horizontal_layout8.addWidget(self._max_res_lineedit)

        self._splitter: Any = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._horizontal_layout1: Any = QtWidgets.QHBoxLayout()
        self._horizontal_layout1.addWidget(self._back_button)
        self._horizontal_layout1.addWidget(self._forward_button)
        self._horizontal_layout1.addWidget(self._play_pause_button)
        self._vertical_layout_0: Any = QtWidgets.QVBoxLayout()
        self._vertical_layout_0.addWidget(self._image_view)
        self._vertical_layout_0.addLayout(self._horizontal_layout1)

        self._vertical_layout_1: Any = QtWidgets.QVBoxLayout()
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout8)
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout7)
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout6)
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout5)
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout4)
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout3)
        self._vertical_layout_1.insertLayout(0, self._horizontal_layout2)
        self._vertical_layout_1.insertWidget(0, self._param_label)
        self._vertical_layout_1.addStretch(1)
        self._vertical_layout_0_widget: Any = QtWidgets.QWidget()
        self._vertical_layout_0_widget.setLayout(self._vertical_layout_0)
        self._vertical_layout_1_widget: Any = QtWidgets.QWidget()
        self._vertical_layout_1_widget.setLayout(self._vertical_layout_1)

        self._splitter.addWidget(self._vertical_layout_0_widget)
        self._splitter.addWidget(self._vertical_layout_1_widget)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        self.setCentralWidget(self._splitter)

        self.show()

    def _update_peaks(
        self,
        *,
        peak_list_x_in_frame: numpy.ndarray,
        peak_list_y_in_frame: numpy.ndarray,
    ) -> None:
        # Updates the Bragg peaks shown by the viewer.
        QtWidgets.QApplication.processEvents()

        self._peak_canvas.setData(
            x=peak_list_y_in_frame,
            y=peak_list_x_in_frame,
            symbol="o",
            size=[5] * len(peak_list_x_in_frame),
            brush=(255, 255, 255, 0),
            pen=self._ring_pen,
            pxMode=False,
        )

    def _update_peak_detection_parameters(self) -> None:
        # Updates the peak detection parameters

        try:
            pf8_adc_threshold: float = float(self._adc_threshold_lineedit.text())
            pf8_minimum_snr: float = float(self._min_snr_lineedit.text())
            pf8_min_pixel_count: int = int(self._min_pixel_count_lineedit.text())
            pf8_max_pixel_count: int = int(self._max_pixel_count_lineedit.text())
            pf8_local_bg_radius: int = int(self._local_bg_radius_lineedit.text())
            pf8_min_res: int = int(self._min_res_lineedit.text())
            pf8_max_res: int = int(self._max_res_lineedit.text())
        except ValueError:
            return

        self._peak_detection.set_adc_thresh(pf8_adc_threshold)
        self._peak_detection.set_minimum_snr(pf8_minimum_snr)
        self._peak_detection.set_min_pixel_count(pf8_min_pixel_count)
        self._peak_detection.set_max_pixel_count(pf8_max_pixel_count)
        self._peak_detection.set_local_bg_radius(pf8_local_bg_radius)
        self._peak_detection.set_min_res(pf8_min_res)
        self._peak_detection.set_max_res(pf8_max_res)

        self._detect_peaks()

    def _detect_peaks(self) -> None:
        # Performs peak detection with the current parameters

        try:
            current_data: numpy.ndarray = self._frame_list[self._current_frame_index]
        except IndexError:
            # If the framebuffer is empty, returns without drawing anything.
            return

        peak_list: cryst_algs.TypePeakList = self._peak_detection.find_peaks(
            data=current_data["detector_data"]
        )

        peak_list_x_in_frame: List[float] = []
        peak_list_y_in_frame: List[float] = []
        data_shape: Tuple[int, int] = current_data["detector_data"].shape

        peak_fs: float
        peak_ss: float
        peak_value: float
        for peak_fs, peak_ss, peak_value in zip(
            peak_list["fs"],
            peak_list["ss"],
            peak_list["intensity"],
        ):
            peak_index_in_slab: int = int(round(peak_ss)) * data_shape[1] + int(
                round(peak_fs)
            )
            y_in_frame: float = self._visual_pixelmap_y[peak_index_in_slab]
            x_in_frame: float = self._visual_pixelmap_x[peak_index_in_slab]
            peak_list_x_in_frame.append(y_in_frame)
            peak_list_y_in_frame.append(x_in_frame)

        self._update_peaks(
            peak_list_x_in_frame=peak_list_x_in_frame,
            peak_list_y_in_frame=peak_list_y_in_frame,
        )

    def _update_image_and_peaks(self) -> None:
        # Updates the image and Bragg peaks shown by the viewer.

        try:
            current_data: numpy.ndarray = self._frame_list[self._current_frame_index]
        except IndexError:
            # If the framebuffer is empty, returns without drawing anything.
            return

        QtWidgets.QApplication.processEvents()

        self._assembled_img[self._visual_pixelmap_y, self._visual_pixelmap_x] = (
            current_data["detector_data"].ravel().astype(self._assembled_img.dtype)
        )

        self._image_view.setImage(
            self._assembled_img.T,
            autoLevels=False,
            autoRange=False,
            autoHistogramRange=False,
        )

        QtWidgets.QApplication.processEvents()

        self._detect_peaks()

        QtWidgets.QApplication.processEvents()

        # Computes the estimated age of the received data and prints it into the status
        # bar (a GUI is supposed to be a Qt MainWindow widget, so it is supposed to
        # have a status bar).
        timenow: float = time.time()
        self.statusBar().showMessage(
            "Estimated delay: {0} seconds".format(
                round(timenow - current_data["timestamp"], 6)
            )
        )

    def update_gui(self) -> None:
        """
        Updates the elements of the Crystallography Parameter Tweaker.

        This method overrides the corresponding method of the base class: please also
        refer to the documentation of that class for more information.

        This function stores the data received from OM, and calls the internal
        functions that initially perform the hit finding with the current chosen
        parameters, and then display the detector frame and the detected peaks.
        """
        # Makes sure that the data shown by the viewer is updated if data is
        # received.

        if self._received_data:
            # Resets the 'received_data' attribute to None. One can then check if
            # data has been received simply by checking wether the attribute is not
            # False.
            local_data = self._received_data
            self._received_data = {}
        else:
            # If no data has been received, returns without drawing anything.
            return

        self._frame_list.append(copy.deepcopy(local_data))
        self._current_frame_index = len(self._frame_list) - 1

        self._update_image_and_peaks()

    def _back_button_clicked(self) -> None:
        # Manages clicks on the 'back' button.
        self._stop_stream()
        if self._current_frame_index > 0:
            self._current_frame_index -= 1
        print("Showing frame {0} in the buffer".format(self._current_frame_index))
        self._update_image_and_peaks()

    def _forward_button_clicked(self) -> None:
        # Manages clicks on the 'forward' button.
        self._stop_stream()
        if (self._current_frame_index + 1) < len(self._frame_list):
            self._current_frame_index += 1
        print("Showing frame {0} in the buffer".format(self._current_frame_index))
        self._update_image_and_peaks()

    def _stop_stream(self) -> None:
        # Disconnects from the OM monitor and stops receiving data.
        if self.listening:
            self._play_pause_button.setText("Play")
            self.stop_listening()

    def _start_stream(self) -> None:
        # Connects to the the OM monitor and starts receiving data.
        if not self.listening:
            self._play_pause_button.setText("Pause")
            self.start_listening()

    def _play_pause_button_clicked(self) -> None:
        # Manages clicks on the 'play/pause' button.
        if self.listening:
            self._stop_stream()
        else:
            self._start_stream()


@click.command()
@click.option(
    "--config",
    "-c",
    default="monitor.yaml",
    type=click.Path(),
    help="configuration file (default: monitor.yaml file in the current working "
    "directory",
)
@click.argument("url", type=str, required=False)
def main(*, url: str, config: str) -> None:
    """
    OM Parameter Tweaker for Crystallography. This program must connect to a running
    OnDA Monitor for Crystallography. If the monitor broadcasts detector frame data,
    this graphical interface will receive it. The user will be allowed to choose a set
    of peakfinding parameters which will then be applied to each received detector
    frame. Each frame will be displayed with its detected peaks. The data stream
    from the monitor can also be temporarily paused, and any of the last 10 displayed
    detector frames can be recalled and operated on. The purpose of this GUI is to
    allow the user to refine the peak finding parameters without interfering with
    with the OnDA Monitor observing the experiment.

    The GUI conects to and OnDA Monitor running at the IP address (or hostname)
    specified by the URL string. This is a string in the format used by the ZeroMQ
    Protocol. The URL string is optional. If not provided, URL defaults to
    tcp://127.0.0.1:12321 and the GUI connects, using the tcp protocol, to a monitor
    running on the local machine at port 12321.
    """
    # This function is turned into a script by the Click library. The docstring
    # above becomes the help string for the script.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    if url is None:
        url = "tcp://127.0.0.1:12321"

    monitor_parameters: parameters.MonitorParams = parameters.MonitorParams(config)

    app: Any = QtWidgets.QApplication(sys.argv)
    _ = CrystallographyParameterTweaker(url=url, monitor_parameters=monitor_parameters)
    sys.exit(app.exec_())
