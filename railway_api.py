import asyncio
import logging
from typing import List, Dict, Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent requests to railway API
API_SEMAPHORE = asyncio.Semaphore(5)  # adjust as needed
API_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

class RailwayAPIError(Exception):
    """Base exception for railway API errors."""
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
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with API_SEMAPHORE:
            url = f"{self.base_url}{endpoint}"
            logger.debug("Requesting %s with params %s", url, params)
            resp = await self.client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("response_code") != 200:
                logger.warning("API error %s: %s", data.get("response_code"), data)
                raise RailwayAPIError(data.get("message", "Unknown API error"))
            return data

    async def close(self):
        await self.client.aclose()

    async def get_train_schedule(self, train_number: str) -> Dict[str, Any]:
        """Fetch full route/schedule for a train."""
        logger.info("Fetching schedule for train %s", train_number)
        data = await self._get(settings.TRAIN_ENDPOINT, {"train": train_number})
        if not data.get("route"):
            raise TrainNotFoundError(f"Train {train_number} not found or has no route")
        return data

    async def get_station_details(self, station_query: str) -> Dict[str, Any]:
        """Resolve station name or code to official code and name."""
        logger.info("Resolving station %s", station_query)
        data = await self._get(settings.STATION_ENDPOINT, {"station": station_query})
        if not data.get("station"):
            raise StationNotFoundError(f"Station {station_query} not found")
        return data

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
        params = {
            "train": train_number,
            "source": source_code,
            "dest": dest_code,
            "date": journey_date,
            "class": travel_class,
            "quota": quota,
        }
        data = await self._get(settings.AVAILABILITY_ENDPOINT, params)
        return data

# Singleton instance
railway_api = RailwayAPI()

# Helper functions used by handlers
async def fetch_train_route(train_number: str) -> List[Dict[str, Any]]:
    """Return list of stations in order with code, name, day, arrival, departure."""
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