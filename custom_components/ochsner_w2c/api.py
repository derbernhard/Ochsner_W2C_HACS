"""Direct asynchronous SOAP client for Ochsner W2C."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from typing import Any
from xml.etree import ElementTree as ET

from aiohttp import BasicAuth, ClientError, ClientResponse, ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)


class W2CApiError(Exception):
    """Raised when communication with the W2C module fails."""


class W2CApi:
    """Async SOAP client supporting HTTP Basic and Digest authentication."""

    def __init__(self, session: ClientSession, host: str, username: str, password: str, timeout: int = 60) -> None:
        self._session = session
        self._host = host.strip().rstrip("/")
        self._url = f"http://{self._host}/ws"
        self._username = username
        self._password = password
        self._timeout = timeout
        self._auth_scheme: str | None = None
        self._digest_challenge: dict[str, str] = {}
        self._nonce_count = 0
        _LOGGER.debug("Initialising Ochsner W2C API: host=%s timeout=%ss", self._host, timeout)

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

    @staticmethod
    def _parse_digest_challenge(header: str) -> dict[str, str]:
        challenge = re.sub(r"^Digest\s+", "", header, flags=re.IGNORECASE)
        parsed = {
            key.lower(): quoted if quoted is not None else plain
            for key, quoted, plain in re.findall(r'(\w+)\s*=\s*(?:"([^"]*)"|([^,\s]+))', challenge)
        }
        _LOGGER.debug(
            "Parsed Digest challenge: realm_present=%s nonce_present=%s algorithm=%s qop=%s opaque_present=%s stale=%s",
            bool(parsed.get("realm")), bool(parsed.get("nonce")), parsed.get("algorithm", "MD5"),
            parsed.get("qop", "<none>"), bool(parsed.get("opaque")), parsed.get("stale", "false"),
        )
        return parsed

    @staticmethod
    def _hash(algorithm: str, value: str) -> str:
        normalized = algorithm.upper().replace("-", "")
        algorithms = {"MD5": hashlib.md5, "SHA": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}
        base = normalized.removesuffix("SESS")
        hash_function = algorithms.get(base)
        if hash_function is None:
            raise W2CApiError(f"Unsupported Digest algorithm: {algorithm}")
        return hash_function(value.encode("utf-8")).hexdigest()

    def _digest_authorization(self, method: str, uri: str) -> str:
        c = self._digest_challenge
        realm, nonce = c.get("realm", ""), c.get("nonce", "")
        if not realm or not nonce:
            raise W2CApiError("Digest challenge is missing realm or nonce")
        algorithm = c.get("algorithm", "MD5")
        qops = [item.strip().lower() for item in c.get("qop", "").split(",") if item.strip()]
        if qops and "auth" not in qops:
            raise W2CApiError(f"Unsupported Digest qop: {c.get('qop')}")
        qop = "auth" if "auth" in qops else None
        self._nonce_count += 1
        nc, cnonce = f"{self._nonce_count:08x}", os.urandom(8).hex()
        ha1 = self._hash(algorithm, f"{self._username}:{realm}:{self._password}")
        if algorithm.upper().replace("-", "").endswith("SESS"):
            ha1 = self._hash(algorithm, f"{ha1}:{nonce}:{cnonce}")
        ha2 = self._hash(algorithm, f"{method}:{uri}")
        digest = self._hash(algorithm, f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}") if qop else self._hash(algorithm, f"{ha1}:{nonce}:{ha2}")
        fields = [f'username="{self._username}"', f'realm="{realm}"', f'nonce="{nonce}"', f'uri="{uri}"', f'response="{digest}"', f"algorithm={algorithm}"]
        if c.get("opaque") is not None:
            fields.append(f'opaque="{c["opaque"]}"')
        if qop:
            fields.extend([f"qop={qop}", f"nc={nc}", f'cnonce="{cnonce}"'])
        return "Digest " + ", ".join(fields)

    async def _request(self, payload: bytes, soap_action: str, authorization: str | None = None) -> ClientResponse:
        headers = {"Content-Type": "text/xml; charset=utf-8", "Accept": "text/xml", "Cache-Control": "no-cache", "Pragma": "no-cache", "SOAPAction": soap_action}
        if authorization:
            headers["Authorization"] = authorization
        _LOGGER.debug("SOAP request: host=%s action=%s auth=%s bytes=%s", self._host, soap_action, self._auth_scheme or "none", len(payload))
        response = await self._session.post(self._url, data=payload, headers=headers, timeout=self._timeout)
        _LOGGER.debug("SOAP response: action=%s status=%s content_type=%s", soap_action, response.status, response.headers.get("Content-Type", ""))
        return response

    @staticmethod
    def _select_auth_challenge(response: ClientResponse) -> tuple[str, str]:
        challenges = response.headers.getall("WWW-Authenticate", [])
        safe = [re.sub(r'nonce="[^"]+"', 'nonce="<redacted>"', item, flags=re.IGNORECASE) for item in challenges]
        _LOGGER.warning("W2C authentication required: status=401 challenges=%s", safe)
        digest = next((item for item in challenges if item.lower().startswith("digest ")), None)
        basic = next((item for item in challenges if item.lower().startswith("basic")), None)
        if digest:
            return "digest", digest
        if basic:
            return "basic", basic
        raise W2CApiError("W2C requested an unsupported authentication method")

    async def _post(self, soap_action: str, body: str) -> bytes:
        payload, uri = self._envelope(body).encode("utf-8"), "/ws"
        response: ClientResponse | None = None
        try:
            if self._auth_scheme == "basic":
                response = await self._request(payload, soap_action, BasicAuth(self._username, self._password).encode())
            elif self._auth_scheme == "digest":
                response = await self._request(payload, soap_action, self._digest_authorization("POST", uri))
            else:
                response = await self._request(payload, soap_action)

            if response.status == 401:
                await response.read()
                scheme, challenge = self._select_auth_challenge(response)
                self._auth_scheme = scheme
                if scheme == "digest":
                    self._digest_challenge = self._parse_digest_challenge(challenge)
                    authorization = self._digest_authorization("POST", uri)
                else:
                    authorization = BasicAuth(self._username, self._password).encode()
                response.release()
                _LOGGER.debug("Retrying SOAP request with %s authentication", scheme)
                response = await self._request(payload, soap_action, authorization)

            if response.status == 401 and self._auth_scheme == "digest":
                await response.read()
                scheme, challenge = self._select_auth_challenge(response)
                if scheme == "digest" and "stale=true" in challenge.lower():
                    self._digest_challenge = self._parse_digest_challenge(challenge)
                    self._nonce_count = 0
                    response.release()
                    response = await self._request(payload, soap_action, self._digest_authorization("POST", uri))

            if response.status >= 400:
                preview = (await response.text(errors="replace"))[:500]
                _LOGGER.error("SOAP HTTP error: action=%s status=%s response_preview=%r", soap_action, response.status, preview)
                response.raise_for_status()
            data = await response.read()
            _LOGGER.debug("SOAP request successful: action=%s response_bytes=%s", soap_action, len(data))
            return data
        except (TimeoutError, asyncio.TimeoutError) as err:
            _LOGGER.error("SOAP timeout: host=%s action=%s error=%r", self._host, soap_action, err)
            raise W2CApiError(f"Timeout while calling {soap_action}") from err
        except ClientResponseError as err:
            _LOGGER.error("SOAP response error: host=%s action=%s status=%s message=%s", self._host, soap_action, err.status, err.message)
            raise W2CApiError(f"HTTP {err.status}: {err.message}") from err
        except ClientError as err:
            _LOGGER.error("SOAP client error: host=%s action=%s type=%s error=%r", self._host, soap_action, type(err).__name__, err)
            raise W2CApiError(f"{type(err).__name__}: {err}") from err
        finally:
            if response is not None:
                response.release()

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
        result = {}
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
        index, normalized = oid.rstrip("/").split("/")[-1], str(value).replace(",", ".")
        body = f"<ns:writeDpRequest><ref><oid>{oid}</oid><prop/></ref><dp><index>{index}</index><name/><prop/><desc/><value>{normalized}</value><unit/><timestamp>0</timestamp></dp></ns:writeDpRequest>"
        await self._post("http://ws01.lom.ch/soap/writeDP", body)
        _LOGGER.debug("W2C OID write successful: oid=%s", oid)
