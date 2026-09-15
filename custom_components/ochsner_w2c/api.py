"""Direct asynchronous SOAP client for Ochsner W2C using HTTP Basic auth."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from xml.etree import ElementTree as ET

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)


class W2CApiError(Exception):
    """Raised when communication with the W2C module fails."""


class W2CApi:
    """Async SOAP client for Ochsner W2C using pre-emptive Basic auth."""

    def __init__(self, session: ClientSession, host: str, username: str, password: str, timeout: int = 60) -> None:
        self._session = session
        self._host = host.strip().rstrip("/")
        self._url = f"http://{self._host}/ws"
        self._auth = BasicAuth(username, password)
        self._timeout = timeout
        _LOGGER.debug("Initialising Ochsner W2C API: host=%s timeout=%ss auth=basic", self._host, timeout)

    @staticmethod
    def _envelope(body: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:ns="http://ws01.lom.ch/soap/">'
            f"<SOAP-ENV:Body>{body}</SOAP-ENV:Body></SOAP-ENV:Envelope>"
        )

    async def _post(self, soap_action: str, body: str) -> bytes:
        payload = self._envelope(body).encode("utf-8")
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "SOAPAction": soap_action,
        }
        _LOGGER.debug("SOAP request: host=%s action=%s auth=basic bytes=%s", self._host, soap_action, len(payload))
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.post(
                    self._url,
                    data=payload,
                    headers=headers,
                    auth=self._auth,
                ) as response:
                    _LOGGER.debug("SOAP response: action=%s status=%s content_type=%s", soap_action, response.status, response.headers.get("Content-Type", ""))
                    if response.status >= 400:
                        preview = (await response.text(errors="replace"))[:500]
                        _LOGGER.error("SOAP HTTP error: action=%s status=%s response_preview=%r", soap_action, response.status, preview)
                        response.raise_for_status()
                    data = await response.read()
                    _LOGGER.debug("SOAP request successful: action=%s response_bytes=%s", soap_action, len(data))
                    return data
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.error("SOAP timeout: host=%s action=%s", self._host, soap_action)
            raise W2CApiError(f"Timeout while calling {soap_action}") from err
        except ClientResponseError as err:
            _LOGGER.error("SOAP response error: host=%s action=%s status=%s message=%s", self._host, soap_action, err.status, err.message)
            raise W2CApiError(f"HTTP {err.status}: {err.message}") from err
        except ClientError as err:
            _LOGGER.error("SOAP client error: host=%s action=%s type=%s error=%r", self._host, soap_action, type(err).__name__, err)
            raise W2CApiError(f"{type(err).__name__}: {err}") from err

    @staticmethod
    def _value(xml_bytes: bytes) -> Any:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as err:
            preview = xml_bytes[:500].decode("utf-8", errors="replace")
            _LOGGER.error("Invalid SOAP XML: error=%s response_preview=%r", err, preview)
            raise W2CApiError(f"Invalid SOAP XML: {err}") from err
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == "value":
                text = (element.text or "").strip()
                if not text:
                    return None
                normalized = text.replace(",", ".")
                try:
                    return float(normalized) if "." in normalized else int(normalized)
                except ValueError:
                    return text
        preview = xml_bytes[:500].decode("utf-8", errors="replace")
        _LOGGER.error("SOAP response contains no value element: preview=%r", preview)
        raise W2CApiError("SOAP response contains no value element")

    async def read_oid(self, oid: str) -> Any:
        _LOGGER.debug("Reading W2C OID: %s", oid)
        body = f"<ns:getDpRequest><ref><oid>{oid}</oid><prop/></ref><startIndex>0</startIndex><count>-1</count></ns:getDpRequest>"
        value = self._value(await self._post("http://ws01.lom.ch/soap/listDP", body))
        _LOGGER.debug("W2C OID read successfully: oid=%s value=%s", oid, value)
        return value

    async def read_all(self, oids: list[str]) -> dict[str, Any]:
        _LOGGER.debug("Starting W2C read of %s OIDs", len(oids))
        result: dict[str, Any] = {}
        for oid in oids:
            try:
                result[oid] = await self.read_oid(oid)
            except W2CApiError:
                _LOGGER.exception("W2C read failed at OID: %s", oid)
                raise
        _LOGGER.debug("W2C read completed: %s values", len(result))
        return result

    async def write_oid(self, oid: str, value: Any) -> None:
        _LOGGER.debug("Writing W2C OID: oid=%s value=%s", oid, value)
        index = oid.rstrip("/").split("/")[-1]
        normalized = str(value).replace(",", ".")
        body = f"<ns:writeDpRequest><ref><oid>{oid}</oid><prop/></ref><dp><index>{index}</index><name/><prop/><desc/><value>{normalized}</value><unit/><timestamp>0</timestamp></dp></ns:writeDpRequest>"
        await self._post("http://ws01.lom.ch/soap/writeDP", body)
        _LOGGER.debug("W2C OID write successful: oid=%s", oid)
