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
OM's configuration parameter management.

This module contains classes and functions that can be used to manage and validate a
set of OM's configuration parameters from a configuration file.
"""
from typing import Any, Dict, TextIO

import yaml  # type: ignore

from om.utils import exceptions


def get_parameter_from_parameter_group(
    *,
    group: Dict[str, Any],
    parameter: str,
    parameter_type: Any = None,
    required: bool = False,
) -> Any:
    """
    Extracts an OM's configuration parameter from a parameter group.

    This function extracts a single configuration parameter from a provided group of
    parameters. Optionally, it validates the type of the parameter according to the
    following rules:

    * If the `required` argument is True and the parameter cannot be found in the
        parameter group, this function will raise an exception.

    * If the `required` argument is False and the parameter cannot be found in the
        parameter group, this function will return None.

    * If a type is specified in the function call (the `parameter_type` argument
        is not None), this function will raise an exception if the type of the
        retrieved parameter does not match the specified one.

    Arguments:

        group: the parameter group from which the parameter should be extracted.

        parameter: The name of the parameter to retrieve.

        parameter_type: The type of the parameter to retrieve. If a type is specified
            here, the type of the retrieved parameter will be validated. Defaults to
            None.

        required: True if the parameter is strictly required and must be present
            in the parameter group. False otherwise. Defaults to False.

    Returns:

        The value of the requested parameter, or None, if the parameter was not
        found in the parameter group (and it is not required).

    Raises:

            OmMissingParameterError: Raised if the parameter is required but cannot be
                found in the parameter group.

            OmWrongParameterTypeError: Raised if the requested parameter type does not
                match the type of the configuration parameter.
    """
    ret: Any = group.get(parameter)
    if ret is None and required is True:
        raise exceptions.OmMissingParameterError(
            "Parameter {0} in group [{1}] was not found, but is "
            "required.".format(parameter, group["name"])
        )
    if ret is not None and parameter_type is not None:
        if parameter_type is str:
            if not isinstance(ret, str):
                raise exceptions.OmWrongParameterTypeError(
                    "Wrong type for parameter {0}: should be {1}, is "
                    "{2}.".format(
                        parameter,
                        str(parameter_type).split()[1][1:-2],
                        str(type(ret)).split()[1][1:-2],
                    )
                )
        elif parameter_type is float:
            if not isinstance(ret, float) and not isinstance(ret, int):
                raise exceptions.OmWrongParameterTypeError(
                    "Wrong type for parameter {0}: should be {1}, is "
                    "{2}.".format(
                        parameter,
                        str(parameter_type).split()[1][1:-2],
                        str(type(ret)).split()[1][1:-2],
                    )
                )
        elif not isinstance(ret, parameter_type):
            raise exceptions.OmWrongParameterTypeError(
                "Wrong type for parameter {0}: should be {1}, is {2}.".format(
                    parameter,
                    str(parameter_type).split()[1][1:-2],
                    str(type(ret)).split()[1][1:-2],
                )
            )

        return ret


class MonitorParams:
    """
    See documentation for the `__init__` function.
    """

    def __init__(self, config: str) -> None:
        """
        Storage, retrieval and validation of OnDA Monitor configuration parameters.

        This class stores a set of OM's configuration parameters, subdivided in groups.
        The parameters must be read from a configuration file written in YAML format.
        The class allows then single parameters or group of parameters to be retrieved,
        and optionally validated.

        Arguments:

            config: The absolute or relative path to a YAML-format configuration file.

        Raises:

            OMConfigurationFileSyntaxError: Raised if there is a syntax error in OM's
                configuration file.
        """

        self._monitor_params: Any = {}

        try:
            open_file: TextIO
            with open(config, "r") as open_file:
                self._monitor_params = yaml.safe_load(open_file)
        except OSError:
            raise exceptions.OmConfigurationFileReadingError(
                "Cannot open or read the configuration file {0}".format(config)
            )
        except yaml.parser.ParserError as exc:
            raise exceptions.OmConfigurationFileSyntaxError(
                "Syntax error in the configuration file: {0}".format(exc)
            ) from exc

        # Store group name within the group
        for group in self._monitor_params:
            self._monitor_params[group]["name"] = group

    def get_parameter_group(
        self,
        *,
        group: str,
    ) -> Any:
        """
        Retrieves an OM's configuration parameter group.

        This function retrieves a configuration group from the full set of OM's
        configuration parameters.

        Arguments:

            group: The name of the parameter group to retrieve.

        Returns:

            The parameter group, if it was found in the full set of configuration
            parameters.

        Raises:

            OmMissingParameterGroupError: Raised if the requested parameter group is
                not present in the full set of OM's configuration parameters.
        """
        if group not in self._monitor_params:
            raise exceptions.OmMissingParameterGroupError(
                "Parameter group [{0}] is not in the configuration file".format(group)
            )
        return self._monitor_params[group]

    def get_parameter(
        self,
        *,
        group: str,
        parameter: str,
        parameter_type: Any = None,
        required: bool = False,
    ) -> Any:
        """
        Retrieves an OM's configuration parameter.

        This function retrieves a single parameter from the full set of OM's
        configuration parameters. Optionally, it also validates the type of the
        parameter, according to the following rules:

        * If the value of the `required` argument is True and the parameter cannot be
          found in OM's configuration file, this function will raise an exception.

        * If the value of the `required` argument is False and the parameter cannot be
          found in OM's configuration file, this function will return None.

        * If a type is specified in the function call (i.e., the `parameter_type`
          argument is not None), this function will raise an exception if the type of
          the retrieved parameter does not match the specified one.

        Arguments:

            group: The name of the parameter group to which the parameter to retrieve
                belongs.

            parameter (str): The name of the parameter to retrieve.

            parameter_type: The type of the parameter to retrieve. If a type is
                specified in this argument, the type of the retrieved parameter will be
                validated. Defaults to None.

            required: True if the parameter is strictly required and must be present
                in OM's configuration file, False otherwise. Defaults to False.

        Returns:

            The value of the requested parameter, or None, if the parameter was not
            found in OM's configuration file (and it is not required).

        Raises:

            OmMissingParameterGroupError: Raised if the requested parameter group is
                not present in the full set configuration parameters.

            OmMissingParameterError: Raised if the parameter is required but cannot be
                found in the full set configuration parameters.

            OmWrongParameterTypeError: Raised if the requested parameter type does not
                match the type of the configuration parameter.
        """
        return get_parameter_from_parameter_group(
            group=self.get_parameter_group(group=group),
            parameter=parameter,
            parameter_type=parameter_type,
            required=required,
        )

    def get_param(
        self,
        group: str,
        parameter: str,
        parameter_type: Any = None,
        required: bool = False,
    ) -> Any:
        """
        Retrieves an OM's configuration parameter.

        WARNING: This function is deprecated and will be removed from a future version
        of OM. Please see the equivalent
        [get_parameter][om.utils.parameters.MonitorParams.get_parameter] function.

        Arguments:

            group: The name of the parameter group to which the parameter to retrieve
                belongs.

            parameter (str): The name of the parameter to retrieve.

            parameter_type: The type of the parameter to retrieve. If a type is
                specified in this argument, the type of the retrieved parameter will be
                validated. Defaults to None.

            required: True if the parameter is strictly required and must be present
                in OM's configuration file, False otherwise. Defaults to False.

        Returns:

            The value of the requested parameter, or None, if the parameter was not
            found in OM's configuration file (and it is not required).

        Raises:

            OmMissingParameterGroupError: Raised if the requested parameter group is
                not present in the full set configuration parameters.

            OmMissingParameterError: Raised if the parameter is required but cannot be
                found in the full set configuration parameters.

            OmWrongParameterTypeError: Raised if the requested parameter type does not
                match the type of the configuration parameter.
        """
        print(
            "OM Warning: the get_param method of the MonitorParams class is "
            "deprecated and will be removed in a future version of OM. If you are "
            "retrieving a parameter to initialize an algorithm, please use the "
            "get_parameter_group method and the new parameter group interface for the "
            "algorithm. If instead you are retrieving a single parameter, please use "
            "the get_parameter function."
        )
        return self.get_parameter(
            group=group,
            parameter=parameter,
            parameter_type=parameter_type,
            required=required,
        )
