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
OM's layer management.

This module contains classes and functions that mange OM's various data processing and
extraction layers.
"""

import importlib
import sys
from types import ModuleType
from typing import Literal, Type, Union, overload

from om.lib.exceptions import (
    OmMissingLayerClassError,
    OmMissingLayerModuleError,
)
from om.lib.protocols import (
    OmDataRetrievalProtocol,
    OmParallelizationProtocol,
    OmProcessingProtocol,
)


@overload
def import_class_from_layer(
    *, layer_name: Literal["processing_layer"], class_name: str
) -> Type[OmProcessingProtocol]:
    """ """
    ...


@overload
def import_class_from_layer(
    *, layer_name: Literal["data_retrieval_layer"], class_name: str
) -> Type[OmDataRetrievalProtocol]:
    """ """
    ...


@overload
def import_class_from_layer(
    *, layer_name: Literal["parallelization_layer"], class_name: str
) -> Type[OmParallelizationProtocol]:
    """ """
    ...


def import_class_from_layer(
    *,
    layer_name: Union[
        Literal["parallelization_layer"],
        Literal["data_retrieval_layer"],
        Literal["processing_layer"],
    ],
    class_name: str,
) -> Union[
    Type[OmParallelizationProtocol],
    Type[OmDataRetrievalProtocol],
    Type[OmProcessingProtocol],
]:
    """
    Imports a class from an OM's layer.

    This function imports a class, identified by the `class_name` argument, from a
    layer identified by the `layer_name` argument. The function looks for a python
    module containing the layer code in the current working directory first.
    Specifically, it looks for a python file with the same name as the layer. If the
    function cannot find the file, it imports the layer from OM's normal installation
    directories. It then proceeds to import the requested class from the layer module.

    Arguments:

        layer_name: The name of the layer from which the class should be imported.

        class_name: The name of the class to import.

    Returns:

        The imported class.

    Raises:

        OmMissingLayerClass: Raised if the requested class cannot be found in the
            specified Python module.

        OmMissingLayerModuleFile: Raised if the requested python module cannot be
            found.
    """

    try:
        imported_layer: ModuleType = importlib.import_module(name=layer_name)
    except ImportError:
        try:
            imported_layer = importlib.import_module(f"om.{layer_name}")
        except ImportError as exc:
            exc_type, exc_value = sys.exc_info()[:2]
            # TODO: Fix types
            if exc_type is not None:
                raise OmMissingLayerModuleError(
                    f"The python module file {layer_name}.py cannot be found or loaded "
                    f"due to the following error: "
                    f"{exc_type.__name__}: {exc_value}"
                ) from exc
    try:
        imported_class: Union[
            Type[OmParallelizationProtocol],
            Type[OmDataRetrievalProtocol],
            Type[OmProcessingProtocol],
        ] = getattr(imported_layer, class_name)
        return imported_class
    except AttributeError:
        raise OmMissingLayerClassError(
            f"The {class_name} class cannot be found in the {layer_name} layer."
        )
