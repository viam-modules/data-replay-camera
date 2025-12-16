"""
This file registers the model with the Python SDK.
"""

from viam.components.camera import Camera
from viam.resource.registry import Registry, ResourceCreatorRegistration

from .models.data_replay import DataReplay

Registry.register_resource_creator(
    Camera.API, 
    DataReplay.MODEL, 
    ResourceCreatorRegistration(DataReplay.new, DataReplay.validate_config)    
)
