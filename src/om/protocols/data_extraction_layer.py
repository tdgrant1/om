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
Data Extraction Layer's base classes.

This module contains base abstract classes for OM's Data Extraction Layer.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List

from om.utils import exceptions, parameters


class OmDataSource(ABC):
    """
    See documentation of the `__init__` function.
    """

    @abstractmethod
    def __init__(
        self,
        *,
        data_source_name: str,
        monitor_parameters: parameters.MonitorParams,
    ) -> None:
        """
        Base class for an OM's Data Source classes.

        Data Sources are classes that perform all the operations needed to retrieve
        data, in OM, from a specific sensor or detector. A data source can be anything
        from a simple diode or wave digitizer, to big x-ray or optical detector.

        A data source class must be initialized with the full set of OM's configuration
        parameters, from which information about the sensor will be extracted. An
        identifying name for the sensor must also be provided. A Data Source class
        always provides one method that prepares OM to read data from the sensor, and
        another one that retrieves data from it.

        This class is the base class from which every other Data Source class should
        inherit. All its methods are abstract. Each derived class must provide its own
        detector- or sensor-specific implementations.

        Arguments:

            data_source_name: A name that identifies the current data source. It is
                used, for example, in communications with the user or for the retrieval
                of a sensor's initialization parameters.

            monitor_parameters: An object storing OM's configuration parameters.
        """
        pass

    @abstractmethod
    def initialize_data_source(
        self,
    ) -> None:
        """
        Data source initialization.

        This method prepares OM to retrieve data from the sensor or detector, reading
        all the necessary configuration parameters and retrieving any additional
        required external data.
        """

    @abstractmethod
    def get_data(
        self,
        *,
        event: Dict[str, Any],
    ) -> Any:  # noqa: F821
        """
        Data Retrieval.

        This function retrieves all the data generated by the data source for the
        provided data event.

        Arguments:

            event: A dictionary storing the event data.

        Returns:

            Data from the sensor.
        """
        pass


