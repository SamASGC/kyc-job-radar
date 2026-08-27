from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable
from job_radar.models import Job


class Source(ABC):
    @abstractmethod
    async def fetch(self) -> Iterable[Job]:
        raise NotImplementedError
