# data-replay camera modular service

*data-replay* is a Viam modular service that provides camera capabilities, returning images from a [Viam dataset](https://docs.viam.com/tutorials/services/data-mlmodel-tutorial/#tag-images-and-create-a-dataset) based on a dataset ID, or from [Viam Data Management](https://docs.viam.com/services/data/) filtered by [tags](https://docs.viam.com/tutorials/services/data-mlmodel-tutorial/#tag-images-and-create-a-dataset) or [labels](https://docs.viam.com/services/data/dataset/#label-data).

The model this module makes available is *viam-modules:camera:data-replay*

## Prerequisites

If using a dataset, you must have created a dataset using [Viam Data Management](https://docs.viam.com/tutorials/services/data-mlmodel-tutorial/#the-data-management-service).

## API

The data-replay resource implements the [RDK camera API](https://github.com/rdk/camera-api), specifically get_image().

### get_image

On each get_image() call, the next image (default search order) will be returned.
After the last image is returned, the next get_image() call will return the first image from the dataset, tag or label filter.

Note that currently, the module must be reconfigured or restarted in order for the images in the dataset/filter/tag to be re-loaded.
Also, if a dataset or tag filter has many results, it is possible this module may consume too much memory storing image metadata.

The following can be passed via the *get_image()* extra parameter:

#### dataset_id (string)

The dataset_id to return images from.
This overrides the default_dataset_id.

#### tags (list)

The tag names to filter by.
This overrides default_tags.

#### labels (list)

The bounding box label names to filter by.
This overrides default_labels.

Examples:

```python
camera.get_image() # returns the next image from the dataset specified via config default_dataset_id
camera.get_image(extra={"dataset_id":"mydatasetid123"}) # returns the next image from the dataset id "mydatasetid123"
camera.get_image(extra={"tags":["dog", "cat"]}) # returns the next image from images with the tags dog or cat
camera.get_image(extra={"labels":["mouse", "rat"]}) # returns the next image from images with the labels mouse or rat
```

## Viam Service Configuration

Example attribute configuration:

```json
{
    "default_dataset_id": "mydatasetid123",
    "app_api_key_id": "xyz123",
    "app_api_key": "keyid"
}
```

### Attributes

The following attributes are available for `viam-modules:camera:data-replay` model:

| Name | Type | Inclusion | Description |
| ---- | ---- | --------- | ----------- |
| `default_dataset_id` | string | |  Default dataset ID. Can be overridden via extra params on get_image() calls. |
| `default_tags` | list | |  Default tag list. Can be overridden via extra params on get_image() calls. |
| `default_labels` | list | |  Default label list. Can be overridden via extra params on get_image() calls. |
| `app_api_key_id` | string | **Required** |  Viam app key id. Required in order to read data from Viam data management. |
| `app_api_key` | string | **Required** |  Viam app key. Required in order to read data from Viam data management. |