class OmDataEventHandler(ABC):
    """
    See documentation of the `__init__` function.
    """

    def __init__(
        self,
        *,
        source: str,
        data_sources: Dict[str, OmDataSource],
        monitor_parameters: parameters.MonitorParams,
    ) -> None:
        """
        Base class for OM's Data Event Handler classes.

        Data Event Handlers are classes that deal, in OM, with data events and their
        sources. They have methods to initialize sources, retrieve events from them,
        open and close events, and examine their content.

        A Data Event Handler class must be initialized with a string describing its
        event source. Additionally, a set of Data Sources must be provided. They
        instruct the Data Event Handler on how to retrieve data from the events.

        This class is the base class from which every Data Event Handler should
        inherit. All its methods are abstract. Each derived class must provide its own
        specific implementations, tailored to a particular facility, detector or
        software framework.

        Arguments:

            source: A string describing the data event source.

            data_sources: A dictionary containing a set of Data Sources.

                * Each dictionary key must define the name of a data source.

                * The corresponding dictionary value must store the instance of the
                  [Data Source class][om.data_retrieval_layer.base.OmDataSource] that
                  describes the source.

            monitor_parameters: An object storing OM's configuration parameters.
        """
        pass

    @abstractmethod
    def initialize_event_handling_on_collecting_node(
        self, *, node_rank: int, node_pool_size: int
    ) -> None:
        """
        Initializes event handling on the collecting node.

        This function is called on the collecting node when OM starts, and initializes
        the event handling on the node.

        Arguments:

            node_rank: The rank, in the OM pool, of the processing node calling the
                function.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.
        """
        pass

    @abstractmethod
    def initialize_event_handling_on_processing_node(
        self, *, node_rank: int, node_pool_size: int
    ) -> None:
        """
        Initializes event handling on a processing node.

        This function is called on a processing node when OM starts. It configures the
        node to start retrieving and processing data events, and initializes all the
        relevant Data Sources.

        Arguments:

            node_rank: The rank, in the OM pool, of the processing node calling the
                function.

            node_pool_size: The total number of nodes in the OM pool, including all the
                processing nodes and the collecting node.
        """
        pass

    @abstractmethod
    def event_generator(
        self,
        *,
        node_rank: int,
        node_pool_size: int,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Retrieves events from the source.

        This function retrieves a series of data events from a source. OM calls this
        function on each processing node to start retrieving events. The function,
        which is a generator, returns an iterator over the events that the calling node
        should process.

        Arguments:

            node_rank: The rank, in the OM pool, of the processing node calling the
                function.

            node_pool_size: The total number of nodes in the OM pool, including
                all the processing nodes and the collecting node.

        Yields:

            A dictionary storing the data for the current event.
        """
        pass

    @abstractmethod
    def open_event(self, *, event: Dict[str, Any]) -> None:
        """
        Opens an event.

        This function processes a data event and makes its content accessible for OM.
        OM calls this function on each processing node before the
        [extract_data][om.data_retrieval_layer.base.OmDataEventHandler.extract_data]
        function.

        Arguments:

            event: A dictionary storing the event data.
        """
        pass

    @abstractmethod
    def close_event(self, *, event: Dict[str, Any]) -> None:
        """
        Closes an event.

        This function processes a data event and prepares it to be discarded by OM. OM
        calls this function on each processing node after the
        [extract_data][om.data_retrieval_layer.base.OmDataEventHandler.extract_data]
        function.

        Arguments:

            event: A dictionary storing the event data.
        """
        pass

    @abstractmethod
    def get_num_frames_in_event(self, *, event: Dict[str, Any]) -> int:
        """
        Gets the number of detector frames in an event.

        This function returns the number of detector frames stored in a data event. OM
        calls it after retrieving each event, to determine how many frames it contains.

        Arguments:

            event: A dictionary storing the event data.

        Returns:

            The number of frames in the event.
        """
        pass

    @abstractmethod
    def extract_data(
        self,
        *,
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extracts data from a frame stored in an event.

        This function extracts data from a frame stored in an event. It works by
        calling, one after the other, all the functions that retrieve data from the
        event's Data Sources, passing the event as input to each of them. The data
        extracted by each function is then returned to the caller.

        For data events with multiple frames, OM calls this function for each frame in
        the event in sequence. The function always passes the full event to each
        data extracting function: an internal flag keeps track of which  frame should
        be processed in each particular call.

        Arguments:

            event: A dictionary storing the event data.

        Returns:

            A dictionary storing the extracted data.

            * Each dictionary key identifies a Data Source in the event for which data
              has been retrieved.

            * The corresponding dictionary value stores the data extracted from the
              Data Source for the frame being processed.
        """
        pass

    @abstractmethod
    def initialize_frame_data_retrieval(self) -> None:
        """
        Initializes frame data retrievals.

        This function initializes the retrieval of a single standalone detector data
        frame, with all the information that refers to it, as opposed to a series of
        events and frames as OM usually does. The function can be called on any type
        of node in OM and even outside of an OnDA Monitor. It prepares the system to
        retrieve the data, initializing the Data Sources, etc.

        Arguments:

            event_id: a string that uniquely identifies a data event.

            frame_id: a string that identifies a particular frame within the data
                event.
        """
        pass

    @abstractmethod
    def retrieve_frame_data(self, event_id: str, frame_id: str) -> Dict[str, Any]:
        """
        Retrieves all data realted to the requested detector frame from an event.

        This function retrieves a standalone detector frame from a data event source,
        together with all the data related to it. Before this function can be called,
        frame data retrieval must be initialized by calling the
        [`initialize_frame_data_retrieval`][initialize_frame_data_retrieval] function.
        The function can then be used to retrieve data related to the data event and
        frame specified by the provided unique identifiers.

        Arguments:

            event_id: a string that uniquely identifies a data event.

            frame_id: a string that identifies a particular frame within the data
                event.

        Returns:

            All data related to the requested detector data frame.
        """
        pass


class OmDataRetrieval(ABC):
    """
    See documentation of the `__init__` function.
    """

    @abstractmethod
    def __init__(
        self,
        *,
        monitor_parameters: parameters.MonitorParams,
        source: str,
    ) -> None:
        """
        Base class for OM's Data Retrieval classes.

        Data Retrieval classes implement OM's Data Retrieval Layer for a specific
        beamline, experiment or facility. They dictate how data is retrieved and
        data events are managed.

        A Data Retrieval class must be initialized with a string describing a data
        event source, and the full set of OM's configuration parameters.

        This class is the base class from which every Data Retrieval class should
        inherit. All its methods are abstract. Each derived class must provide its own
        implementations tailored to a specific beamline, facility or experiment.

        Arguments:

            monitor_parameters: An object storing OM's configuration parameters.
            source: A string describing the data event source.
        """
        pass

    @abstractmethod
    def get_data_event_handler(self) -> OmDataEventHandler:
        """
        Retrieves the Data Event Handler used by the class.

        This function returns the Data Event Handler used by the Data Retrieval class
        to manipulate data events.

        Returns:

            The Data Event Handler used by the Data Retrieval class.
        """
        pass


def filter_data_sources(
    *,
    data_sources: Dict[str, OmDataSource],
    required_data: List[str],
) -> List[str]:
    """
    Selects only the required Data Sources.

    This function filters the list of all Data Sources associated with a
    Data Retrieval class, returning only the subset of Data Sources needed to retrieve
    the data requested by the user.

    Arguments:

        data_sources: A list containing the names of all
            Data Sources available for a Data Retrieval class.

        required_data: A list containing the names of the data items requested by the
            user.

    Returns:

        A list of Data Source names containing only the required Data Sources.
    """
    required_data_sources: List[str] = []
    entry: str
    for entry in required_data:
        if entry == "timestamp":
            continue
        if entry in data_sources:
            required_data_sources.append(entry)
        else:
            raise exceptions.OmMissingDataSourceClassError(
                f"Data source {entry} is not defined"
            )
    return required_data_sources
