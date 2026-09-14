"""Direct asynchronous SOAP client for Ochsner W2C."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
from typing import Any
from xml.etree import ElementTree as ET

from aiohttp import BasicAuth, ClientError, ClientResponse, ClientSession


class W2CApiError(Exception):
    """Raised when communication with the W2C module fails."""


class W2CApi:
    """Async SOAP client supporting HTTP Basic and Digest authentication."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        username: str,
        password: str,
        timeout: int = 60,
    ) -> None:
        self._session = session
        self._url = f"http://{host.strip().rstrip('/')}/ws"
        self._username = username
        self._password = password
        self._timeout = timeout
        self._auth_scheme: str | None = None
        self._digest_challenge: dict[str, str] = {}
        self._nonce_count = 0

    @staticmethod
    def _envelope(body: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<SOAP-ENV:Envelope '
            'xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:ns="http://ws01.lom.ch/soap/">'
            f"<SOAP-ENV:Body>{body}</SOAP-ENV:Body>"
            "</SOAP-ENV:Envelope>"
        )

    @staticmethod
    def _parse_digest_challenge(header: str) -> dict[str, str]:
        challenge = header[len("Digest ") :]
        return {
            key.lower(): (quoted if quoted is not None else plain)
            for key, quoted, plain in re.findall(
                r'(\w+)\s*=\s*(?:"([^"]*)"|([^,\s]+))', challenge
            )
        }

    @staticmethod
    def _hash(algorithm: str, value: str) -> str:
        normalized = algorithm.upper().replace("-", "")
        algorithms = {
            "MD5": hashlib.md5,
            "SHA": hashlib.sha1,
            "SHA256": hashlib.sha256,
            "SHA512": hashlib.sha512,
        }
        base = normalized.removesuffix("SESS")
        hash_function = algorithms.get(base)
        if hash_function is None:
            raise W2CApiError(f"Unsupported Digest algorithm: {algorithm}")
        return hash_function(value.encode("utf-8")).hexdigest()

    def _digest_authorization(self, method: str, uri: str) -> str:
        challenge = self._digest_challenge
        realm = challenge.get("realm", "")
        nonce = challenge.get("nonce", "")
        opaque = challenge.get("opaque")
        algorithm = challenge.get("algorithm", "MD5")
        qop_values = [x.strip() for x in challenge.get("qop", "").split(",") if x]
        qop = "auth" if "auth" in qop_values else None

        self._nonce_count += 1
        nc = f"{self._nonce_count:08x}"
        cnonce = os.urandom(8).hex()
        ha1 = self._hash(algorithm, f"{self._username}:{realm}:{self._password}")
        if algorithm.upper().endswith("-SESS") or algorithm.upper().endswith("SESS"):
            ha1 = self._hash(algorithm, f"{ha1}:{nonce}:{cnonce}")
        ha2 = self._hash(algorithm, f"{method}:{uri}")
        if qop:
            response = self._hash(
                algorithm, f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}"
            )
        else:
            response = self._hash(algorithm, f"{ha1}:{nonce}:{ha2}")

        fields = [
            f'username="{self._username}"',
            f'realm="{realm}"',
            f'nonce="{nonce}"',
            f'uri="{uri}"',
            f'response="{response}"',
            f"algorithm={algorithm}",
        ]
        if opaque is not None:
            fields.append(f'opaque="{opaque}"')
        if qop:
            fields.extend([f"qop={qop}", f"nc={nc}", f'cnonce="{cnonce}"'])
        return "Digest " + ", ".join(fields)

    async def _request(
        self, payload: bytes, soap_action: str, authorization: str | None = None
    ) -> ClientResponse:
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "SOAPAction": soap_action,
        }
        if authorization:
            headers["Authorization"] = authorization
        return await self._session.post(
            self._url,
            data=payload,
            headers=headers,
            timeout=self._timeout,
        )

    async def _post(self, soap_action: str, body: str) -> bytes:
        payload = self._envelope(body).encode("utf-8")
        uri = "/ws"
        try:
            if self._auth_scheme == "basic":
                auth = BasicAuth(self._username, self._password).encode()
                response = await self._request(payload, soap_action, auth)
            elif self._auth_scheme == "digest":
                auth = self._digest_authorization("POST", uri)
                response = await self._request(payload, soap_action, auth)
            else:
                response = await self._request(payload, soap_action)

            if response.status == 401:
                await response.read()
                challenge = response.headers.get("WWW-Authenticate", "")
                if challenge.lower().startswith("digest "):
                    self._auth_scheme = "digest"
                    self._digest_challenge = self._parse_digest_challenge(challenge)
                    auth = self._digest_authorization("POST", uri)
                elif challenge.lower().startswith("basic"):
                    self._auth_scheme = "basic"
                    auth = BasicAuth(self._username, self._password).encode()
                else:
                    raise W2CApiError(
                        "W2C requested an unsupported authentication method"
                    )
                response = await self._request(payload, soap_action, auth)

            response.raise_for_status()
            return await response.read()
        except (TimeoutError, asyncio.TimeoutError, ClientError) as err:
            raise W2CApiError(str(err)) from err

    @staticmethod
    def _value(xml_bytes: bytes) -> Any:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as err:
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
        raise W2CApiError("SOAP response contains no value element")

    async def read_oid(self, oid: str) -> Any:
        body = (
            "<ns:getDpRequest><ref>"
            f"<oid>{oid}</oid><prop/></ref>"
            "<startIndex>0</startIndex><count>-1</count>"
            "</ns:getDpRequest>"
        )
        xml = await self._post("http://ws01.lom.ch/soap/listDP", body)
        return self._value(xml)

    async def read_all(self, oids: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for oid in oids:
            result[oid] = await self.read_oid(oid)
        return result

    async def write_oid(self, oid: str, value: Any) -> None:
        index = oid.rstrip("/").split("/")[-1]
        normalized = str(value).replace(",", ".")
        body = (
            "<ns:writeDpRequest><ref>"
            f"<oid>{oid}</oid><prop/></ref><dp>"
            f"<index>{index}</index><name/><prop/><desc/>"
            f"<value>{normalized}</value><unit/><timestamp>0</timestamp>"
            "</dp></ns:writeDpRequest>"
        )
        await self._post("http://ws01.lom.ch/soap/writeDP", body)
