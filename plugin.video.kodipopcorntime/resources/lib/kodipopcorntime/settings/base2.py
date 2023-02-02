#!/usr/bin/python
import xbmcvfs, sys, os, time, stat, shutil
from . import SUBTITLE_ISO, QUALITIES, PUBLIC_TRACKERS
from .addon import Addon
from .base import _Base, _MetaClass
from urllib.parse import urlparse
from kodipopcorntime.platform import Platform
from kodipopcorntime.exceptions import Error, Notify
from kodipopcorntime.logging import log, LOGLEVEL

__addon__ = sys.modules['__main__'].__addon__

class _MetaClass2(_MetaClass):
    def _mediaType(cls):
        cls.mediaType = cls.__name__.lower()

    def _lastchanged(cls):
        cls.lastchanged = cls.subtitle_lastchanged > cls.metadata_lastchanged and cls.subtitle_lastchanged or cls.metadata_lastchanged

    def _subtitle_lastchanged(cls):
        _name =  cls.mediaType
        _time = str(time.time())
        for _s in ['preferred_subtitles', 'prioritere_impaired', 'subtitles_provider']:
            _tmp = str(getattr(cls, _s))
            if not _tmp == __addon__.getSetting('%s_%s_old' %(_name, _s)):
                __addon__.setSetting('%s_%s_old' %(_name, _s), _tmp)
                __addon__.setSetting('%s_subtitle_lastchanged' %_name, _time)

        cls.subtitle_lastchanged = float(__addon__.getSetting("%s_subtitle_lastchanged" %_name) or 0.0)

    def _metadata_lastchanged(cls):
        _name =  cls.mediaType
        _time = str(time.time())

        _tmp = str(cls.metadata_provider)
        if not _tmp == __addon__.getSetting('%s_metadata_provider_old' %_name):
            __addon__.setSetting("%s_metadata_provider_old" %_name, _tmp)
            __addon__.setSetting("%s_metadata_lastchanged" %_name, _time)

        if not Addon.language == __addon__.getSetting('%s_syslang_old' %_name):
            __addon__.setSetting("%s_syslang_old" %_name, Addon.language)
            __addon__.setSetting("%s_metadata_lastchanged" %_name, _time)

        cls.metadata_lastchanged = float(__addon__.getSetting("%s_metadata_lastchanged" %_name) or 0.0)

    def _preferred_subtitles(cls):
        subtitles = []
        if cls.subtitles_provider:
            for i in range(3):
                _n = int(__addon__.getSetting('%s_subtitle_language%d' %(cls.mediaType, i)))
                if not _n > 0:
                    break
                subtitles = subtitles+[SUBTITLE_ISO[_n-1]]
        cls.preferred_subtitles = subtitles

    def _prioritere_impaired(cls):
        if not __addon__.getSetting('%s_subtitle_language1' %cls.mediaType) == '0' and __addon__.getSetting("hearing_impaired") == 'true':
            cls.prioritere_impaired = True
        else:
            cls.prioritere_impaired = False

    def _proxies(cls):
        p = []
        domains = __addon__.getSetting("%s_proxies" %cls.mediaType).split(',')
        # Evaluate user domains
        for domain in reversed(domains):
            if not domain[:4] == 'http' and not domain[:2] == '//':
                domain = "http://"+domain
            d = urlparse(domain)
            if d.netloc:
                p.append("%s://%s/%s" %(d.scheme, d.netloc, d.path))
        cls.proxies = p

    def _qualities(cls):
        __qualities = []
        if cls.play3d > 0:
            __qualities = [QUALITIES[0]]
        if __addon__.getSetting("%s_quality" %cls.mediaType) == '0':
            cls.qualities = __qualities+QUALITIES[-2:]
        else:
            cls.qualities = __qualities+QUALITIES[1:]

    def _play3d(cls):
        if not __addon__.getSetting("%s_quality" %cls.mediaType) == '0':
            cls.play3d = int(__addon__.getSetting("%s_play3d"  %cls.mediaType))
        else:
            cls.play3d = 0

    def _media_cache_path(cls):
        _path = os.path.join(Addon.cache_path, cls.mediaType)
        if not os.path.exists(_path):
            os.makedirs(_path)
            if not os.path.exists(_path):
                raise Error("Unable to create cache directory %s" % _path, 30322)
        cls.media_cache_path = _path

    def _user_download_path(cls):
        _path = xbmcvfs.translatePath(__addon__.getSetting("%s_download_path"  %cls.mediaType))
        if _path:
            if _path.lower().startswith("smb://"):
                if Platform.system != "windows":
                    raise Notify("Downloading to an unmounted network share is not supported (%s)" % _path, 30319, 0)
                _path.replace("smb:", "").replace("/", "\\")

            if not os.path.isdir(_path):
                raise Notify('Download path does not exist (%s)' % _path, 30310, 1)

            cls.user_download_path = _path
        else:
            cls.user_download_path = None

    def _download_path(cls):
        cls.download_path = cls.user_download_path or cls.media_cache_path

    def _delete_files(cls):
        if cls.keep_files or cls.keep_complete or cls.keep_incomplete:
            cls.delete_files = False
        else:
            cls.delete_files = True

    def _keep_files(cls):
        if __addon__.getSetting("%s_keep_files" %cls.mediaType) == 'true' and not cls.keep_complete and not cls.keep_incomplete:
            cls.keep_files = True
        else:
            cls.keep_files = False

    def _keep_complete(cls):
        if not __addon__.getSetting("%s_keep_incomplete" %cls.mediaType) == 'false' and __addon__.getSetting("%s_keep_complete" %cls.mediaType) == 'true':
            cls.keep_complete = True
        else:
            cls.keep_complete = False

    def _keep_incomplete(cls):
        if __addon__.getSetting("%s_keep_incomplete" %cls.mediaType) == 'true' and __addon__.getSetting("%s_keep_complete" %cls.mediaType) == 'false':
            cls.keep_incomplete = True
        else:
            cls.keep_incomplete = False

    def _binary_path(cls):
        binary = "torrent2http"
        if Platform.system == 'windows':
            binary = "torrent2http.exe"

        binary_path = os.path.join(__addon__.getAddonInfo('path'), 'resources', 'bin', "%s_%s" %(Platform.system, Platform.arch), binary)

        if Platform.system == "android":
            existBinary(binary_path)
            binary_path = ensure_android_binary_location(binary_path, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(xbmcvfs.translatePath('special://xbmc')))), "files", __addon__.getAddonInfo('id'), binary))

        existBinary(binary_path)
        ensure_exec(binary_path)

        cls.binary_path = binary_path

    def _download_kbps(cls):
        download_kbps = int(__addon__.getSetting("download_kbps"))
        if download_kbps <= 0:
            download_kbps = -1
        cls.download_kbps = download_kbps

    def _upload_kbps(cls):
        upload_kbps = int(__addon__.getSetting("upload_kbps"))
        if upload_kbps <= 0:
            upload_kbps = -1
        elif upload_kbps < 15:
            raise Notify('Max Upload Rate must be above 15 Kilobytes per second.', 30324, 1)
            upload_kbps = 15
        cls.upload_kbps = upload_kbps

    def _trackers(cls):
        trackers = __addon__.getSetting('trackers')
        if trackers:
            trackers = ",".join(trackers.split(',')+PUBLIC_TRACKERS)
        else:
            trackers = ",".join(PUBLIC_TRACKERS)
        cls.trackers = trackers

    def _torrent_options(cls):
        debug = __addon__.getSetting("debug")
        kwargs = {
            '--bind':                   '127.0.0.1:5001',
            '--dl-path':                cls.download_path,
            '--connections-limit':      int(__addon__.getSetting('connections_limit')),
            '--dl-rate':                cls.download_kbps,
            '--ul-rate':                cls.upload_kbps,
            '--enable-dht':             __addon__.getSetting('enable_dht'),
            '--enable-lsd':             __addon__.getSetting('enable_lsd'),
            '--enable-natpmp':          __addon__.getSetting('enable_natpmp'),
            '--enable-upnp':            __addon__.getSetting('enable_upnp'),
            '--enable-scrape':          __addon__.getSetting('enable_scrape'),
            '--encryption':             int(__addon__.getSetting('encryption')),
            '--show-stats':             debug,
            '--files-progress':         debug,
            '--overall-progress':       debug,
            '--pieces-progress':        debug,
            '--listen-port':            int(__addon__.getSetting('listen_port')),
            '--random-port':            __addon__.getSetting('use_random_port'),
            '--keep-complete':          str(cls.keep_complete).lower(),
            '--keep-incomplete':        str(cls.keep_incomplete).lower(),
            '--keep-files':             str(cls.keep_files).lower(),
            '--max-idle':               300,
            '--no-sparse':              'false',
            #'--resume-file':            None,
            '--user-agent':             'torrent2http/1.0.1 libtorrent/1.0.3.0 kodipopcorntime/%s' %Addon.version,
            #'--state-file':             None,
            '--enable-utp':             __addon__.getSetting('enable_utp'),
            '--enable-tcp':             __addon__.getSetting('enable_tcp'),
            '--debug-alerts':           debug,
            '--torrent-connect-boost':  int(__addon__.getSetting('torrent_connect_boost')),
            '--connection-speed':       int(__addon__.getSetting('connection_speed')),
            '--peer-connect-timeout':   int(__addon__.getSetting('peer_connect_timeout')),
            '--request-timeout':        20,
            '--min-reconnect-time':     int(__addon__.getSetting('min_reconnect_time')),
            '--max-failcount':          int(__addon__.getSetting('max_failcount')),
            '--dht-routers':            __addon__.getSetting('dht_routers') or None,
            '--trackers':               cls.trackers
        }

        args = [cls.binary_path]
        for k, v in kwargs.items():
            if v == 'true':
                args.append(k)
            elif v == 'false':
                args.append("%s=false" % k)
            elif v is not None:
                args.append(k)
                args.append(str(v))

        cls.torrent_options = args

