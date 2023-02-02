#!/usr/bin/python
import os, sys, xbmc, xbmcgui, xbmcvfs, mimetypes, time, subprocess, socket, re
from urllib.parse import parse_qsl, urlparse
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from contextlib import closing
from simplejson import JSONDecodeError
from kodipopcorntime.utils import SafeDialogProgress, xbmcItem, get_free_port, shortenBytes, clear_media_cache
from kodipopcorntime.logging import log, LOGLEVEL, LogPipe, log_error
from kodipopcorntime.exceptions import Error, TorrentError, Abort
from kodipopcorntime.settings import addon as _settings
from kodipopcorntime import request
from kodipopcorntime.platform import Platform
from kodipopcorntime.threads import Thread

__addon__ = sys.modules['__main__'].__addon__

class OverlayText:
    def __init__(self):
        log('(Overlay) Initialize overlay text', LOGLEVEL.INFO)
        x, y, w, h = self._calculate_the_size()

        self._shown       = False
        self._window     = xbmcgui.Window(12005)
        self._label      = xbmcgui.ControlLabel(x, y, w, h, '', alignment=0x00000002 | 0x00000004)
        self._background = xbmcgui.ControlImage(x, y, w, h, os.path.join(_settings.resources_path, "media", "black.png"))

        self._background.setColorDiffuse("0xD0000000")

    def __enter__(self):
        return self

    def open(self):
        if not self._shown:
            self._window.addControls([self._background, self._label])
            self._shown = True

    def isShowing(self):
        return self._shown

    def setText(self, text):
        if self._shown:
            self._label.setLabel(text)

    def _calculate_the_size(self):
        # get skin resolution
        tree = ET.parse(os.path.join(xbmcvfs.translatePath("special://skin/"), "addon.xml"))
        res = tree.findall("./extension/res")[0]
        viewport_w = int(res.attrib["width"])
        viewport_h = int(res.attrib["height"])
        # Adjust size based on viewport, we are using 1080p coordinates
        w = int(int(1920.0 * 0.7) * viewport_w / 1920.0)
        h = int(150 * viewport_h / 1088.0)
        x = (viewport_w - w) // 2
        y = (viewport_h - h) // 2
        return x, y, w, h

    def __exit__(self, *exc_info):
        self.close()
        return not exc_info[0]

    def __del__(self):
        self.close()

    def close(self):
        if hasattr(self, '_background') and self._shown:
            self._window.removeControls([self._background, self._label])
            self._shown = False

