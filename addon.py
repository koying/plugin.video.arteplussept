#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#     Copyright (C) 2015 known-as-bmf
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

from xbmcswift2 import Plugin
from xbmcswift2 import actions
import xbmc
import os
import json
import urllib2

base_url = 'http://www.arte.tv'

categories = [('new',         30001),
              ('selection',   30002),
              ('most_viewed', 30003),
              ('last_chance', 30004),
              ('themes',      30005)]

themes = [('ACT', 3000501),
          ('DOC', 3000502),
          ('DEC', 3000503),
          ('EUR', 3000504),
          ('GEO', 3000505),
          ('SOC', 3000506),
          ('JUN', 3000507),
          ('AUT', 3000508),
          ('CIN', 3000509),
          ('ART', 3000510),
          ('CUL', 3000511),
          ('ENV', 3000512)]


# http://www.arte.tv/papi/tvguide/videos/stream/{lang}/{id}_PLUS7-{lang}/{protocol}/{quality}.json
# lang     : F | D
# protocol : HBBTV | RTMP
# quality  : SQ (High) | EQ (Med) | HQ (Low)
video_json = base_url + '/papi/tvguide/videos/stream/{lang}/{id}_PLUS7-{lang}/{protocol}/ALL.json'

# http://www.arte.tv/papi/tvguide/videos/livestream/{lang}/
# lang : F | D
live_json = base_url + '/papi/tvguide/videos/livestream/{lang}/'

# http://www.arte.tv/guide/{lang}/plus7/par_dates.json?value={date}
# lang : fr | de
# date : date sous la forme yyyy-mm-jj

# http://www.arte.tv/guide/{lang}/plus7/par_themes.json?value={genre}
# lang  : fr | de
# genre : trigramme du genre (ACT DOC DEC EUR GEO SOC JUN AUT CIN ART CUL ENV)

# http://www.arte.tv/guide/{lang}/plus7/par_emissions.json?value={emission}
# lang     : fr | de
# emission : trigramme de l'emission (VMI TSG AJT JTE COU FUM KAR DCA MTR PNB PHI SUA TRA VOX XEN YOU

plugin = Plugin()

user_agent = plugin.name + '/' + plugin.addon.getAddonInfo('version')
print user_agent

language = 'fr' if plugin.get_setting('lang', int) == 0 else 'de'
quality = plugin.get_setting('quality', int)
protocol = 'HBBTV' if plugin.get_setting('protocol', int) == 0 else 'RMP4'
download_folder = plugin.get_setting('download_folder', str)
download_quality = plugin.get_setting('download_quality', int)


@plugin.route('/')
def index():
    items = [{
        'label': plugin.get_string(value),
        'path': plugin.url_for('show_' + key)
    } for key, value in categories]
    items.append({
        'label': plugin.get_string(30006),
        'path': plugin.url_for('play_live'),
        'is_playable': True
    })
    return items


@plugin.route('/new', name='show_new',
              options={'json_url': base_url + '/guide/{lang}/plus7.json'})
@plugin.route('/selection', name='show_selection',
              options={'json_url': base_url + '/guide/{lang}/plus7/selection.json'})
@plugin.route('/most_viewed', name='show_most_viewed',
              options={'json_url': base_url + '/guide/{lang}/plus7/plus_vues.json'})
@plugin.route('/last_chance', name='show_last_chance',
              options={'json_url': base_url + '/guide/{lang}/plus7/derniere_chance.json'})
@plugin.route('/themes/<theme>', name='show_theme',
              options={'json_url': base_url + '/guide/{lang}/plus7/par_themes.json?value={theme}'})
def list(json_url, theme=None):
    plugin.set_content('tvshows')
    if theme is not None:
        data = json.loads(get_url(json_url.format(lang=language, theme=theme)))
    else:
        data = json.loads(get_url(json_url.format(lang=language)))
    items = [{
        'label': video['title'],
        'path': plugin.url_for('play', id=str(video['em'])),
        'thumbnail': video['image_url'],
        'is_playable': True,
        'info_type': 'video',
        'info': {
            'label': video['title'],
            'title': video['title'],
            'duration': str(video['duration']),
            'genre': video['video_channels'] if video['video_channels'] is not None else '',
            'plot': video['desc'] if video['desc'] is not None else '',
            #'aired': video['airdate_long'].encode('utf-8') if video['airdate_long'] is not None else '',
        },
        'properties': {
            'fanart_image': video['image_url'],
        },
        'context_menu': [
            (plugin.get_string(30021), actions.background(plugin.url_for('download', id=str(video['em'])))),
        ],
    } for video in data['videos']]
    return plugin.finish(items)


@plugin.route('/show_themes', name='show_themes')
def show_themes():
    items = [{
        'label': plugin.get_string(value),
        'path': plugin.url_for('show_theme', theme=key)
    } for key, value in themes]
    return plugin.finish(items)


@plugin.route('/play/<id>', name='play')
def play(id):
    return plugin.set_resolved_url(create_item(id))


@plugin.route('/download/<id>', name='download')
def download_file(id):
    data = load_json(id)
    if download_folder:
        url = None
        for version in data['video']['VSR']:
            if version['VQU'] == quality_map[download_quality]:
                url = version['VUR']
                break
        if not url:
            url = data['video']['VSR'][0]['VUR']
        title = data['video']['VTI']
        filename = id + '_' + data['video']['VST']['VNA'] + os.extsep + 'mp4'

        block_sz = 8192
        f = open(os.path.join(download_folder, filename), 'wb')
        u = urllib2.urlopen(url)
        xbmc.executebuiltin('XBMC.Notification({title}, {message}, {duration})'.format(title='Downloading', message=title, duration=5000))
        while True:
            buffer = u.read(block_sz)
            if not buffer:
                break
            f.write(buffer)
        f.close()
        xbmc.executebuiltin('XBMC.Notification({title}, {message}, {duration})'.format(title='Done downloading', message=title, duration=5000))
    else:
        # TODO: i18n
        xbmc.executebuiltin('XBMC.Notification({title}, {message}, {duration})'.format(title='Error', message='Please set download folder in settings.', duration=5000))


@plugin.route('/live', name='play_live')
def play_live():
    fetch_url = live_json.format(lang=language[0].upper())
    data = json.loads(get_url(fetch_url))
    url = data['video']['VSR'][0]['VUR']
    return plugin.play_video({
        'label': data['video']['VTI'],
        'path': (url + ' live=1')
    })


quality_map = {0: 'SQ', 1: 'EQ', 2: 'HQ'}
def create_item(id):
    data = load_json(id)
    url = None
    for version in data['video']['VSR']:
        if version['VQU'] == quality_map[quality]:
            url = version['VUR']
            break
    if not url:
        url = data['video']['VSR'][0]['VUR']
    item = {
        'label': data['video']['VTI'],
        'path': url
    }
    return item


def load_json(id):
    fetch_url = video_json.format(id=id, lang=language[0].upper(), protocol=protocol)
    return json.loads(get_url(fetch_url))


def get_url(url):
    request = urllib2.Request(url)
    request.add_header('User-Agent', user_agent)
    opener = urllib2.build_opener()
    body = opener.open(request).read()
    return body


if __name__ == '__main__':
    plugin.run()
