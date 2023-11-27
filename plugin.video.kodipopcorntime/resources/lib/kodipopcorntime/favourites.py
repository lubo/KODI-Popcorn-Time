import json
from urllib.request import Request, urlopen
import os
import xbmc
import xbmcaddon
import xbmcvfs
import hashlib

from kodipopcorntime.logging import log


__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
__addondir__ = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))

_json_file = os.path.join(__addondir__, 'favourites.json')
_json_movie_file = os.path.join(__addondir__, 'test.json')

_skeleton = {
    "movies": [],
    "tvshows": [],
    "anime": [],
}


def get_favourites_from_file():
    """Gets all favourites from the JSON file.

    If the JSON file does not exist, a skeleton file is generated.
    """
    if not os.path.isfile(_json_file):
        create_skeleton_file()

    with open(_json_file) as json_read:
        return json.load(json_read)


def set_favourites_to_file(favourites):
    """Overwrites the JSON file with the `favourites` dictionary"""
    with open(_json_file, mode='w') as json_write:
        json_write.write(json.dumps(favourites, indent=3))


def create_skeleton_file():
    set_favourites_to_file(_skeleton)
    log("(Favourites) File created")


def _add_to_favs(mediatype, data):
    favourites = get_favourites_from_file()
    log("(Favourites) _add_to_favs %s" % favourites)

    string1 ={'action': 'watch_list', 'categ': 'movie_test', 'order': '-1'}
    filename = 'movies.browse.%s' %hashlib.md5(str(string1).encode()).hexdigest()
    log("(Favourites) filename %s" % filename)
    try:
        os.remove(os.path.join(__addondir__, 'cache', filename))
    except:
        pass

    add_favourite_by_type(new_fav_id=data, fav_type=mediatype, favourites=favourites)

    log("(Favourites2) _add_to_favs %s" % favourites)
    set_favourites_to_file(favourites)

    xbmc.executebuiltin('Notification(%s, %s favourite has been added, 5000)' % (__addonname__, mediatype))


def _remove_from_favs(mediatype, data):
    favourites = get_favourites_from_file()
    log("(Favourites) _remove_from_favs %s" % favourites)

    string1 ={'action': 'watch_list', 'categ': 'movie_test', 'order': '-1'}
    filename = 'movies.browse.%s' %hashlib.md5(str(string1).encode()).hexdigest()
    log("(Favourites) filename %s" % filename)
    try:
        os.remove(os.path.join(__addondir__, 'cache', filename))
    except:
        pass

    if data == 'all':
        _clear_favourites(mediatype)
    else:
        remove_favourite_by_type(fav_id=data, fav_type=mediatype, favourites=favourites)
        log("(Favourites2) _remove_from_favs %s" % favourites)
        set_favourites_to_file(favourites)

    xbmc.executebuiltin('Notification(%s, %s favourite has been removed, 5000)' % (__addonname__, mediatype))
    if mediatype == 'movies':
        pass
    else:
        xbmc.executebuiltin('Container.Refresh')


def _get_favs(mediatype):
    favourites = get_favourites_from_file()
    log("(Favourites) _get_favs %s" % favourites)
    return favourites.get(mediatype)


def _clear_favourites(mediatype):
    if mediatype == 'all':
        create_skeleton_file()
        return

    # Get the existing favourites
    favourites = get_favourites_from_file()
    # Overwrite the favourites for the specified mediatype with an empty list
    favourites[mediatype] = []
    # Save changes to the JSON file
    set_favourites_to_file(favourites)


def add_favourite_by_type(new_fav_id, fav_type, favourites):
    """
    Modifies the `favourites` dictionary by adding the `new_fav_id` to its
    `fav_type` inner list, if it is not already a favourite.

    Examples of `fav_type` are: 'movies', 'tvshows', 'anime'
    """
    type_favourites = favourites.get(fav_type)

    if all(fav['id'] != new_fav_id for fav in type_favourites):
        type_favourites.append({'id': str(new_fav_id)})


def remove_favourite_by_type(fav_id, fav_type, favourites):
    """
    Modifies the `favourites` dictionary by removing the `fav_id` from its
    `fav_type` inner list.

    Examples of `fav_type` are: 'movies', 'tvshows', 'anime'
    """
    favourites[fav_type] = filter(
        lambda fav: fav['id'] != fav_id,
        favourites.get(fav_type),
    )

def _create_movie_favs():
    movie_favs = _get_favs('movies')
    log("(Favourites_movie) %s" % movie_favs)
    movie_favs1 = []
    for fav in movie_favs:
        log("(Favourites_movie) %s" % fav)
        search = '%s/movie/%s' % ('https://shows.cf', fav['id'])
        req = Request(search, headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.66 Safari/537.36", "Accept-Encoding": "none"})
        response = urlopen(req)
        movie_fav = json.loads(response.read())
        movie_favs1.append(movie_fav)
        log("(Favourites_movie) %s" % movie_favs1)
    with open(_json_movie_file, mode='w') as json_write:
        json_write.write(json.dumps(movie_favs1))
        log("(Favourites_movie) %s" % movie_favs1)
