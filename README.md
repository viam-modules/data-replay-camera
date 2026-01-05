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
  "dataset_id": "<string>",
  "tags": ["<string>"],
  "labels": ["<string>"]
}
```

#### Example configuration

```json
{
  "dataset_id": "demo",
  "tags": ["demo"],
  "labels": []
}
```

### Attributes

| Name | Type | Inclusion | Description |
|------|------|----------|-------------|
| `dataset_id` | string | Optional | Dataset ID to filter images. |
| `tags` | list | Optional | Tag filter for images. |
| `labels` | list | Optional | Bounding-box label filter for images. |

**Authentication:** This module automatically uses Viam-provided credentials when running as a module. No API keys need to be configured manually.

---

## How to use it

### Camera API
Implements the RDK Camera API:
- `get_image()`: returns the next image (wraps around after the last)
- `get_images()`: returns a single image per call (internally calls `get_image()`)

The camera returns images filtered by the configured `dataset_id`, `tags`, and `labels`. If multiple filters are provided, results must match **all** constraints.

Example usage:

```python
camera.get_image()
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
