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
MPI-based Parallelization Layer for OM.

This module contains a Parallelization Layer based on the MPI protocol.
"""


import sys
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from mpi4py import MPI

from om.lib.exceptions import OmDataExtractionError
from om.lib.logging import log
from om.lib.protocols import (
    OmDataEventHandlerProtocol,
    OmDataRetrievalProtocol,
    OmParallelizationProtocol,
    OmProcessingProtocol,
)


class MpiTags(int, Enum):
    die = 999
    dead = 1000
    data = 1001
    feedback = 1002


# Define some labels for internal MPI communication (just some syntactic sugar).


class MpiParallelization(OmParallelizationProtocol):
    """
    See documentation of the `__init__` function.
    """

    def __init__(
        self,
        *,
        data_retrieval_layer: OmDataRetrievalProtocol,
        processing_layer: OmProcessingProtocol,
        parameters: Dict[str, Any],
    ) -> None:
        """
        MPI-based Parallelization Layer for OM.

        This class implements a Parallelization Layer based on the MPI protocol. The
        nodes communicate with each other using an implementation of the MPI protocol
        supported by the Python language (OpenMPI or MPICH).

        This class implements the interface described by its base Protocol class.
        Please see the documentation of that class for additional information about
        the interface.

        Arguments:

            data_retrieval_layer: A class defining how data and data events are
                retrieved and handled.

            processing_layer: A class defining how retrieved data is processed.

            monitor_parameters: An object storing OM's configuration parameters.
        """
        del parameters
        self._data_event_handler: OmDataEventHandlerProtocol = (
            data_retrieval_layer.get_data_event_handler()
        )
        self._processing_layer: OmProcessingProtocol = processing_layer
        self._mpi_size: int = MPI.COMM_WORLD.Get_size()
        self._rank: int = MPI.COMM_WORLD.Get_rank()

        if self._rank == 0:
            self._data_event_handler.initialize_event_handling_on_collecting_node(
                node_rank=self._rank, node_pool_size=self._mpi_size
            )
            self._num_no_more: int = 0
            self._num_collected_events: int = 0
        else:
            self._data_event_handler.initialize_event_handling_on_processing_node(
                node_rank=self._rank, node_pool_size=self._mpi_size
            )

    def start(self) -> None:  # noqa: C901
        """
        Starts the MPI parallelization.

        This function sets up the communication between OM's collecting and processing
        nodes using the MPI protocol. The function starts the nodes and manages all of
        their interactions, organizing the receiving and dispatching of data and
        control commands over MPI channels.

        Please see the documentation of the base Protocol class for additional
        information about this method.
        """
        if self._rank == 0:
            log.info(
                "You are using an OM real-time monitor. Please cite: "
                "Mariani et al., J Appl Crystallogr. 2016 May 23;49(Pt 3):1073-1080",
            )
            log.info("---")
            self._processing_layer.initialize_collecting_node(
                node_rank=self._rank, node_pool_size=self._mpi_size
            )

            req: Any = 0

            while True:
                try:
                    if MPI.COMM_WORLD.Iprobe(source=MPI.ANY_SOURCE, tag=MpiTags.data):
                        received_data: Tuple[Dict[str, Any], int] = MPI.COMM_WORLD.recv(
                            source=MPI.ANY_SOURCE, tag=MpiTags.data
                        )
                        if "end" in received_data[0].keys():
                            # If the received message announces that a processing node
                            # has finished processing data, keeps track of how many
                            # processing nodes have already finished.
                            log.info(f"{received_data[1]}")
                            self._num_no_more += 1
                            # When all processing nodes have finished, calls the
                            # 'end_processing_on_collecting_node' function then shuts
                            # down.
                            if self._num_no_more == self._mpi_size - 1:
                                log.info("All processing nodes have run out of events.")
                                log.info("Shutting down.")
                                self._processing_layer.end_processing_on_collecting_node(  # noqa: E501
                                    node_rank=self._rank, node_pool_size=self._mpi_size
                                )
                                MPI.Finalize()
                                exit(0)
                            else:
                                continue
                        feedback_data: Optional[Dict[int, Dict[str, Any]]] = (
                            self._processing_layer.collect_data(
                                node_rank=self._rank,
                                node_pool_size=self._mpi_size,
                                processed_data=received_data,
                            )
                        )
                        self._num_collected_events += 1
                        if feedback_data is not None:
                            receiving_rank: int
                            for receiving_rank in feedback_data.keys():
                                if receiving_rank == 0:
                                    target_rank: int
                                    for target_rank in range(1, self._mpi_size):
                                        if req:
                                            req.Wait()
                                        req = MPI.COMM_WORLD.isend(
                                            feedback_data[0],
                                            dest=target_rank,
                                            tag=MpiTags.feedback,
                                        )
                                else:
                                    if req:
                                        req.Wait()
                                    req = MPI.COMM_WORLD.isend(
                                        feedback_data[receiving_rank],
                                        dest=receiving_rank,
                                        tag=MpiTags.feedback,
                                    )
                    else:
                        self._processing_layer.wait_for_data(
                            node_rank=self._rank, node_pool_size=self._mpi_size
                        )

                except KeyboardInterrupt as exc:
                    log.info("Received keyboard sigterm...")
                    log.info(str(exc))
                    log.info("shutting down.")
                    self.shutdown()
                    log.info("---> execution finished.")
                    sys.exit(0)
        else:
            self._processing_layer.initialize_processing_node(
                node_rank=self._rank, node_pool_size=self._mpi_size
            )

            # Flag used to make sure that the MPI messages have been processed.
            req = None
            events = self._data_event_handler.event_generator(
                node_rank=self._rank,
                node_pool_size=self._mpi_size,
            )

            event: Dict[str, Any]
            for event in events:
                # Listens for requests to shut down.
                if MPI.COMM_WORLD.Iprobe(source=0, tag=MpiTags.die):
                    self.shutdown(msg=f"Shutting down RANK: {self._rank}.")

                feedback_dict: Dict[str, Any] = {}
                if MPI.COMM_WORLD.Iprobe(source=0, tag=MpiTags.feedback):
                    feedback_dict = MPI.COMM_WORLD.recv(source=0, tag=MpiTags.feedback)

                try:
                    data: Dict[str, Any] = self._data_event_handler.extract_data(
                        event=event
                    )
                except OmDataExtractionError as exc:
                    log.warning(f"{exc}")
                    log.warning("Skipping event...")
                    continue
                data.update(feedback_dict)
                processed_data: Tuple[Dict[str, Any], int] = (
                    self._processing_layer.process_data(
                        node_rank=self._rank, node_pool_size=self._mpi_size, data=data
                    )
                )
                if req:
                    req.Wait()
                req = MPI.COMM_WORLD.isend(processed_data, dest=0, tag=MpiTags.data)
                # Makes sure that the last MPI message has processed.
                if req:
                    req.Wait()

            # After finishing iterating over the events to process, calls the
            # end_processing function, and if the function returns something, sends it
            # to the processing node.
            final_data: Optional[Dict[str, Any]] = (
                self._processing_layer.end_processing_on_processing_node(
                    node_rank=self._rank, node_pool_size=self._mpi_size
                )
            )
            if final_data is not None:
                if req:
                    req.Wait()
                req = MPI.COMM_WORLD.isend(
                    (final_data, self._rank), dest=0, tag=MpiTags.data
                )
                if req:
                    req.Wait()

            # Sends a message to the collecting node saying that there are no more
            # events.
            end_dict = {"end": True}
            if req:
                req.Wait()
            req = MPI.COMM_WORLD.isend((end_dict, self._rank), dest=0, tag=MpiTags.data)
            if req:
                req.Wait()
            MPI.Finalize()
            exit(0)

    def shutdown(self, *, msg: str = "Reason not provided.") -> None:
        """
        Shuts down the MPI parallelization.

        This function stops OM, closing all the communication channels between the
        nodes and managing a controlled shutdown of OM's resources. Additionally, it
        terminates the MPI processes in an orderly fashion.

        Please see the documentation of the base Protocol class for additional
        information about this method.

        Arguments:

            msg: Reason for shutting down. Defaults to "Reason not provided".
        """
        log.info(f"Shutting down: {msg}")
        if self._rank == 0:
            # Tells all the processing nodes that they need to shut down, then waits
            # for confirmation. During the whole process, keeps receiving normal MPI
            # messages from the nodes (MPI cannot shut down if there are unreceived
            # messages).
            try:
                node_num: int
                for node_num in range(1, self._mpi_size):
                    MPI.COMM_WORLD.isend(0, dest=node_num, tag=MpiTags.die)
                num_shutdown_confirm = 0
                while True:
                    if MPI.COMM_WORLD.Iprobe(source=MPI.ANY_SOURCE, tag=MpiTags.data):
                        _ = MPI.COMM_WORLD.recv(source=MPI.ANY_SOURCE, tag=MpiTags.data)
                    if MPI.COMM_WORLD.Iprobe(source=MPI.ANY_SOURCE, tag=MpiTags.data):
                        num_shutdown_confirm += 1
                    if num_shutdown_confirm == self._mpi_size - 1:
                        break
                # When all the processing nodes have confirmed, shuts down the
                # collecting node.
                MPI.Finalize()
                exit(0)
            except RuntimeError:
                # In case of error, crashes hard!
                MPI.COMM_WORLD.Abort(0)
                exit(0)
        else:
            MPI.COMM_WORLD.send(None, dest=0, tag=MpiTags.dead)
            MPI.Finalize()
            exit(0)
