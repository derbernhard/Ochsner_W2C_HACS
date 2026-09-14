from __future__ import annotations
import urllib.error, urllib.request
from xml.etree import ElementTree as ET

class W2CApiError(Exception):
    pass

class W2CApi:
    def __init__(self, hass, host, username, password, timeout=60):
        self.hass = hass
        self.url = f"http://{host.strip().rstrip('/')}/ws"
        self.username = username
        self.password = password
        self.timeout = timeout
        manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, self.url, username, password)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPDigestAuthHandler(manager),
            urllib.request.HTTPBasicAuthHandler(manager),
        )

    def _envelope(self, body):
        return ('<?xml version="1.0" encoding="UTF-8"?>'
          '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns="http://ws01.lom.ch/soap/">'
          f'<SOAP-ENV:Body>{body}</SOAP-ENV:Body></SOAP-ENV:Envelope>')

    def _post_sync(self, soap_action, body):
        payload = self._envelope(body).encode('utf-8')
        req = urllib.request.Request(self.url, data=payload, method='POST', headers={
            'Content-Type': 'text/xml; charset=utf-8', 'Accept': 'text/xml',
            'SOAPAction': soap_action, 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
            raise W2CApiError(str(err)) from err

    @staticmethod
    def _value(xml_bytes):
        try:
            root = ET.fromstring(xml_bytes)
            for elem in root.iter():
                if elem.tag.rsplit('}', 1)[-1] == 'value':
                    text = (elem.text or '').strip()
                    if text == '': return None
                    try: return float(text) if '.' in text or ',' in text else int(text)
                    except ValueError: return text
        except ET.ParseError as err:
            raise W2CApiError(f'Invalid SOAP XML: {err}') from err
        raise W2CApiError('SOAP response contains no value element')

    async def read_oid(self, oid):
        body = f'<ns:getDpRequest><ref><oid>{oid}</oid><prop/></ref><startIndex>0</startIndex><count>-1</count></ns:getDpRequest>'
        xml = await self.hass.async_add_executor_job(self._post_sync, 'http://ws01.lom.ch/soap/listDP', body)
        return self._value(xml)

    async def read_all(self, oids):
        result = {}
        for oid in oids:
            result[oid] = await self.read_oid(oid)
        return result

    async def write_oid(self, oid, value):
        index = oid.rstrip('/').split('/')[-1]
        body = (f'<ns:writeDpRequest><ref><oid>{oid}</oid><prop/></ref><dp><index>{index}</index>'
                f'<name/><prop/><desc/><value>{str(value).replace(",", ".")}</value><unit/>'
                '<timestamp>0</timestamp></dp></ns:writeDpRequest>')
        await self.hass.async_add_executor_job(self._post_sync, 'http://ws01.lom.ch/soap/writeDP', body)