class TorrentEngine:
    QUEUED_FOR_CHECKING     = 0
    CHECKING_FILES          = 1
    DOWNLOADING_METADATA    = 2
    DOWNLOADING             = 3
    FINISHED                = 4
    SEEDING                 = 5
    ALLOCATING              = 6
    CHECKING_RESUME_DATA    = 7
    NO_CONNECTION           = 8

    def __init__(self, mediaSettings, magnet):
        log('(Torrent) Initialize torrent engine', LOGLEVEL.INFO)
        self._mediaSettings      = mediaSettings
        self._magnet             = magnet
        self._url                = None
        self._shutdown           = False
        self._process            = None
        self._logpipe            = None
        self._file_id            = None
        self._json               = request.Json()
        # "IOError: [Errno 9] Bad file descriptor" FIX!!!
        self._last_status   = {"name":"","state":self.NO_CONNECTION,"state_str":"no_connection","error":"","progress":0,"download_rate":0, "upload_rate":0,"total_download":0,"total_upload":0,"num_peers":0,"num_seeds":0,"total_seeds":-1,"total_peers":-1}
        self._last_files    = []

    def __enter__(self):
        return self

    def start(self):
        if not self._shutdown:
            log('(Torrent) Find free port', LOGLEVEL.INFO)
            port = get_free_port()

            log('(Torrent) Starting torrent2http', LOGLEVEL.INFO)
            startupinfo = None
            if Platform.system == "windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= 1
                startupinfo.wShowWindow = 0

            if _settings.debug:
                self._logpipe = LogPipe(self._debug)

            torrent_options = self._mediaSettings.get_torrent_options(self._magnet, port)
            try:
                self._process = subprocess.Popen(torrent_options, stderr=self._logpipe, stdout=self._logpipe, startupinfo=startupinfo)
            except:
                raise TorrentError("Can't start torrent2http: %s" % str(sys.exc_info()[1]))
            self._url = "http://127.0.0.1:%s/" %port

            start = time.time()
            while not self._shutdown:
                if (time.time() - start) > 5 or not self.isAlive():
                    raise TorrentError("Can't start torrent2http")
                if not self.status(1)['state'] == self.NO_CONNECTION:
                    log("(Torrent) torrent2http successfully started")
                    return True
        return False

    def isAlive(self):
        return self._process and self._process.poll() is None

    def status(self, timeout=10):
        if not self._shutdown:
            try:
                if not self.isAlive():
                    raise TorrentError("torrent2http are not running")
                self._last_status = self._json.request(self._url, "/status", timeout=timeout) or self._last_status
                if self._last_status.get('error'):
                    raise TorrentError("torrent2http error: %s" %self._last_status['error'])
            except (JSONDecodeError, socket.timeout, IOError) as e:
                log('(Torrent) %s: %s' %(e.__class__.__name__, str(e)), LOGLEVEL.INFO)
        return self._last_status

    def files(self, timeout=10):
        if not self._shutdown:
            try:
                if not self.isAlive():
                    raise TorrentError("torrent2http are not running")
                self._last_files = self._json.request(self._url, "/ls", timeout=timeout)['files'] or self._last_files
            except (JSONDecodeError, socket.timeout, IOError) as e:
                log('(Torrent) %s: %s' %(e.__class__.__name__, str(e)), LOGLEVEL.INFO)
        return self._last_files


    def playFile(self, timeout=10):
        files = self.files(timeout)
        if not files:
            return {}
        if self._file_id is None:
            size = 0
            for i, f in enumerate(files):
                mimeType = mimetypes.guess_type(f['name'])
                log('(Torrent) File name: %s, MIME info: %s' %(f['name'], str(mimeType)))
                # if mimeType[0] and mimeType[0][:5] == 'video' and f['size'] > size:
                # if 'video' in str(mimeType) and f['size'] > size:
                if(re.match('.*\.avi|.*\.mp4|.*\.mkv', f['name'])):
                    self._file_id = i
                    urlopen(f['url'], timeout=50)
        try:
            return files[self._file_id]
        except (KeyError, TypeError):
            raise TorrentError("Can not find a file to play")

    def shutdown(self, timeout=1):
        if self.isAlive():
            if self._logpipe:
                log("(Torrent) Shutting down log pipe")
                self._logpipe.close()
            log("(Torrent) Shutting down torrent2http")
            try:
                request.Send().request(self._url, "/shutdown", timeout=timeout)
                start = time.time()
                while (time.time() - start) < 10:
                    time.sleep(0.100)
                    if not self.isAlive():
                        log("(Torrent) torrent2http successfully shutdown", LOGLEVEL.INFO)
                        break
                else:
                    log("(Torrent) Timeout occurred while shutting down torrent2http", LOGLEVEL.WARNING)
            except:
                log("(Torrent) An error occurred while shutting down torrent2http", LOGLEVEL.WARNING)
            if self.isAlive():
                log("(Torrent) Killing torrent2http", LOGLEVEL.WARNING)
                self._process.kill()
            self._logpipe = self._process = None

    def _debug(self, message):
        log("(Torrent) (torrent2http) %s" % message)

    def __exit__(self, *exc_info):
        self.close()
        return not exc_info[0]

    def __del__(self):
        self.close()

    def close(self):
        if hasattr(self, '_json') and not self._shutdown:
            self._shutdown = True
            try:
                self._json.cancel()
                self.shutdown()
            finally:
                self._json = None
                # Clean debris from the cache dir
                if not self._mediaSettings.user_download_path and self._mediaSettings.delete_files:
                    try:
                        clear_media_cache(self._mediaSettings.media_cache_path)
                    except:
                        pass

