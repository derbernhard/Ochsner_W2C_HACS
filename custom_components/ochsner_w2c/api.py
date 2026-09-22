"""Direct asynchronous SOAP client for Ochsner W2C using HTTP Basic auth."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from xml.etree import ElementTree as ET

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)

NS = "[ws01.lom.ch](http://ws01.lom.ch/soap/)"
ACTION_LIST = "[ws01.lom.ch](http://ws01.lom.ch/soap/listDP)"
ACTION_WRITE = "[ws01.lom.ch](http://ws01.lom.ch/soap/writeDP)"


class W2CApiError(Exception):
    """Raised when communication with the W2C module fails."""


class W2CApi:
    """Async SOAP client for Ochsner W2C using pre-emptive Basic auth."""

    def __init__(self, session: ClientSession, host: str, username: str, password: str, timeout: int = 60) -> None:
        if not hasattr(session, "post"):
            raise W2CApiError(
                "W2CApi erwartet eine aiohttp ClientSession. "
                "Bitte async_get_clientsession(hass) verwenden, nicht hass selbst."
            )
        self._session = session
        self._host = host.strip().rstrip("/")
        self._url = f"[{self._host}](http://{self._host}/ws)"
        self._auth = BasicAuth(username, password)
        self._timeout = timeout
        _LOGGER.debug("Initialising Ochsner W2C API: host=%s timeout=%ss auth=basic", self._host, timeout)

    @staticmethod
    def _envelope(body: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<SOAP-ENV:Envelope xmlns:SOAP-ENV="[schemas.xmlsoap.org](http://schemas.xmlsoap.org/soap/envelope/)" '
            'xmlns:SOAP-ENC="[schemas.xmlsoap.org](http://schemas.xmlsoap.org/soap/encoding/)" '
            'xmlns:xsi="[w3.org](http://www.w3.org/2001/XMLSchema-instance)" '
            'xmlns:xsd="[w3.org](http://www.w3.org/2001/XMLSchema)" '
            f'xmlns:ns="{NS}">'
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
                    _LOGGER.debug(
                        "SOAP response: action=%s status=%s content_type=%s",
                        soap_action, response.status, response.headers.get("Content-Type", ""),
                    )
                    if response.status >= 400:
                        preview = (await response.text(errors="replace"))[:500]
                        _LOGGER.error(
                            "SOAP HTTP error: action=%s status=%s response_preview=%r",
                            soap_action, response.status, preview,
                        )
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
            _LOGGER.error("SOAP response is not valid XML: preview=%r", preview)
            raise W2CApiError(f"Malformed SOAP response: {err}") from err

        for path in (f".//{{{NS}}}value", ".//value"):
            el = root.find(path)
            if el is not None and el.text is not None:
                text = el.text.strip()
                try:
                    return float(text.replace(",", "."))
                except ValueError:
                    return text

        preview = xml_bytes[:500].decode("utf-8", errors="replace")
        _LOGGER.error("SOAP response contains no value element: preview=%r", preview)
        raise W2CApiError("SOAP response contains no value element")

    async def read_oid(self, oid: str) -> Any:
        _LOGGER.debug("Reading W2C OID: %s", oid)
        body = f"<ns:getDpRequest><ref><oid>{oid}</oid><prop/></ref><startIndex>0</startIndex><count>-1</count></ns:getDpRequest>"
        value = self._value(await self._post(ACTION_LIST, body))
        _LOGGER.debug("W2C OID read successfully: oid=%s value=%s", oid, value)
        return value

    async def read_oid_limits(self, oid: str) -> tuple[float | None, float | None]:
        """Liest minValue und maxValue eines Datenpunkts vom Gerät."""
        body = f"<ns:getDpRequest><ref><oid>{oid}</oid><prop/></ref><startIndex>0</startIndex><count>-1</count></ns:getDpRequest>"
        raw = await self._post(ACTION_LIST, body)
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as err:
            raise W2CApiError(f"Malformed SOAP response: {err}") from err

        def _find(tag: str):
            el = root.find(f".//{{{NS}}}{tag}")
            if el is None:
                el = root.find(f".//{tag}")
            return el.text if el is not None else None

        def _num(text):
            try:
                return float(str(text).replace(",", "."))
            except (TypeError, ValueError):
                return None

        limits = (_num(_find("minValue")), _num(_find("maxValue")))
        _LOGGER.debug("W2C OID limits: oid=%s min=%s max=%s", oid, limits[0], limits[1])
        return limits

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
        body = (
            f"<ns:writeDpRequest><ref><oid>{oid}</oid><prop/></ref>"
            f"<dp><index>{index}</index><name/><prop/><desc/>"
            f"<value>{normalized}</value><unit/><timestamp>0</timestamp></dp>"
            f"</ns:writeDpRequest>"
        )
        await self._post(ACTION_WRITE, body)
        _LOGGER.debug("W2C OID write successful: oid=%s", oid)
