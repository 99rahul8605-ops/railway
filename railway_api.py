import asyncio
import logging
from typing import List, Dict, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)

API_SEMAPHORE = asyncio.Semaphore(5)
API_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

class RailwayAPIError(Exception):
    pass

class TrainNotFoundError(RailwayAPIError):
    pass

class StationNotFoundError(RailwayAPIError):
    pass

class AvailabilityError(RailwayAPIError):
    pass

class RailwayAPI:
    def __init__(self):
        self.base_url = settings.RAILWAY_API_BASE_URL.rstrip("/")
        self.api_key = settings.RAILWAY_API_KEY
        self.client = httpx.AsyncClient(timeout=API_TIMEOUT)

    def _headers(self) -> Dict[str, str]:
        # railkit uses x-api-key header
        return {"x-api-key": self.api_key} if self.api_key else {}

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _get(self, url: str) -> Dict[str, Any]:
        async with API_SEMAPHORE:
            logger.info("Requesting %s", url)
            resp = await self.client.get(url, headers=self._headers())
            if resp.status_code >= 400:
                logger.error(
                    "RailKit request failed: %s -> %s %s",
                    url,
                    resp.status_code,
                    resp.text[:500],
                )
            resp.raise_for_status()
            data = resp.json()
            # railkit returns {success: bool, data: ..., message: ...}
            if not data.get("success"):
                raise RailwayAPIError(data.get("message", "API error"))
            return data.get("data", data)

    async def close(self):
        await self.client.aclose()

    async def get_train_schedule(self, train_number: str) -> Dict[str, Any]:
        """Fetch full route/schedule for a train."""
        logger.info("Fetching schedule for train %s", train_number)
        url = f"{self.base_url}/getTrainInfo/{train_number}"
        data = await self._get(url)
        # expect data.route list
        if not data.get("route"):
            raise TrainNotFoundError(f"Train {train_number} not found or has no route")
        return data

    async def get_station_details(self, station_query: str) -> Dict[str, Any]:
        """Resolve station name or code to official code and name.
        Railkit does not expose a direct station lookup; we accept station code directly.
        """
        logger.info("Resolving station %s (assuming code)", station_query)
        # Return minimal structure; caller expects .station.code/.name
        return {"station": {"code": station_query.upper(), "name": station_query.upper()}}

    async def get_seat_availability(
        self,
        train_number: str,
        source_code: str,
        dest_code: str,
        journey_date: str,
        travel_class: str,
        quota: str = "GN",
    ) -> Dict[str, Any]:
        """Check seat availability for a specific class."""
        logger.info(
            "Checking availability %s -> %s on %s class %s quota %s",
            source_code,
            dest_code,
            journey_date,
            travel_class,
            quota,
        )
        url = f"{self.base_url}/getAvailability/{train_number}/{source_code}/{dest_code}/{journey_date}/{travel_class}/{quota}"
        data = await self._get(url)
        return data

railway_api = RailwayAPI()

async def fetch_train_route(train_number: str) -> List[Dict[str, Any]]:
    data = await railway_api.get_train_schedule(train_number)
    return data.get("route", [])

async def resolve_station(query: str) -> Dict[str, str]:
    data = await railway_api.get_station_details(query)
    station = data.get("station", {})
    return {"code": station.get("code"), "name": station.get("name")}

async def check_availability(
    train_number: str,
    source_code: str,
    dest_code: str,
    journey_date: str,
    travel_class: str,
    quota: str = "GN",
) -> Dict[str, Any]:
    return await railway_api.get_seat_availability(
        train_number, source_code, dest_code, journey_date, travel_class, quota
    )