class Loader(Thread):
    STARTING                = 1
    WAITING_FOR_PLAY_FILE   = 2
    CHECKING_DATA           = 3
    PRELOADING              = 4
    DOWNLOADING_SUBTITLE    = 5
    FINISHED                = 6
    url                     = None
    subtitle                = None

    def __init__(self, mediaSettings, TorrentEngine, item, subtitleURL=None, callback=None):
        log('(Loader) Initialize loader')
        self._item          = item
        self.callbackfn     = callback
        # Torrent
        self._mediaSettings = mediaSettings
        self._TEngine       = TorrentEngine
        # Subtitle
        self._subtitleURL   = subtitleURL
        self._request       = request.Download()
        self._path          = os.path.join(_settings.cache_path, 'temp.zip')
        self._tmppath       = None

        super(Loader, self).__init__(target=self._run)

    def is_done(self, wait=0):
        time.sleep(wait)
        return Loader.url is not None or self.stop.is_set()

    def _run(self):
        if self.callbackfn:
            self.callbackfn(self.STARTING, 0)

        # if self._TEngine.start() and self._getPlayFile() and self._checkData() and (self._isDownloadDone() or self._preloading(self._item.get('stream_info', {}).get('video', {}).get('duration', 0))):
        if self._TEngine.start() and self._getPlayFile() and self._checkData() and self._preloading(self._item.get('stream_info', {}).get('video', {}).get('duration', 0)):
            playFileInfo = self._TEngine.playFile()

            if self._subtitleURL:
                if self.callbackfn:
                    self.callbackfn(self.DOWNLOADING_SUBTITLE, 1)

                filename = os.path.splitext(os.path.basename(playFileInfo['name']))[0]
                if self._item.get('stream_info', {}).get('subtitle', {}).get('language'):
                    filename = ".".join([filename, self._item['stream_info']['subtitle']['language']])
                if self._getSubtitle(os.path.dirname(playFileInfo['save_path']), filename) and os.path.isfile(self._path):
                    Loader.subtitle = self._path

            if self.callbackfn:
                self.callbackfn(self.FINISHED, 1)
            Loader.url = playFileInfo['url']

    def _getPlayFile(self):
        log('(Loader) Waiting on play file')
        if self.callbackfn:
            self.callbackfn(self.WAITING_FOR_PLAY_FILE, 0)
        while not self.stop.is_set():
                if self._TEngine.playFile(1):
                    return not self.stop.is_set()
        return False

    def _checkData(self):
        log('(Loader) Checking data')
        while not self.stop.is_set():
            if self.callbackfn:
                self.callbackfn(self.CHECKING_DATA, 0)
            if self._TEngine.status()['state'] in [self._TEngine.FINISHED, self._TEngine.SEEDING, self._TEngine.DOWNLOADING]:
                return not self.stop.is_set()
            time.sleep(0.100)
        else:
            return False

    def _isDownloadDone(self):
        if self._TEngine.status()['state'] in [self._TEngine.FINISHED, self._TEngine.SEEDING]:
            log('(Loader) Media is downloaded')
            #if self.callbackfn:
             #   self.callbackfn(Loader.PRELOADING, 100)
            return not self.stop.is_set()
        return False

    def _preloading(self, duration=0):
        log('(Loader) Pre-Loading media', LOGLEVEL.INFO)
        if self.callbackfn:
            self.callbackfn(self.PRELOADING, 0)

        progress = 0
        while not self.stop.is_set():
            time.sleep(0.100)

            status = self._TEngine.status()
            if status['download_rate'] <= 0:
                continue

            filestatus = self._TEngine.playFile()

            bytSeconds = status['download_rate']*0.8*1024 # Download rate is reduced by 20 percent to make sure against fluctuations.
            needSizeInProcent = 0.015 # Fix cache size
            if duration > 0:
                # How long does it take to download the entire movie in seconds.
                seconds = filestatus['size']/bytSeconds
                # Does it take longer time than to play the movie? Otherwise we only
                # need a buffer to protect against fluctuations (0.02)
                if seconds > duration:
                    # If a movie has a playback time of 2 hours and we take 3 hours to download the movie,
                    # we can only reach to download 2/3 of the movie. We therefore need to cache 1/3 of the movie before playback.
                    # (Or the user need a new connection)
                    needSizeInProcent = 1-(duration/seconds)
                else:
                    needSizeInProcent = 1-(duration/(duration+60.0)) # 60 seconds cache

            needCacheSize = filestatus['size']*needSizeInProcent
            progressValue = (100/(((needCacheSize)/bytSeconds)*1000))*100
            if self.callbackfn:
                self.callbackfn(self.PRELOADING, progressValue)

            progress = progress+progressValue
            if progress >= 100 or (filestatus['download']*0.45) >= needCacheSize: # We are caching about 65% (filestatus['download']*0.45) more end need (needCacheSize).
                if self.callbackfn:
                    self.callbackfn(self.PRELOADING, (100-progress) > 0 and (100-progress) or 0)
                log('(Loader) Finished with pre-loading media')
                return not self.stop.is_set()

        return False

    def _getSubtitle(self, dirname, filename):
        log('(Loader) Downloading')
        scheme, netloc, path, _, query, _ = urlparse(self._subtitleURL)
        self._request.request(self._path, "%s://%s" %(scheme, netloc), path, dict(parse_qsl(query)))
        if not os.path.isfile(self._path) or self.stop.is_set():
            return False

        log('(Loader) Unzipping')
        with closing(ZipFile(self._path)) as zip:
            for subtitle in zip.namelist():
                if os.path.splitext(subtitle)[1] in ['.aqt', '.gsub', '.jss', '.sub', '.ttxt', '.pjs', '.psb', '.rt', '.smi', '.stl', '.ssf', '.srt', '.ssa', '.ass', '.usf', '.idx']:
                    zip.extract(subtitle, _settings.cache_path)
                    self._tmppath = os.path.join(_settings.cache_path, subtitle)
        if not os.path.isfile(self._tmppath) or self.stop.is_set():
            return False
        os.unlink(self._path)
        self._path = self._tmppath

        log('(Loader) Move')
        self._tmppath = os.path.join(dirname, filename+os.path.splitext(self._path)[1])
        if not os.path.isfile(self._tmppath):
            with open(self._tmppath, 'w') as dst:
                with open(self._path, 'r') as src:
                    dst.write(src.read())
        if not os.path.isfile(self._tmppath) or self.stop.is_set():
            return False
        os.unlink(self._path)
        self._path = self._tmppath
        self._tmppath = None
        return not self.stop.is_set()

    def close(self):
        if hasattr(self, '_tmppath'):
            super(Loader, self).close()
            self._request.cancel()
            if self._tmppath and os.path.isfile(self._tmppath):
                os.unlink(self._tmppath)
            if self._path and os.path.isfile(self._path) and not (Loader.subtitle or Loader.subtitle == self._path):
                os.unlink(self._path)

