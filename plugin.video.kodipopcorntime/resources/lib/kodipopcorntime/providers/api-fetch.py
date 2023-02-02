import os
import sys
import xbmcaddon
import xbmcvfs
from kodipopcorntime import settings
from .apifetch import movies as api_movies
from .apifetch import tvShows as api_tvShows
from .apifetch import anime as api_anime
from kodipopcorntime.logging import log, LOGLEVEL
from kodipopcorntime import favourites as _favs
__addon__ = sys.modules['__main__'].__addon__

_categories = {
    '30350': 'Movies',
    '30351': 'TVShows',
    '30352': 'Anime'
}

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
__addondir__ = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))

_json_file = os.path.join(__addondir__, 'test.json')

_proxy_identifier = 'api-fetch.proxies'

def _getDomains():
    domains = [
        # Currently working, doesn't support anime yet
        "https://popcorn-time.ga"
    ]

    # User domains have highest priority
    return settings.movies.proxies+domains

def folders(action, **kwargs):
    '''folders are used to create lists of genres, shows, animes and seasons
       :param action: (string) When index is call, this parameter will be empty, then set an operation.
       :param kwargs: (dict) When index is call, this parameter will be empty, then contains the user parameters.
       :return: (list) Return a list with items. (Only the first item are used when index is call.)
    '''

    _dom = _getDomains()

    if action == 'categories':
        '''Action categories creates list of categories '''
        items= []
        for n in __addon__.getLocalizedString(30353).split(','):
            if _categories.get(n):
                path = os.path.join(settings.addon.resources_path, 'media', 'categories', '%s.png' %_categories[n])
                items.append({
                    "label": __addon__.getLocalizedString(int(n)),
                    "icon": path,
                    "thumbnail": path,
                    "params": {
                        "endpoint": "folders",                                  # endpoint is required
                        'action': "cat_%s" %_categories[n]                      # action carries an operation
                    }
                })
        return items

    if action == 'cat_Movies':
        '''Action cat_Movies creates a list of options for movies '''
        return api_movies._folders(action)

    if action == 'genres_movies':
        '''Action genres_movies creates a list of genres'''
        return api_movies._folders(action)

    if action == 'favourites_movies':
        '''Action favorites_TV-Shows gets saved favourites for TV Shows'''
        return api_movies._favourites(_dom, **kwargs)

    if action == 'cat_TVShows':
        '''Action cat_TVShows creates a list of options for TV Shows '''
        return api_tvShows._folders(action)

    if action == 'genres_TV-shows':
        '''Action genres_movies creates a list of genres'''
        return api_tvShows._folders(action)

    if action == 'favorites_TV-Shows':
        '''Action favorites_TV-Shows gets saved favourites for TV Shows'''
        return api_tvShows._favourites(_dom, **kwargs)

    if action == 'cat_Anime':
        '''Action cat_TVShows creates a list of options for TV Shows '''
        return api_anime._folders(action)

    if action == 'genres_anime':
        '''Action genres_anime creates a list of genres'''
        return api_anime._folders(action)

    if action == 'favorites_Anime':
        '''Action favorites_TV-Shows gets saved favourites for TV Shows'''
        return api_anime._favourites(_dom, **kwargs)


    if action == 'show-list':
        '''Action show-list creates a list of TV Shows'''
        return api_tvShows._shows(_dom, **kwargs)

    if action == 'show-seasons':
        '''Action show-seasons creates a list of seasons for a TV Show'''
        return api_tvShows._seasons(_dom, **kwargs)

    if action == 'anime-list':
        '''Action anime-list creates a list of Animes'''
        return api_anime._shows(_dom, **kwargs)

    if action == 'anime-seasons':
        '''Action anime-seasons creates a list of seasons for a Animes'''
        return api_anime._seasons(_dom, **kwargs)

    # There was no action, therefore has index be called
    return [{
        "label": __addon__.getLocalizedString(30030),                               # "label" is require
        "icon": os.path.join(settings.addon.resources_path, 'media', 'movies.png'),
        "thumbnail": os.path.join(settings.addon.resources_path, 'media', 'movies.png'),
        "params": {
            "endpoint": "folders",                                                  # "endpoint" is require
            'action': "categories"                                                         # Require when calling browse or folders (Action is used to separate the content)
        }
    }]

def browse(action, page, **kwargs):
    '''browse are used to returning parameters used for 'Request' when a movie or show episodes list is displayed.
       :param action: (string) This parameter set an operation
       :param page: (int) Contains the current page number
       :param kwargs: (dict) Contain user parameters
       :return: (dict) Return parameters used for 'Request'
    '''
    if kwargs['categ'] == 'movies':
        return {
            'proxies': _getDomains(),
            'path': "/movies/%s" %page,
            'params': {
                'genre': action == 'genre' and kwargs['genre'] or 'all',
                'sort': action == 'genre' and "seeds" or action,
                'order': kwargs['order']
            },
            'proxyid': _proxy_identifier
        }
    else:
        if kwargs['categ'] == 'movie_test':
            return {
                'proxies': '',
                'path': 'movie_favs',
                'params': {

                },
                'proxyid': _proxy_identifier
            }
        else:
            return {
                'proxies': _getDomains(),
                'path': "/%s/%s" % (kwargs['categ'], action),
                'params': {
                },
                'proxyid': _proxy_identifier
            }

def browse_build(data, action, page, **kwargs):
    '''browse_build are used to create a dict with the items when a movie or episode list is displayed.

       :param data: Contains a list with data from 'Request'
       :param action: (string) This parameter set an operation
       :param page: (int) Contains the current page number
       :param kwargs: (dict) Contain user parameters that were given to browse function
       :return: Return a dict
    '''
    items = []

    if kwargs['categ'] == 'movies':
        for movie in data:
            item = api_movies._create_item(movie)
            if item:
                items.append(item)
        if not items:
            return {}
    else:
        if kwargs['categ'] == 'movie_test':
            for movie in data:
                item = api_movies._create_item(movie)
                if item:
                    items.append(item)
            if not items:
                return {}
        else:
            episodes = data['episodes']
            for episode in episodes:
                episode2 = []
                episode2.append(episode)
                episode2.append(kwargs)
                if kwargs['categ'] == 'show':
                    item = api_tvShows._create_item(episode2)
                else:
                    item = api_anime._create_item(episode2)
                if item:
                    items.append(item)
            if not items:
                return {}
            items = sorted(items, key=lambda k: k['info']['episode'])
    return {
        'pages': 50, #int(movie_count/settings.addon.limit) + (movie_count%settings.addon.limit > 0), # Specify the total number of pages (require)
        'items': items
    }

def search(query, page, **kwargs):
    '''This function is only used when we are calling search for movies'''
    _dom = _getDomains()
    _proxy = _proxy_identifier
    return api_movies._search(_proxy, _dom, query, page, **kwargs)

def search_build(data, query, page, **kwargs):
    '''This function is only used when we are calling search for movies'''
    return api_movies._search_build(data, query, page, **kwargs)
