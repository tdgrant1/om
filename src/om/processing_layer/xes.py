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
# Copyright 2020 -2023 SLAC National Accelerator Laboratory
#
# Based on OnDA - Copyright 2014-2019 Deutsches Elektronen-Synchrotron DESY,
# a research centre of the Helmholtz Association.
"""
OnDA Monitor for X-ray Emission Spectroscopy.

This module contains an OnDA Monitor for X-ray Emission Spectroscopy experiments.
"""


from __future__ import absolute_import, division, print_function

from typing import Any, Dict, Optional, Tuple, Union

import numpy
from numpy.typing import NDArray
from pydantic import BaseModel, Field, ValidationError

from om.algorithms.xes import EnergySpectrumRetrieval
from om.lib.event_management import EventCounter
from om.lib.exceptions import OmConfigurationFileSyntaxError
from om.lib.geometry import GeometryInformation
from om.lib.logging import log
from om.lib.protocols import OmProcessingProtocol
from om.lib.xes import XesAnalysisAndPlots
from om.lib.zmq import ZmqDataBroadcaster, ZmqResponder


class _XesProcessingParameters(BaseModel):
    geometry_file: str
    time_resolved: bool
    data_broadcast_url: Optional[str] = Field(default=None)
    responding_url: Optional[str] = Field(default=None)
    speed_report_interval: int
    data_broadcast_interval: int
    hit_frame_sending_interval: Optional[int] = Field(default=None)
    non_hit_frame_sending_interval: Optional[int] = Field(default=None)


class _MonitorParameters(BaseModel):
    xes: _XesProcessingParameters