class TorrentPlayer(xbmc.Player):
    def onPlayBackStarted(self):
        log('(Torrent Player) onPlayBackStarted')

    def onPlayBackResumed(self):
        log('(Torrent Player) onPlayBackResumed')
        self._overlay.close()

    def onPlayBackPaused(self):
        log('(Torrent Player) onPlayBackPaused')
        self._overlay.open()

    def onPlayBackStopped(self):
        log('(Torrent Player) Stop playback')
        self._overlay.close()

    def onPlayBackSeek(self):
        log('(Torrent Player) onPlayBackSeek')
        self.pause()

    def playTorrentFile(self, mediaSettings, magnet, item, subtitleURL=None):
        monitor = xbmc.Monitor()

        with TorrentEngine(mediaSettings, magnet) as _TorrentEngine:
            # Loading
            log('(Torrent Player) Loading', LOGLEVEL.INFO)
            with closing(SafeDialogProgress()) as dialog:
                dialog.create(item['info']['title'])
                dialog.update(0, __addon__.getLocalizedString(30031), ' ', ' ')

                # Update progress dialog
                dialog.set_mentions((101+bool(subtitleURL)))

                def on_update(state, progressValue):
                    if state == Loader.PRELOADING:
                        dialog.update(progressValue, *self._get_status_lines(_TorrentEngine.status()))
                    elif state == Loader.CHECKING_DATA:
                        dialog.update(progressValue, __addon__.getLocalizedString(30037), ' ', ' ')
                    elif state == Loader.WAITING_FOR_PLAY_FILE:
                        dialog.update(progressValue, __addon__.getLocalizedString(30016), ' ', ' ')
                    elif state == Loader.DOWNLOADING_SUBTITLE:
                        dialog.update(progressValue, __addon__.getLocalizedString(30019), ' ', ' ')
                    elif state == Loader.FINISHED:
                        dialog.update(progressValue, __addon__.getLocalizedString(30020), ' ', ' ')

                with Loader(mediaSettings, _TorrentEngine, item, subtitleURL, on_update) as _loader:
                    while not _loader.is_done(0.100):
                        if monitor.abortRequested() or dialog.iscanceled():
                            raise Abort()

            # Starts the playback
            log('(Torrent Player) Start the playback', LOGLEVEL.INFO)
            self.play(Loader.url, xbmcItem(**item))

            # Waiting for playback to start
            log('(Torrent Player) Waiting for playback to start')
            for _ in range(300):
                if self.isPlaying():
                    break
                time.sleep(0.100)
            else:
                raise Error('Playback is terminated due to timeout', 30318)

            if Loader.subtitle:
                log('(Torrent Player) Add subtitle to the playback')
                self.setSubtitles(Loader.subtitle)

            with OverlayText() as self._overlay:
                while not monitor.abortRequested() and self.isPlaying():
                    if self._overlay.isShowing():
                        self._overlay.setText("\n".join(self._get_status_lines(_TorrentEngine.status())))
                        time.sleep(0.100)
                        continue
                    time.sleep(0.250)
                log('(Torrent Player) The playback has stop')

    def _get_status_lines(self, status):
            if status:
                if status['state'] in [TorrentEngine.DOWNLOADING, TorrentEngine.FINISHED, TorrentEngine.SEEDING]:
                    return [
                        __addon__.getLocalizedString(30021),
                        __addon__.getLocalizedString(30008) %(shortenBytes(status['download_rate']*1024), shortenBytes(status['upload_rate']*1024)),
                        __addon__.getLocalizedString(30015)+str(status['num_seeds'])
                    ]
                if status['state'] in [TorrentEngine.FINISHED, TorrentEngine.SEEDING]:
                    return [
                        __addon__.getLocalizedString(30022),
                        ' ',
                        ' '
                    ]
            return [
                __addon__.getLocalizedString(30036),
                __addon__.getLocalizedString(30015)+str(status['num_seeds']),
                ' '
            ]
