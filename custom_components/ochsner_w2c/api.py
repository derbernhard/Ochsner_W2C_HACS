from __future__ import annotations
import asyncio
from aiohttp import BasicAuth, ClientError, ClientSession, TCPConnector
OIDS=["/1/2/4/119/1","/1/2/4/119/3","/1/2/4/119/7","/1/2/4/119/0","/1/2/4/107/0","/1/2/7/121/1","/1/2/7/121/2","/1/2/7/121/0","/1/2/7/107/0"]
class ApiError(Exception):pass
class W2CApi:
 def __init__(self,session,gateway,target,user,password,verify_ssl=False):self.s=session;self.base=f"https://{gateway.strip().rstrip('/')}";self.target=target;self.user=user;self.password=password;self.ssl=verify_ssl
 async def _get(self,params):
  try:
   async with asyncio.timeout(20):
    r=await self.s.get(f"{self.base}/web2com.php",params=params,ssl=self.ssl);r.raise_for_status();return await r.json(content_type=None)
  except (TimeoutError,ClientError,ValueError) as e:raise ApiError(str(e)) from e
 async def read(self):return await self._get({'host':self.target,'user':self.user,'pass':self.password,'getoid':';'.join(OIDS)})
 async def write(self,oid,value):await self._get({'host':self.target,'user':self.user,'pass':self.password,'setoid':oid,'value':value})
