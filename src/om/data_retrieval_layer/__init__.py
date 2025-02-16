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
OM's Data Retrieval Layer.

This package contains OM's Data Retrieval Layer, which takes care of retrieving data
and data events to be processed. Modules in this package contain functions and classes
for specific detectors, facilities or software frameworks.
"""


from .data_retrieval_files import (  # noqa: F401
    EigerFilesDataRetrieval,
    Jungfrau1MFilesDataRetrieval,
    Lambda1M5FilesDataRetrieval,
    RayonixMccdFilesDataRetrieval,
)
from .data_retrieval_zmq import Jungfrau1MZmqDataRetrieval  # noqa: F401
from .data_sources_files import (  # noqa: F401
    Eiger16MFiles,
    EventIdEiger16MFiles,
    EventIdFromFilePath,
    EventIdJungfrau1MFiles,
    EventIdLambda1M5Files,
    Jungfrau1MFiles,
    Lambda1M5Files,
    RayonixMccdSingleFrameFiles,
    TimestampFromFileModificationTime,
    TimestampJungfrau1MFiles,
)
from .data_sources_zmq import (  # noqa: F401
    EventIdJungfrau1MZmq,
    Jungfrau1MZmq,
    TimestampJungfrau1MZmq,
)

try:
    import fabio  # type: ignore  # noqa: F401

    from .data_retrieval_files import PilatusFilesDataRetrieval  # noqa: F401
    from .data_sources_files import PilatusSingleFrameFiles  # noqa: F401
except ModuleNotFoundError:
    pass


try:
    import psana  # type: ignore  # noqa: F401

    from .data_retrieval_psana import (  # noqa: F401
        CxiLclsCspadDataRetrieval,
        CxiLclsDataRetrieval,
        LclsEpix100DataRetrieval,
        MfxLclsDataRetrieval,
        MfxLclsRayonixDataRetrieval,
    )
    from .data_sources_psana import (  # noqa: F401
        AcqirisPsana,
        AreaDetectorPsana,
        AssembledDetectorPsana,
        BeamEnergyFromEpicsVariablePsana,
        BeamEnergyPsana,
        CspadPsana,
        DiodeTotalIntensityPsana,
        EpicsVariablePsana,
        EventIdPsana,
        EvrCodesPsana,
        LclsExtraPsana,
        OpalPsana,
        TimestampPsana,
        Wave8TotalIntensityPsana,
    )
except ModuleNotFoundError:
    pass

try:
    import asapo_consumer  # type: ignore  # noqa: F401

    from .data_retrieval_asapo import (  # noqa: F401
        EigerAsapoDataRetrieval,
        PilatusAsapoDataRetrieval,
    )
    from .data_sources_asapo import (  # noqa: F401
        BeamEnergyAsapo,
        DetectorDataAsapo,
        DetectorDistanceAsapo,
        EventIdAsapo,
        TimestampAsapo,
    )
except ModuleNotFoundError:
    ...

try:
    import PIL  # type: ignore  # noqa: F401

    from .data_retrieval_http import EigerHttpDataRetrieval  # noqa: F401
    from .data_sources_http import (  # noqa: F401
        Eiger16MHttp,
        EventIdEiger16MHttp,
        TimestampEiger16MHttp,
    )
except ModuleNotFoundError:
    pass
