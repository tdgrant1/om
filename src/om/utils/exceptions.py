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
# Copyright 2020 SLAC National Accelerator Laboratory
#
# Based on OnDA - Copyright 2014-2019 Deutsches Elektronen-Synchrotron DESY,
# a research centre of the Helmholtz Association.
"""
OM-specific exceptions and exception handling.

This module contains a set of python exceptions that are specific to OM, and a custom
exception handler that reports the OM exceptions in a simplified way.
"""
import sys
import traceback


class OmException(Exception):
    """
    Base class for OM exceptions.

    All other OM-specific exceptions should subclass from this exception.
    """


class OmConfigurationFileReadingError(OmException):
    """
    Raised if an error happens while reading the configuration file.
    """


class OmConfigurationFileSyntaxError(OmException):
    """
    Raised if there is a syntax error in the configuration file.
    """


class OmDataExtractionError(OmException):
    """
    Raised if an error happens during data extraction.
    """


class OmHdf5FileReadingError(OmException):
    """
    Raised if an error happens while reading an HDF5 file.
    """


class OmHdf5PathError(OmException):
    """
    Raised if an internal HDF5 path is not found.
    """


class OmHidraAPIError(OmException):
    """
    Raised if an error happens during a HiDRA API call.
    """


class OmInvalidSourceError(OmException):
    """
    Raised if the format of the source string is not valid.
    """


class OmInvalidDataBroadcastUrl(OmException):
    """
    Raised if the format of the data broadcasting URL is not valid.
    """


class OmMissingDataEventHandlerError(OmException):
    """
    The implementation of a data event handler cannot be found on the system.
    """


class OmMissingDataExtractionFunctionError(OmException):
    """
    Raised if a Data Extraction Function is not defined.
    """


class OmMissingDependencyError(OmException):
    """
    Raised if one of the dependencies of a module is not found on the system.
    """


class OmMissingEventHandlingFunctionError(OmException):
    """
    Raised if an Event Handling Function is not defined.
    """


class OmMissingLayerModuleFileError(OmException):
    """
    Raised if the python implementation of an OM layer cannot be found on the system.
    """


class OmMissingParameterError(OmException):
    """
    Raised if a parameter is missing from the configuration file.
    """


class OmMissingParameterGroupError(OmException):
    """
    Raised if a parameter group is missing from the configuration file.
    """


class OmMissingPsanaInitializationFunctionError(OmException):
    """
    Raised if a psana Detector Interface Initialization Function is not defined.
    """


class OmWrongParameterTypeError(OmException):
    """
    Raised if the type of the configuration parameter does not match the requested one.
    """


def om_exception_handler(parameter_type, value, traceback_):  # type: ignore
    """
    Custom OM exception handler.

    This function should never be called directly. Instead it should be used as a
    replacement for the standard exception handler. For all OM exceptions, this
    handler adds a label to the Exception and hides the stacktrace. All non-OM
    exceptions are instead reported normally.

    Arguments:

        parameter_type (Exception): exception type.

        value (str): exception value (the message that comes with the exception).

        traceback_ (str): traceback to be printed.
    """
    # TODO: Fix types.
    if issubclass(parameter_type, OmException):
        print("OM ERROR: {0}".format(value))
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(0)
    else:
        traceback.print_exception(parameter_type, value, traceback_)
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(0)
