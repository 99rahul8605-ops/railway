import asyncio
import hashlib
import hmac
import logging
import os
import time
from typing import List, Dict, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

logger = logging.getLogger(__name__)

API_SEMAPHORE = asyncio.Semaphore(5)
API_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
SDK_VERSION = "1"

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
        self.signing_secret = settings.RAILWAY_SDK_SIGNING_SECRET
        self.client = httpx.AsyncClient(timeout=API_TIMEOUT)

    def _headers(self, method: str, path: str, payload: str = "") -> Dict[str, str]:
        # RailKit requires x-api-key PLUS a set of HMAC-signed headers on every
        # request. Missing/incorrect signed headers -> gateway returns a bare 404
        # (it hides the real route from unsigned requests), not a 401/403.
        if not self.api_key:
            return {}
        timestamp = str(int(time.time() * 1000))
        nonce = os.urandom(32).hex()
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        message = "\n".join(
            [method.upper(), path, timestamp, nonce, payload_hash, self.api_key]
        )
        signature = hmac.new(
            self.signing_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "x-api-key": self.api_key,
            "Accept": "application/json",
            "x-irctc-sdk-ts": timestamp,
            "x-irctc-sdk-nonce": nonce,
            "x-irctc-sdk-payload-sha256": payload_hash,
            "x-irctc-sdk-signature": signature,
            "x-irctc-sdk-version": SDK_VERSION,
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _get(self, path: str) -> Dict[str, Any]:
        async with API_SEMAPHORE:
            url = f"{self.base_url}{path}"
            logger.info("Requesting %s", url)
            resp = await self.client.get(url, headers=self._headers("GET", path))
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
        path = f"/api/getTrainInfo/{train_number}"
        data = await self._get(path)
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
        path = f"/api/getAvailability/{train_number}/{source_code}/{dest_code}/{journey_date}/{travel_class}/{quota}"
        data = await self._get(path)
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