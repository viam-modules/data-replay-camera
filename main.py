import asyncio
import sys

from viam.module.module import Module 

try:
    from src.models.data_replay import DataReplay
except ModuleNotFoundError:
    # when running as local module with run.sh
    from .models.data_replay import DataReplay  # noqa: F401

if __name__ == "__main__":
    asyncio.run(Module.run_from_registry())