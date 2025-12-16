import sys
from typing import Any, ClassVar, Dict, Final, List, Mapping, Optional, Sequence, Tuple, NamedTuple, cast
from typing_extensions import Self

from viam.media.utils.pil import viam_to_pil_image, pil_to_viam_image, CameraMimeType
from viam.app.viam_client import ViamClient
from viam.media.video import NamedImage, ViamImage
from viam.proto.common import ResponseMetadata
from viam.proto.component.camera import GetPropertiesResponse
from viam.rpc.dial import DialOptions


if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName, Vector3
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily
from viam.proto.app.data import Filter, TagsFilter
from viam.proto.app.data import BinaryID
from viam.utils import struct_to_dict

from viam.components.camera import Camera
from viam.logging import getLogger

from datetime import datetime, timezone
from google.protobuf.timestamp_pb2 import Timestamp
from PIL import Image
from io import BytesIO

class DataReplay(Camera, Reconfigurable):
    
    class Properties(NamedTuple):
        supports_pcd: bool = False
        intrinsic_parameters = None
        distortion_parameters = None
        mime_types : List[str] = [CameraMimeType.JPEG]
    
    MODEL: ClassVar[Model] = Model(ModelFamily("viam-modules", "camera"), "data-replay")
    
    camera_properties: Camera.Properties = Properties()

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.logger = getLogger(name)    
        
        # Initialize viam client  
        self.app_client: Optional[ViamClient] = None
        
        # Per-instance state (set mutable defaults)
        self.api_key_id: str = ""
        self.api_key: str = ""
        self.dataset_name: str = ""
        self.dataset_id: str = ""
        self.tags: List[str] = []
        self.labels: List[str] = []
        self.binary_ids: Dict[str, List] = {}
        self.image_index: Dict[str, int] = {}
        
    # Constructor
    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        my_class = cls(config.name)
        my_class.reconfigure(config, dependencies)
        return my_class

    @classmethod
    def _validate_api_key(cls, attrs: Dict[str, Any]) -> None:
        """Validates the required 'app_api_key' attribute."""
        api_key = attrs.get("app_api_key", "")
        if not api_key or not isinstance(api_key, str):
            raise ValueError("'app_api_key' is required and must be a non-empty string")

    @classmethod
    def _validate_api_key_id(cls, attrs: Dict[str, Any]) -> None:
        """Validates the required 'app_api_key_id' attribute."""
        api_key_id = attrs.get("app_api_key_id", "")
        if not api_key_id or not isinstance(api_key_id, str):
            raise ValueError("'app_api_key_id' is required and must be a non-empty string")

    @classmethod
    def _validate_dataset_id(cls, attrs: Dict[str, Any]) -> None:
        """Validates the optional 'default_dataset_id' attribute if present."""
        if "default_dataset_id" in attrs:
            dataset_id = attrs["default_dataset_id"]
            if not isinstance(dataset_id, str):
                raise TypeError("'default_dataset_id' must be a string")

    @classmethod
    def _validate_tags(cls, attrs: Dict[str, Any]) -> None:
        """Validates the optional 'default_tags' attribute if present."""
        if "default_tags" in attrs:
            tags = attrs["default_tags"]
            if not isinstance(tags, list):
                raise TypeError("'default_tags' must be a list")

    @classmethod
    def _validate_labels(cls, attrs: Dict[str, Any]) -> None:
        """Validates the optional 'default_labels' attribute if present."""
        if "default_labels" in attrs:
            labels = attrs["default_labels"]
            if not isinstance(labels, list):
                raise TypeError("'default_labels' must be a list")

    # Validates JSON Configuration
    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        """Validates the configuration for the data replay camera."""
        attrs = struct_to_dict(config.attributes)

        # Validate required attributes
        cls._validate_api_key(attrs)
        cls._validate_api_key_id(attrs)

        # Validate optional attributes (only if present)
        cls._validate_dataset_id(attrs)
        cls._validate_tags(attrs)
        cls._validate_labels(attrs)

        return [], []

    def _reconfigure_credentials(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures API credentials for Viam data management access."""
        self.api_key = attrs.get("app_api_key", "")
        self.api_key_id = attrs.get("app_api_key_id", "")

    def _reconfigure_dataset(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures the default dataset ID for image filtering."""
        self.dataset_id = attrs.get("default_dataset_id", "")

    def _reconfigure_tags(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures the default tags for image filtering."""
        self.tags = attrs.get("default_tags", [])

    def _reconfigure_labels(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures the default labels for image filtering."""
        self.labels = attrs.get("default_labels", [])

    # Handles attribute reconfiguration
    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        """Reconfigures the component with new configuration."""
        self.app_client = None 
        
        attrs = struct_to_dict(config.attributes)

        # Reset internal state
        self.image_index = {}
        self.binary_ids = {}

        # Reconfigure all components
        self._reconfigure_credentials(attrs)
        self._reconfigure_dataset(attrs)
        self._reconfigure_tags(attrs)
        self._reconfigure_labels(attrs)

        self.logger.info(f"Reconfigured: dataset_id={self.dataset_id or 'none'}, tags={len(self.tags)}, labels={len(self.labels)}")
    
    async def viam_connect(self) -> ViamClient:
        """Create a new Viam Cloud connection."""
        dial_options = DialOptions.with_api_key( 
            api_key=self.api_key,
            api_key_id=self.api_key_id
        )
        
        return await ViamClient.create_from_dial_options(dial_options)
    
    async def _ensure_connected(self) -> ViamClient:
        """Lazy connect - reuses existing connection."""
        if self.app_client is None:
            self.app_client = await self.viam_connect()
            self.logger.info("Connected to Viam Cloud")
            
        return self.app_client
        
    def filter_id(self, dataset_id, tags, labels):
        return dataset_id + '---' + ' '.join(tags) + ' '.join(labels)

    async def get_binary_ids(self, dataset_id, tags, labels):
        filter_id = self.filter_id(dataset_id, tags, labels)

        if not filter_id in self.binary_ids:
            # lookup ids from data management
            self.binary_ids[filter_id] = []

            filter_args = {}
            if dataset_id != "":
                filter_args['dataset_id'] = dataset_id
            if len(tags) > 0:
                filter_args['tags_filter'] =  TagsFilter(tags=tags)
            filter = Filter(**filter_args)
            if len(labels) > 0:
                filter_args['bbox_labels'] = labels
            filter = Filter(**filter_args)

            binary_args = {'filter': filter, 'include_binary_data': False}
            # we need to page through results
            done = False
            while not done:
                binary_ids = await self.app_client.data_client.binary_data_by_filter(**binary_args)
                if len(binary_ids[0]):
                    self.binary_ids[filter_id].extend(binary_ids[0])
                    binary_args['last'] = binary_ids[2]
                else:
                    done = True
        return self.binary_ids[filter_id]

    async def get_next_binary_image(self, dataset_id, tags, labels, binary_ids) -> Image:
        filter_id = self.filter_id(dataset_id, tags, labels)
        if not filter_id in self.image_index:
            self.image_index[filter_id] = 0
        
        binary_id = BinaryID(
            file_id = binary_ids[self.image_index[filter_id]].metadata.id,
            organization_id = binary_ids[self.image_index[filter_id]].metadata.capture_metadata.organization_id,
            location_id = binary_ids[self.image_index[filter_id]].metadata.capture_metadata.location_id
        )

        self.image_index[filter_id] = self.image_index[filter_id] + 1
        if (self.image_index[filter_id] >= len(binary_ids)):
            self.image_index[filter_id] = 0
        
        binary_data = await self.app_client.data_client.binary_data_by_ids(binary_ids=[binary_id])
        return Image.open(BytesIO(binary_data[0].binary))

    async def get_image(
        self, mime_type: str = "", *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs
    ) -> ViamImage:
        # Ensure connection to Viam Cloud
        await self._ensure_connected()

        dataset_id = self.dataset_id
        if extra != None and extra.get('dataset_id') != None:
            dataset_id = extra['dataset_id']
        tags = self.tags
        if extra != None and extra.get('tags') != None:
            tags = extra['tags']
        labels = self.labels
        if extra != None and extra.get('labels') != None:
            labels = extra['labels']

        binary_ids = await self.get_binary_ids(dataset_id, tags, labels)
        img = await self.get_next_binary_image(dataset_id, tags, labels, binary_ids)

        return pil_to_viam_image(img.convert('RGB'), CameraMimeType.JPEG)
    
    async def get_images(self, *, timeout: Optional[float] = None, **kwargs) -> Tuple[List[NamedImage], ResponseMetadata]:        
        viam_image = await self.get_image(timeout=timeout)
        
        ts = Timestamp()
        ts.FromDatetime(datetime.now(timezone.utc))
        
        return ([NamedImage(name="", image=viam_image)], ResponseMetadata(captured_at=ts))

    async def get_point_cloud(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs
    ) -> Tuple[bytes, str]:
        raise NotImplementedError()

    async def get_properties(self, *, timeout: Optional[float] = None, **kwargs) -> Properties:
        return self.camera_properties


