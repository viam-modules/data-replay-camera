# Module data-replay-camera
Replay images from Viam Data Management as a camera.

## Model `viam-modules:camera:data-replay`
A camera component that returns images stored in Viam Data Management. Instead of streaming live sensor data, it **replays** previously captured images by returning the **next** matching image on every `get_image()` call.

---

## When to use this module
Use `data-replay-camera` when you want a camera-like component that:
- Feeds a dataset (or filtered slice of Data Management) into a pipeline that expects a camera
- Replays images deterministically (good for debugging, demos, and repeatable tests)

This module is **not** intended to be a high-throughput streaming camera.

---

## Quick start

### Configuration

#### Attribute template

```json
{
  "default_dataset_id": "<string>",
  "default_tags": ["<string>"],
  "default_labels": ["<string>"],
  "app_api_key_id": "<string>",
  "app_api_key": "<string>"
}
```

#### Example configuration

```json
{
  "default_dataset_id": "mydatasetid123",
  "default_tags": ["training", "indoors"],
  "default_labels": ["fish"],
  "app_api_key_id": "your-key-id-here",
  "app_api_key": "your-key-here"
}
```

### Attributes

| Name | Type | Inclusion | Description |
|------|------|----------|-------------|
| `default_dataset_id` | string | Optional | Default dataset ID. Can be overridden via `extra.dataset_id`. |
| `default_tags` | list | Optional | Default tag filter. Can be overridden via `extra.tags`. |
| `default_labels` | list | Optional | Default bounding-box label filter. Can be overridden via `extra.labels`. |
| `app_api_key_id` | string | **Required** | Viam app API key ID used to access Data Management. |
| `app_api_key` | string | **Required** | Viam app API key used to access Data Management. |

---

## How to use it

### Camera API
Implements the RDK Camera API:
- `get_image()`: returns the next image (wraps around after the last)
- `get_images()`: returns a single image per call (internally calls `get_image()`)

### `get_image()` overrides (via `extra`)
Pass any of the following in the `extra` dict to override configured defaults:

- `dataset_id` (string): overrides `default_dataset_id`
- `tags` (list of strings): overrides `default_tags`
- `labels` (list of strings): overrides `default_labels`

**Filters are combinable:** if you provide multiple (`dataset_id` + `tags` + `labels`), results must match **all** provided constraints.

Examples:

```python
camera.get_image()
camera.get_image(extra={"dataset_id": "mydatasetid123"})
camera.get_image(extra={"tags": ["dog", "cat"]})
camera.get_image(extra={"labels": ["mouse", "rat"]})
camera.get_image(extra={"dataset_id": "mydatasetid123", "tags": ["dog"], "labels": ["mouse"]})
```

---

## Behavior  

- **Replay order:** Each call returns the *next* image from the matched result set.
- **Wrap-around:** After the last image is returned, the next call returns the first image again.
- **Caching:** The module caches the list of matching images the first time a given filter combination is requested.
- **Refreshing results:** If dataset contents / tags / labels change, **restart or reconfigure** the component to refresh cached results.
- **Encoding:** Images are returned as **JPEG**.
- **No matches:** If the filter returns no images, `get_image()` raises an error.

---

## Prerequisites / links

- Tag images and create a dataset (tutorial):
  - https://docs.viam.com/data-ai/train/create-dataset/
- Data Management service overview:
  - https://docs.viam.com/data-ai/capture-data/capture-sync/
- Dataset label data:
  - https://docs.viam.com/data-ai/train/annotate-images/