class XesProcessing(OmProcessingProtocol):
    """
    See documentation for the `__init__` function.
    """

    def __init__(self, *, parameters: Dict[str, Any]) -> None:
        """
        OnDA Monitor for X-ray Emission Spectroscopy.

        This Processing class implements and OnDA Monitor for X-ray Emission
        Spectroscopy experiments. The monitor processes camera data frames, extracting
        energy spectrum information. It then computes cumulative raw and smoothed
        spectral data information, broadcasting it to external programs (like
        [OM's XES GUI][om.graphical_interfaces.xes_gui.XesGui], for visualization. In
        time resolved experiments, the monitor can process spectra for pumped and dark
        events separately, and compute their difference. The monitor additionally
        computes and broadcasts sums of detector data frames.

        This monitor is designed to work with cameras or simple single-module
        detectors. It will not work with a segmented area detector.

        This class implements the interface described by its base Protocol class.
        Please see the documentation of that class for additional information about
        the interface.

        Arguments:

            parameters: An object storing OM's configuration parameters.
        """
        self._monitor_parameters: Dict[str, Any] = parameters

        try:
            self._parameters = _MonitorParameters.model_validate(
                self._monitor_parameters
            )
        except ValidationError as exception:
            raise OmConfigurationFileSyntaxError(
                "Error parsing OM's configuration parameters: " f"{exception}"
            )

        # Geometry
        self._geometry_information = GeometryInformation.from_file(
            geometry_filename=self._parameters.xes.geometry_file
        )

    def initialize_processing_node(
        self, *, node_rank: int, node_pool_size: int
    ) -> None:
        """
        Initializes the processing nodes for the XES Monitor.

        This function just initializes some internal counters.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.
        """
        # Frame sending
        self._send_hit_frame: bool = False
        self._send_non_hit_frame: bool = False

        self._energy_spectrum_retrieval: EnergySpectrumRetrieval = (
            EnergySpectrumRetrieval(
                parameters=self._monitor_parameters["xes"],
            )
        )

        # Console
        log.info(f"Processing node {node_rank} starting")

    def initialize_collecting_node(
        self, *, node_rank: int, node_pool_size: int
    ) -> None:
        """
        Initializes the collecting node for the XES Monitor.

        This function initializes the data analysis and accumulation algorithms and the
        storage buffers used to compute statistics on the aggregated spectral data.
        Additionally, it prepares all the necessary network sockets.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.
        """

        # Plots
        self._xes_analysis_and_plots = XesAnalysisAndPlots(
            parameters=self._monitor_parameters["xes"],
            time_resolved=self._parameters.xes.time_resolved,
        )

        # Data broadcast
        self._data_broadcast_socket: ZmqDataBroadcaster = ZmqDataBroadcaster(
            data_broadcast_url=self._parameters.xes.data_broadcast_url
        )

        # Responding socket
        self._responding_socket: ZmqResponder = ZmqResponder(
            responding_url=self._parameters.xes.responding_url
        )

        # Event counting
        self._event_counter: EventCounter = EventCounter(
            speed_report_interval=self._parameters.xes.speed_report_interval,
            data_broadcast_interval=self._parameters.xes.data_broadcast_interval,
            hit_frame_sending_interval=self._parameters.xes.hit_frame_sending_interval,
            non_hit_frame_sending_interval=(
                self._parameters.xes.non_hit_frame_sending_interval
            ),
            node_pool_size=node_pool_size,
        )

        # Console
        log.info("Starting the monitor...")

    def process_data(
        self, *, node_rank: int, node_pool_size: int, data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """
        Processes a detector data frame and extracts spectrum information.

        This function processes retrieved data events and prepares the data for
        transmission to to the collecting node.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.

            data: A dictionary containing the data that OM retrieved for the detector
                data frame being processed.

                * The dictionary keys describe the Data Sources for which OM has
                  retrieved data. The keys must match the source names listed in the
                  `required_data` entry of OM's `om` configuration parameter group.

                * The corresponding dictionary values must store the the data that OM
                  retrieved for each of the Data Sources.

        Returns:

            A tuple with two entries. The first entry is a dictionary storing the
                processed data that should be sent to the collecting node. The second
                entry is the OM rank number of the node that processed the information.
        """
        processed_data: Dict[str, Any] = {}
        camera_data: NDArray[numpy.float_] = data["detector_data"]

        # Mask the camera edges
        camera_data[camera_data.shape[0] // 2 - 1 : camera_data.shape[0] // 2 + 1] = 0
        camera_data[
            :,
            camera_data.shape[1] // 2 - 1 : camera_data.shape[1] // 2 + 1,
        ] = 0

        xes: Dict[str, NDArray[numpy.float_]] = (
            self._energy_spectrum_retrieval.calculate_spectrum(data=camera_data)
        )

        processed_data["timestamp"] = data["timestamp"]
        processed_data["spectrum"] = xes["spectrum"]
        processed_data["beam_energy"] = data["beam_energy"]
        processed_data["data_shape"] = data["detector_data"].shape
        processed_data["detector_data"] = camera_data
        if self._parameters.xes.time_resolved:
            processed_data["optical_laser_active"] = data["optical_laser_active"]
        else:
            processed_data["optical_laser_active"] = False
        return (processed_data, node_rank)

    def wait_for_data(
        self,
        *,
        node_rank: int,
        node_pool_size: int,
    ) -> None:
        """
        Receives and handles requests from external programs.

        This function receives requests from external programs over a network socket
        and reacts according to the nature of the request, sending data back to the
        source of the request or modifying the internal behavior of the monitor.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.

        """
        pass

    def collect_data(
        self,
        *,
        node_rank: int,
        node_pool_size: int,
        processed_data: Tuple[Dict[str, Any], int],
    ) -> Optional[Dict[int, Dict[str, Any]]]:
        """
        Computes statistics on aggregated spectrum data and broadcasts them.

        This method overrides the corresponding method of the base class: please also
        refer to the documentation of that class for more information.

        This function computes aggregated statistics on spectral data received from the
        processing nodes. It then broadcasts the aggregated information to external
        programs for visualization.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.

            processed_data (Tuple[Dict, int]): A tuple whose first entry is a
                dictionary storing the data received from a processing node, and whose
                second entry is the OM rank number of the node that processed the
                information.
        """
        del node_rank
        del node_pool_size
        received_data: Dict[str, Any] = processed_data[0]
        return_dict: Dict[int, Dict[str, Any]] = {}

        spectrum_for_gui = received_data["spectrum"]

        spectra_cumulative_sum: Optional[
            Union[NDArray[numpy.float_], NDArray[numpy.int_]]
        ]
        spectra_cumulative_sum_smoothed: Optional[NDArray[numpy.float_]]
        cumulative_2d: Optional[Union[NDArray[numpy.float_], NDArray[numpy.int_]]]
        spectra_cumulative_sum_pumped: Optional[NDArray[numpy.float_]]
        spectra_cumulative_sum_dark: Optional[NDArray[numpy.float_]]
        spectra_cumulative_sum_difference: Optional[NDArray[numpy.float_]]
        (
            spectra_cumulative_sum,
            spectra_cumulative_sum_smoothed,
            cumulative_2d,
            spectra_cumulative_sum_pumped,
            spectra_cumulative_sum_dark,
            spectra_cumulative_sum_difference,
        ) = self._xes_analysis_and_plots.update_plots(
            detector_data=received_data["detector_data"],
            optical_laser_active=received_data["optical_laser_active"],
        )

        if self._event_counter.should_broadcast_data():
            message: Dict[str, Any] = {
                "timestamp": received_data["timestamp"],
                "detector_data": cumulative_2d,
                "spectrum": spectrum_for_gui,
                "spectra_sum": spectra_cumulative_sum,
                "spectra_sum_smoothed": spectra_cumulative_sum_smoothed,
                "beam_energy": received_data["beam_energy"],
            }
            if self._parameters.xes.time_resolved:
                message["spectra_sum_pumped"] = spectra_cumulative_sum_pumped
                message["spectra_sum_dark"] = spectra_cumulative_sum_dark
                message["spectra_sum_difference"] = spectra_cumulative_sum_difference

            self._data_broadcast_socket.send_data(
                tag="omdata",
                message=message,
            )

        self._event_counter.report_speed()

        if return_dict:
            return return_dict
        return None

    def end_processing_on_processing_node(
        self, *, node_rank: int, node_pool_size: int
    ) -> Optional[Dict[str, Any]]:
        """
        Ends processing on the processing nodes for the XES Monitor.

        This function prints a message on the console and ends the processing.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.

        Returns:

            Usually nothing. Optionally, a dictionary storing information to be sent to
                the processing node.
        """
        log.info(f"Processing node {node_rank} shutting down.")
        return None

    def end_processing_on_collecting_node(
        self, *, node_rank: int, node_pool_size: int
    ) -> None:
        """
        Ends processing on the collecting node for the XES Monitor.

        This function prints a message on the console and ends the processing.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            node_rank: The OM rank of the current node, which is an integer that
                unambiguously identifies the current node in the OM node pool.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.
        """
        log.info(
            "Processing finished. OM has processed "
            f"{self._event_counter.get_num_events()} events in total."
        )
