#!/usr/bin/python
import os
import sys
import xbmc
import xbmcvfs
from datetime import date
from kodipopcorntime.exceptions import Error
from kodipopcorntime.logging import log, LOGLEVEL
from .base import _Base, _MetaClass

__addon__ = sys.modules['__main__'].__addon__

SPECIAL_DATES = (
    {
        'name': 'christmass',
        'image': 'xmass.jpg',
        'start': {'month': 12, 'day': 22},
        'end': {'month': 12, 'day': 27},
    },
    {
        'name': 'new year',
        'image': 'new_year.jpg',
        'start': {'month': 12, 'day': 29},
        'end': {'month': 12, 'day': 31},
    },
    {
        'name': 'new year 2',
        'image': 'new_year.jpg',
        'start': {'month': 1, 'day': 1},
        'end': {'month': 1, 'day': 5},
    },
    {
        'name': 'valentine',
        'image': 'valentine.jpg',
        'start': {'month': 2, 'day': 13},
        'end': {'month': 2, 'day': 15},
    },
    {
        'name': 'halloween',
        'image': 'haloween.jpg',
        'start': {'month': 10, 'day': 28},
        'end': {'month': 10, 'day': 31},
    },
)


class MetaAddon(_MetaClass):
    def _base_url(cls):
        cls.base_url = sys.argv[0]

    def _handle(cls):
        cls.handle = int(sys.argv[1])

    def _cur_uri(cls):
        cls.cur_uri = sys.argv[2][1:]

    def _language(cls):
        cls.language = xbmc.getLanguage(xbmc.ISO_639_1)

    def _cache_path(cls):
        _path = xbmcvfs.translatePath("special://profile/addon_data/%s/cache" % cls.id)
        if not os.path.exists(_path):
            os.makedirs(_path)
            if not os.path.exists(_path):
                raise Error("Unable to create cache directory %s" % _path, 30322)
        cls.cache_path = _path

    def _resources_path(cls):
        cls.resources_path = os.path.join(__addon__.getAddonInfo('path'), 'resources')

    def _debug(cls):
        cls.debug = __addon__.getSetting("debug") == 'true'

    def _id(cls):
        cls.id = __addon__.getAddonInfo('id')

    def _name(cls):
        cls.name = __addon__.getAddonInfo('name')

    def _version(cls):
        cls.version = __addon__.getAddonInfo('version')

    def _fanart(cls):
        today = date.today()

        # Check special dates
        for special_date in SPECIAL_DATES:
            start_date = date(today.year, special_date['start']['month'], special_date['start']['day'])
            end_date = date(today.year, special_date['end']['month'], special_date['end']['day'])

            if start_date <= today <= end_date:
                log(
                    '(settings-date) {0} {1}'.format(special_date['name'], today),
                    LOGLEVEL.INFO,
                )
                cls.fanart = os.path.join(
                    __addon__.getAddonInfo('path'),
                    'resources',
                    'media',
                    'background',
                    special_date['image'],
                )
                break
        # No special date
        else:
            log('(settings-date) no condition met {0}'.format(today), LOGLEVEL.INFO)
            cls.fanart = __addon__.getAddonInfo('fanart')

    def _info_image(cls):
        cls.info_image = os.path.join(__addon__.getAddonInfo('path'), 'resources', 'media', 'info.png')

    def _warning_image(cls):
        cls.warning_image = os.path.join(__addon__.getAddonInfo('path'), 'resources', 'media', 'warning.png')

    def _error_image(cls):
        cls.error_image = os.path.join(__addon__.getAddonInfo('path'), 'resources', 'media', 'error.png')

    def _limit(cls):
        cls.limit = 20

    def _last_update_id(cls):
        cls.last_update_id = __addon__.getSetting("last_update_id")


class Addon(_Base, metaclass=MetaAddon):
    pass
