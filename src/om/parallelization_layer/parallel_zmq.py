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


import multiprocessing
import sys
from typing import Any, Dict, List, Optional, Tuple

import zmq
from pydantic import BaseModel, ValidationError

from om.lib.exceptions import OmConfigurationFileSyntaxError, OmDataExtractionError
from om.lib.logging import log
from om.lib.protocols import (
    OmDataEventHandlerProtocol,
    OmDataRetrievalProtocol,
    OmParallelizationProtocol,
    OmProcessingProtocol,
)
from om.lib.zmq import get_current_machine_ip


class _OmParameters(BaseModel):
    node_pool_size: int


class _MonitorParameters(BaseModel):
    om: _OmParameters


def _om_processing_node(
    *,
    rank: int,
    node_pool_size: int,
    data_event_handler: OmDataEventHandlerProtocol,
    processing_layer: OmProcessingProtocol,
) -> None:
    context = zmq.Context()

    sender_push = context.socket(zmq.PUSH)
    sender_push.connect(f"tcp://{get_current_machine_ip()}:5555")

    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect(f"tcp://{get_current_machine_ip()}:5556")

    socket_sub.setsockopt_string(zmq.SUBSCRIBE, f"{rank}#")
    socket_sub.setsockopt_string(zmq.SUBSCRIBE, "all#")

    zmq_poller = zmq.Poller()
    zmq_poller.register(socket_sub, zmq.POLLIN)

    data_event_handler.initialize_event_handling_on_processing_node(
        node_rank=rank, node_pool_size=node_pool_size
    )

    processing_layer.initialize_processing_node(
        node_rank=rank, node_pool_size=node_pool_size
    )

    events = data_event_handler.event_generator(
        node_rank=rank,
        node_pool_size=node_pool_size,
    )

    event: Dict[str, Any]
    for event in events:
        feedback_dict: Dict[str, Any] = {}

        socks = dict(zmq_poller.poll(0))
        if socket_sub in socks and socks[socket_sub] == zmq.POLLIN:
            _ = socket_sub.recv_string()
            message: Dict[str, Any] = socket_sub.recv_pyobj()
            if "stop" in message:
                log.info(f"Shutting down RANK: {rank}.")
                sender_push.send_pyobj(({"stopped": True}, rank))
                return
            else:
                feedback_dict = message

        try:
            data: Dict[str, Any] = data_event_handler.extract_data(event=event)
        except OmDataExtractionError as exc:
            log.warning(f"{exc}")
            log.warning("Skipping event...")
            continue
        data.update(feedback_dict)
        processed_data: Tuple[Dict[str, Any], int] = processing_layer.process_data(
            node_rank=rank, node_pool_size=node_pool_size, data=data
        )
        sender_push.send_pyobj(processed_data)
        # Makes sure that the last MPI message has processed.

    # After finishing iterating over the events to process, calls the
    # end_processing function, and if the function returns something, sends it
    # to the processing node.
    final_data: Optional[Dict[str, Any]] = (
        processing_layer.end_processing_on_processing_node(
            node_rank=rank, node_pool_size=node_pool_size
        )
    )
    if final_data is not None:
        sender_push.send_pyobj((final_data, rank))

    # Sends a message to the collecting node saying that there are no more
    # events.
    end_dict = {"end": True}
    sender_push.send_pyobj((end_dict, rank))
    return


