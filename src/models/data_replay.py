import os, sys
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Tuple, NamedTuple
from typing_extensions import Self

from viam.app.viam_client import ViamClient
from viam.media.utils.pil import pil_to_viam_image, CameraMimeType
from viam.media.video import NamedImage, ViamImage
from viam.proto.common import ResponseMetadata
from viam.rpc.dial import DialOptions, Credentials


if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

from viam.components.camera import Camera
from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.proto.app.data import Filter, TagsFilter 
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily

from viam.utils import struct_to_dict
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
    def _validate_dataset_id(cls, attrs: Dict[str, Any]) -> None:
        """Validates the optional 'dataset_id' attribute if present."""
        if "dataset_id" in attrs:
            dataset_id = attrs["dataset_id"]
            if dataset_id is not None and not isinstance(dataset_id, str):
                raise TypeError("'dataset_id' must be a string")

    @classmethod
    def _validate_tags(cls, attrs: Dict[str, Any]) -> None:
        """Validates the optional 'tags' attribute if present."""
        if "tags" in attrs:
            tags = attrs["tags"]
            if tags is not None and not isinstance(tags, list):
                raise TypeError("'tags' must be a list")

    @classmethod
    def _validate_labels(cls, attrs: Dict[str, Any]) -> None:
        """Validates the optional 'labels' attribute if present."""
        if "labels" in attrs:
            labels = attrs["labels"]
            if labels is not None and not isinstance(labels, list):
                raise TypeError("'labels' must be a list")

    # Validates JSON Configuration
    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[Sequence[str], Sequence[str]]:
        """Validates the configuration for the data replay camera."""
        attrs = struct_to_dict(config.attributes)

        # Validate optional attributes (only if present)
        cls._validate_dataset_id(attrs)
        cls._validate_tags(attrs)
        cls._validate_labels(attrs)

        return [], []

    def _reconfigure_dataset(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures the dataset ID for image filtering."""
        self.dataset_id = attrs.get("dataset_id") or ""

    def _reconfigure_tags(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures the tags for image filtering."""
        self.tags = attrs.get("tags") or []

    def _reconfigure_labels(self, attrs: Dict[str, Any]) -> None:
        """Reconfigures the labels for image filtering."""
        self.labels = attrs.get("labels") or []

    # Handles attribute reconfiguration
    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        """Reconfigures the component with new configuration."""
        attrs = struct_to_dict(config.attributes)

        # Reset internal state
        self.image_index = {}
        self.binary_ids = {}

        # Reconfigure all components
        self._reconfigure_dataset(attrs)
        self._reconfigure_tags(attrs)
        self._reconfigure_labels(attrs)

        self.logger.info(f"Reconfigured: dataset_id={self.dataset_id or 'none'}, tags={len(self.tags)}, labels={len(self.labels)}")    

    @staticmethod
    def _get_viam_env_credentials() -> Tuple[str, str]:
        """Return (api_key, api_key_id) from module-injected env vars, or raise."""
        api_key = (os.environ.get("VIAM_API_KEY") or "").strip()
        api_key_id = (os.environ.get("VIAM_API_KEY_ID") or "").strip()

        if not api_key or not api_key_id:
            raise ValueError(
                "VIAM_API_KEY and VIAM_API_KEY_ID are not set. "
                "These are normally injected when running as a Viam module."
            )

        return api_key, api_key_id
    
    async def viam_connect(self) -> ViamClient:
        """Create a new Viam Cloud connection."""
        api_key, api_key_id = self._get_viam_env_credentials() 
        
        # Helpful debug logging for machine permissions check
        self.logger.debug(
            "machine=%s location=%s org=%s",
            os.getenv("VIAM_MACHINE_ID"),
            os.getenv("VIAM_LOCATION_ID"),
            os.getenv("VIAM_PRIMARY_ORG_ID"),
            )

        dial_options = DialOptions(
            credentials=Credentials(
                type="api-key",
                payload=api_key,
            ),
            auth_entity=api_key_id,
        )

        return await ViamClient.create_from_dial_options(dial_options)
    
    async def _ensure_connected(self) -> ViamClient:
        """Lazy connect - reuses existing connection."""
        if self.app_client is None:
            self.app_client = await self.viam_connect()
            self.logger.info("Connected to Viam Cloud")
            
        return self.app_client
        
    def filter_id(self, dataset_id, tags, labels):
        return f"{dataset_id}---{' '.join(tags)}{' '.join(labels)}"

    async def get_binary_ids(self, dataset_id, tags, labels):
        filter_id = self.filter_id(dataset_id, tags, labels)

        if filter_id not in self.binary_ids:
            # lookup ids from data management
            self.binary_ids[filter_id] = []

            filter_args = {}
            if dataset_id != "":
                filter_args['dataset_id'] = dataset_id
            if len(tags) > 0:
                filter_args['tags_filter'] = TagsFilter(tags=tags)
            if len(labels) > 0:
                filter_args['bbox_labels'] = labels
                
            filter = Filter(**filter_args)

            binary_args = {'filter': filter, 'include_binary_data': False}
            # we need to page through results
            done = False
            while not done:
                self.logger.debug(f"Querying dataset_id={dataset_id} tags={tags} labels={labels}")
                binary_ids = await self.app_client.data_client.binary_data_by_filter(**binary_args)
                self.logger.debug(f"Fetched {len(self.binary_ids[filter_id])} binary items for {filter_id}")
                
                if len(binary_ids[0]):
                    self.binary_ids[filter_id].extend(binary_ids[0])
                    binary_args['last'] = binary_ids[2]
                else:
                    done = True
        return self.binary_ids[filter_id]

    async def get_next_binary_image(self, dataset_id, tags, labels, binary_ids) -> Image:
        filter_id = self.filter_id(dataset_id, tags, labels)
            
        if filter_id not in self.image_index:
            self.image_index[filter_id] = 0

        if not binary_ids:
            raise ValueError(f"No binary images found for filter={filter_id}")    
            
        binary_data_id = binary_ids[self.image_index[filter_id]].metadata.binary_data_id
        
        self.image_index[filter_id] = (self.image_index[filter_id] + 1) % len(binary_ids)
        binary_data = await self.app_client.data_client.binary_data_by_ids(binary_ids=[binary_data_id])
        
        return Image.open(BytesIO(binary_data[0].binary))

    async def get_image(
        self, mime_type: str = "", *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs
    ) -> ViamImage:
        # Ensure connection to Viam Cloud
        await self._ensure_connected()

        binary_ids = await self.get_binary_ids(self.dataset_id, self.tags, self.labels)
        img = await self.get_next_binary_image(self.dataset_id, self.tags, self.labels, binary_ids)

        return pil_to_viam_image(img.convert('RGB'), CameraMimeType.JPEG)
    


    async def get_images(
        self, 
        *,
        timeout: Optional[float] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        extra: Optional[Mapping[str, Any]] = None,
        filter_source_names: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[List[NamedImage], ResponseMetadata]:
        # Apply filtering if specified - if filter is provided and our camera name is not in it, return empty
        if filter_source_names and self.name not in filter_source_names:
            # Return empty result + empty metadata
            return [], ResponseMetadata()
        
        viam_image: ViamImage = await self.get_image(timeout=timeout)
        
        ts = Timestamp()
        ts.FromDatetime(datetime.now(timezone.utc))
        
        named_image = NamedImage(
            name=self.name,
            data=viam_image.data,
            mime_type=viam_image.mime_type,
        )

        return [named_image], ResponseMetadata()

    async def get_point_cloud(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, **kwargs
    ) -> Tuple[bytes, str]:
        raise NotImplementedError()

    async def get_properties(self, *, timeout: Optional[float] = None, **kwargs) -> Properties:
        return self.camera_properties


