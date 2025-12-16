"""
This file registers the model with the Python SDK.
"""

from viam.components.camera import Camera
from viam.resource.registry import Registry, ResourceCreatorRegistration

from .data_replay import DataReplay

Registry.register_resource_creator(Camera.SUBTYPE, DataReplay.MODEL, ResourceCreatorRegistration(DataReplay.new, DataReplay.validate_config))
