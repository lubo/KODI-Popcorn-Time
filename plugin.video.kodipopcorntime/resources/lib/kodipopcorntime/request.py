#!/usr/bin/python
from http import HTTPStatus
from http.client import HTTPConnection, HTTPSConnection, responses
import zlib, simplejson, sys, socket, http, errno, xbmcaddon, xbmcvfs, os, json
from urllib.parse import urlencode, urlparse
from kodipopcorntime.utils import Cache
from kodipopcorntime.exceptions import HTTPError, ProxyError
from kodipopcorntime.logging import log, LOGLEVEL
from kodipopcorntime.settings import addon as _settings
from kodipopcorntime import favourites as _favs

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
__addondir__ = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))

_json_file = os.path.join(__addondir__, 'test.json')

class URL(object):
    def __init__(self):
        self.conn = self.scheme = self.netloc = self.uri = self.url = None
        # Default headers
        self.headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.66 Safari/537.36", "Accept-Encoding": "gzip"}

    def __enter__(self):
        return self

    def request_proxy(self, proxies, path, proxyid, params={}, headers={}, timeout=10):
        log("(URL) Proxy domain is activated", LOGLEVEL.NONE)
        with Cache(proxyid) as proxies_cache:
            if not proxies_cache or not all(p in proxies_cache['proxies'] for p in proxies):
                proxies_cache['proxies'] = proxies

            for proxy in proxies_cache['proxies'][:]:
                try:
                    if path == 'movie_favs':
                        _favs._create_movie_favs()
                        with open(_json_file) as json_read:
                            _data = json.load(json_read)
                    else:
                        _data = self.request(proxy, path, params, headers, timeout)
                    if _data or _data is None:
                        return _data
                except (HTTPError, socket.timeout, socket.gaierror, socket.herror, socket.error) as e:
                    if e.__class__.__name__ == 'error':
                        if not e.errno in [errno.EUSERS, errno.ECONNRESET, errno.ETIMEDOUT, errno.ECONNREFUSED, errno.EHOSTDOWN]:
                            raise
                    log("(URL) %s: %s - %s" %(e.__class__.__name__, str(e), self.url), LOGLEVEL.ERROR)
                log("(URL) Proxy domain '%s' is not working and will therefore have low priority in the future" %proxy, LOGLEVEL.INFO)
                proxies_cache.extendKey('proxies', [proxies_cache['proxies'].pop(0)])
            raise ProxyError("There was not any domains that worked", 30328)

    def request(self, domain, path, params={}, headers={}, timeout=10):
        headers.update(self.headers)
        log("(URL) Headers: %s" %str(headers), LOGLEVEL.NONE)

        self.scheme, self.netloc, self.uri, self.url = self.urlParse(domain, path, params)
        log("(URL) Trying to obtaining data from %s" %self.url, LOGLEVEL.NONE)
        try:
            if self.scheme == 'https':
                self.conn = HTTPSConnection(self.netloc, timeout=timeout)
            else:
                self.conn = HTTPConnection(self.netloc, timeout=timeout)
            if _settings.debug:
                self.conn.set_debuglevel(1)
            self.conn.request("GET", self.uri, headers=headers)
            response = self.conn.getresponse()
            if response.status == HTTPStatus.OK:
                return self._read(response)
            raise HTTPError("Received wrong status code (%s %s) from %s" %(response.status, responses.get(response.status, ''), self.url), 30329)
        except socket.error as e:
            if e.errno in [errno.ESHUTDOWN, errno.ECONNABORTED]:
                log("(URL) socket.error: %s. (Connection has most likely been canceled by user choices)" %str(e), LOGLEVEL.INFO)
                return None
            raise

    def decompress(self, data):
        log("(Request) Decompress content", LOGLEVEL.NONE)
        return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data)

    def urlParse(self, domain, path, params={}):
        scheme, netloc, _path, _, _, _ = urlparse(domain)
        if _path and not _path == '/': # Support path in domain
            if _path[-1:] == '/':
                path = _path[:-1]+path
            else:
                path = _path+path
        uri = path
        if params:
            uri = "%s?%s" %(path, urlencode(params))
        return scheme, netloc, uri, "%s://%s%s" %(scheme, netloc, uri)

    def _read(self, response):
        log("(URL) Reading response", LOGLEVEL.NONE)
        data = response.read()
        if data and response.getheader("Content-Encoding", "") == "gzip":
            data = self.decompress(data)
        if not data:
            log("(URL) Did not receive any data %s" %self.url, LOGLEVEL.INFO)
        else:
            log("(URL) Successful receive data from %s" %self.url, LOGLEVEL.NONE)
        return data

    def __exit__(self, *exc_info):
        self.close()
        return not exc_info[0]

    def __del__(self):
        self.close()

    def cancel(self):
        self.close()

    def close(self):
        if hasattr(self, 'conn'):
            if self.conn and self.conn.sock:
                self.conn.sock.shutdown(socket.SHUT_RDWR)
            self.conn = None

class Send(URL):
    def request_proxy(self, *agrs, **kwagrs):
        return super(Send, self).request_proxy(*agrs, **kwagrs)

    def request(self, *agrs, **kwagrs):
        return super(Send, self).request(*agrs, **kwagrs)

    def _read(self, response):
        return None

class Json(URL):
    def _read(self, response):
        log("(URL) Reading response", LOGLEVEL.NONE)
        data = response.read()
        if data and response.getheader("Content-Encoding", "") == "gzip":
            data = self.decompress(data)
        if not data:
            log("(URL) Did not receive any data %s" %self.url, LOGLEVEL.INFO)
        else:
            log("(Json) Reading JSON data", LOGLEVEL.NONE)
            data = simplejson.loads(data, 'UTF-8')
            if data:
                log("(Json) Successful receive data from %s" %self.url, LOGLEVEL.NONE)
                return data

class Download(URL):
    def __init__(self):
        # Default headers
        self.headers      = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.66 Safari/537.36"}
        self.downloadPath = None

    def request_proxy(self, downloadPath, *agrs, **kwagrs):
        self.downloadPath = downloadPath
        return super(Download, self).request_proxy(*agrs, **kwagrs)

    def request(self, downloadPath, *agrs, **kwagrs):
        self.downloadPath = downloadPath
        return super(Download, self).request(*agrs, **kwagrs)

    def _read(self, response):
        log("(Download) Store data on location %s" %self.downloadPath, LOGLEVEL.NONE)
        with open(self.downloadPath, "wb") as f:
            f.write(response.read())
        log("(Download) Successful stored data at %s" %self.url, LOGLEVEL.NONE)
        return self.downloadPath