class ZmqParallelization(OmParallelizationProtocol):
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
        Multiprocessing-based Parallelization Layer for OM.

        This method overrides the corresponding method of the base class: please also
        refer to the documentation of that class for more information.

        This class implements a Parallelization Layer based on Python's multiprocessing
        module. Each processing node is spawned as a subprocess. The parent process
        acts as a collecting node and additionally manages the child processes. This
        method generates all the subprocesses, and sets up all the communication
        channels through which data and control commands are received and dispatched.

        Arguments:

            data_retrieval_layer: A class defining how data and data events are
                retrieved and handled.

            processing_layer: A class defining how retrieved data is processed.

            monitor_parameters: An object storing OM's configuration parameters.
        """

        # self._subscription_string: str = tag
        self._zmq_context: Any = zmq.Context()

        self._receiver_pull = self._zmq_context.socket(zmq.PULL)
        self._receiver_pull.bind(f"tcp://{get_current_machine_ip()}:5555")

        self._socket_pub = self._zmq_context.socket(zmq.PUB)
        self._socket_pub.bind(f"tcp://{get_current_machine_ip()}:5556")

        self._zmq_poller = zmq.Poller()
        self._zmq_poller.register(self._receiver_pull, zmq.POLLIN)

        self._data_event_handler: OmDataEventHandlerProtocol = (
            data_retrieval_layer.get_data_event_handler()
        )
        self._processing_layer: OmProcessingProtocol = processing_layer

        try:
            self._parameters: _MonitorParameters = _MonitorParameters.model_validate(
                parameters
            )
        except ValidationError as exception:
            raise OmConfigurationFileSyntaxError(
                "Error parsing the following section of OM's configuration parameters: "
                f"om"
                f"{exception}"
            )

        self._processing_nodes: List[multiprocessing.Process] = []

        processing_node_rank: int
        for processing_node_rank in range(1, self._parameters.om.node_pool_size):
            processing_node = multiprocessing.Process(
                target=_om_processing_node,
                kwargs={
                    "rank": processing_node_rank,
                    "node_pool_size": self._parameters.om.node_pool_size,
                    "data_event_handler": self._data_event_handler,
                    "processing_layer": self._processing_layer,
                },
            )
            self._processing_nodes.append(processing_node)

        self._rank: int = 0
        self._data_event_handler.initialize_event_handling_on_collecting_node(
            node_rank=self._rank, node_pool_size=self._parameters.om.node_pool_size
        )
        self._num_no_more: int = 0
        self._num_collected_events: int = 0
        print("debug ZMQ")

    def start(self) -> None:  # noqa: C901
        """
        Starts the multiprocessing parallelization.

        This method overrides the corresponding method of the base class: please also
        refer to the documentation of that class for more information.

        The function starts the nodes and manages all of their interactions
        """
        log.info(
            "You are using an OM real-time monitor. Please cite: "
            "Mariani et al., J Appl Crystallogr. 2016 May 23;49(Pt 3):1073-1080",
        )
        log.info("---")
        for processing_node in self._processing_nodes:
            processing_node.start()

        self._processing_layer.initialize_collecting_node(
            node_rank=self._rank, node_pool_size=self._parameters.om.node_pool_size
        )

        while True:
            try:
                socks = dict(self._zmq_poller.poll(0))
                if (
                    self._receiver_pull in socks
                    and socks[self._receiver_pull] == zmq.POLLIN
                ):
                    received_data: Tuple[Dict[str, Any], int] = (
                        self._receiver_pull.recv_pyobj()
                    )

                    if "end" in received_data[0]:
                        # If the received message announces that a processing node has
                        # finished processing data, keeps track of how many processing
                        # nodes have already finished.
                        log.info(f"Finalizing {received_data[1]}")
                        self._num_no_more += 1
                        # When all processing nodes have finished, calls the
                        # 'end_processing_on_collecting_node' function then shuts down.
                        if self._num_no_more == self._parameters.om.node_pool_size - 1:
                            log.info("All processing nodes have run out of events.")
                            log.info("Shutting down.")
                            self._processing_layer.end_processing_on_collecting_node(
                                node_rank=self._rank,
                                node_pool_size=self._parameters.om.node_pool_size,
                            )
                            for processing_node in self._processing_nodes:
                                processing_node.join()
                                # join() means wait for processing to close and
                                # terminate
                            sys.exit(0)
                        else:
                            continue
                    feedback_data: Optional[Dict[int, Dict[str, Any]]] = (
                        self._processing_layer.collect_data(
                            node_rank=self._rank,
                            node_pool_size=self._parameters.om.node_pool_size,
                            processed_data=received_data,
                        )
                    )
                    self._num_collected_events += 1
                    if feedback_data is not None:
                        receiving_rank: int
                        for receiving_rank in feedback_data.keys():
                            if receiving_rank == 0:
                                self._socket_pub.send_string("all#", zmq.SNDMORE)
                                self._socket_pub.send_pyobj(feedback_data[0])
                            else:
                                self._socket_pub.send_string(
                                    f"{receiving_rank}#", zmq.SNDMORE
                                )
                                self._socket_pub.send_pyobj(
                                    feedback_data[receiving_rank]
                                )
                else:
                    self._processing_layer.wait_for_data(
                        node_rank=self._rank,
                        node_pool_size=self._parameters.om.node_pool_size,
                    )

            except KeyboardInterrupt as exc:
                log.info("Received keyboard sigterm...")
                log.info(f"{str(exc)}")
                log.info("Shutting down.")
                self.shutdown()

    def shutdown(self, *, msg: str = "Reason not provided.") -> None:
        """
        Shuts down the multiprocessing parallelization.

        This method overrides the corresponding method of the base class: please also
        refer to the documentation of that class for more information.

        This function stops OM, closing all the communication channels between the
        nodes and managing a controlled shutdown of OM's resources. Additionally, it
        terminates the processing node subprocesses in an orderly fashion.

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
                # message_pipe: multiprocessing.connection.Connection
                # for message_pipe in self._message_pipes:
                # message_pipe.send({"stop": True})

                self._socket_pub.send_string("all#", zmq.SNDMORE)
                self._socket_pub.send_pyobj({"stop": True})
                num_shutdown_confirm = 0
                while True:
                    # message: Tuple[Dict[str, Any], int] = self._data_queue.get()
                    message: Tuple[Dict[str, Any], int] = (
                        self._receiver_pull.recv_pyobj()
                    )
                    if "stopped" in message[0]:
                        num_shutdown_confirm += 1
                    if num_shutdown_confirm == self._parameters.om.node_pool_size - 1:
                        break
                # When all the processing nodes have confirmed, shuts down the
                # collecting node.
                for processing_node in self._processing_nodes:
                    processing_node.join()
                sys.exit(0)
            except RuntimeError:
                # In case of error, crashes hard!
                for processing_node in self._processing_nodes:
                    processing_node.join()
                sys.exit(0)