class _Base2(_Base):
    @classmethod
    def get_torrent_options(self, magnet, port):
        args = ['--uri', magnet, '--bind', '127.0.0.1:%s' %port]
        return self.torrent_options+args

def load_provider(module):
    provider = "kodipopcorntime.providers.%s" % module
    mod = __import__(provider)
    for comp in provider.split('.')[1:]:
        mod = getattr(mod, comp)
    return mod

def existBinary(binary_path):
    if not os.path.isfile(binary_path):
        raise Error("torrent2http binary was not found at path %s" % os.path.dirname(binary_path), 30320)

def ensure_android_binary_location(binary_path, android_binary_path):
    log("Trying to copy torrent2http to ext4, since the sdcard is noexec", LOGLEVEL.INFO)
    if not os.path.exists(os.path.dirname(android_binary_path)):
        os.makedirs(os.path.dirname(android_binary_path))
    if not os.path.exists(android_binary_path) or int(os.path.getmtime(android_binary_path)) < int(os.path.getmtime(binary_path)):
        shutil.copy2(binary_path, android_binary_path)
    return android_binary_path

def ensure_exec(binary_path):
    st = os.stat(binary_path)
    os.chmod(binary_path, st.st_mode | stat.S_IEXEC)
    st = os.stat(binary_path)
    if not st.st_mode & stat.S_IEXEC:
        raise Error("Cannot make torrent2http executable (%s)" % binary_path, 30321)
