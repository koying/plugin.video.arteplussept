
# coding=utf-8
# -*- coding: utf-8 -*-
#
# plugin.video.arteplussept, Kodi add-on to watch videos from http://www.arte.tv/guide/fr/plus7/
# Copyright (C) 2015  known-as-bmf
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

from xbmcswift2 import Plugin
from xbmcswift2 import actions
import requests
import os
import urllib2
import time
import datetime
import xbmcvfs


plugin = Plugin()

base_url = 'http://www.arte.tv'
video_json = 'https://api.arte.tv/api/player/v1/config/{lang}/{id}'
daily_json = base_url + '/hbbtvv2/services/web/index.php/OPA/v3/programs/{date}/{lang}'

headers = {'user-agent': plugin.name + '/' + plugin.addon.getAddonInfo('version')}

quality_map = {0: 'SQ', 1: 'EQ', 2: 'HQ', 3: 'MQ'}

# Settings
language = 'fr' if plugin.get_setting('lang', int) == 0 else 'de'
prefer_vost = plugin.get_setting('prefer_vost', bool)
quality = plugin.get_setting('quality', int)
download_folder = plugin.get_setting('download_folder', str)
download_quality = plugin.get_setting('download_quality', int)
download_nfo = plugin.get_setting('download_nfo', bool)


def get_menu_items():
    return [(plugin.url_for('all'), 30001)]


def get_dates():
    today = datetime.date.today()
    one_day = datetime.timedelta(days=1)

    dates = []
    dates.append((str(today), plugin.get_string(30008))) # Today
    dates.append((str(today - one_day), plugin.get_string(30009))) # Yesterday
    for i in xrange(2, 8): #TODO: find better interval
        cdate = today - (one_day * i)
        dates.append((str(cdate), '{d:%A}, {d:%d}'.format(d=cdate)))
    return dates


@plugin.route('/')
def index():
    items = [{
        'label': plugin.get_string(sid),
        'path': path
    } for path, sid in get_menu_items()]
    return items


def flatten(l):
  return [item for sublist in l for item in sublist]


def get_last7days():
    return flatten([get_day(date) for (date, _) in get_dates()])


def get_day(date):
    url = daily_json.format(date=date, lang=language)
    data = load_json(url)
    return data['programs']


@plugin.route('/all', name='all')
def all_videos():
    plugin.set_content('tvshows')

    # create list item & filter programs without 'video' (live streams ?)
    items = [create_item(program) for program in get_last7days() if program.get('video') is not None and program['video'].get('durationSeconds') is not None and program['video'].get('durationSeconds') > 180]
    # sort by airdate desc
    items.sort(key=lambda item: item['info']['aired'], reverse=True)

    return plugin.finish(items)


@plugin.route('/play/<vid>', name='play')
def play(vid):
    return plugin.set_resolved_url(create_video(vid))


@plugin.route('/enqueue/<vid>', name='enqueue')
def enqueue(vid):
    plugin.add_to_playlist([create_video(vid)])


@plugin.route('/download/<vid>', name='download')
def download_file(vid):
    if download_folder:
        video = create_video(vid, True)

#       <episodedetails>
#        <title>A comme Aardvark</title>
#        <plot>Oreilles d'├óne, queue de kangourou, groin de porc et une langue de 40 centim├¿tres... : l'aardvark ? nom anglais d├⌐riv├⌐ de l'afrikaans erdvark, appel├⌐ en fran├ºais oryct├⌐rope du Cap, mammif├¿re fourmilier d'Afrique, joue un r├┤le ├⌐cologique important en contr├┤lant la prolif├⌐ration des termites. Il peut atteindre 1,70 m├¿tres de long et peser 70 kilos. Il est tr├¿s rare d'en voir un, mais ├á force de pers├⌐v├⌐rance, l'├⌐quipe de tournage y est parvenue...</plot>
#        <aired>2016-05-20</aired>
#        <thumb>https://static-cdn.arte.tv/resize/iHUnL7JeIHhKhaq67nQ8AKqQSdc=/940x530/smart/apios/Img_data/18/060183-000-A_a-wie-aadvark_05.jpg</thumb>
#        <season>0</season>
#        <episode>0</episode>
#       </episodedetails>

        if download_nfo:
          filename_nfo = vid + '_' + video['label'] + os.extsep + 'nfo'
          fo = xbmcvfs.File(os.path.join(download_folder, filename_nfo), 'wb')
          fo.write("<episodedetails>")
          fo.write(str("<title>" + video['info']['title'] + "</title>"));
          fo.write(str("<plot>" + video['info']['plot'] + "</plot>"));
          fo.write(str("<aired>" + video['info']['aired'] + "</aired>"));
          fo.write(str("<thumb>" + video['thumbnail'] + "</thumb>"));
          fo.write("<season>0</season>");
          fo.write("<episode>0</episode>");
          fo.write("</episodedetails>")
          fo.close()

        filename = vid + '_' + video['label'] + os.extsep + 'mp4'
        block_sz = 8192
        f = xbmcvfs.File(os.path.join(download_folder, filename), 'wb')
        u = urllib2.urlopen(video['path'])

        plugin.notify(filename, plugin.get_string(30010))
        while True:
            buff = u.read(block_sz)
            if not buff:
                break
            f.write(buff)
        f.close()
        plugin.notify(filename, plugin.get_string(30011))
        
    else:
        plugin.notify(plugin.get_string(30013), plugin.get_string(30012))


def create_item(data):
    broadcast = data.get('broadcast')
    video = data.get('video')

    airdate = parse_date(broadcast.get('broadcastBeginRounded')[:-6], '%a, %d %b %Y %H:%M:%S') if broadcast.get('broadcastBeginRounded') else None
    programId = str(video.get('programId'))
    label = '[B]{title}[/B]'.format(title=video.get('title').encode('utf8'))
    # suffixes
    if video.get('subtitle'):
        label += ' - {subtitle}'.format(subtitle=video.get('subtitle').encode('utf8'))

    item = {
        'label': label,
        'path': plugin.url_for('play', vid=programId),
        'thumbnail': video.get('imageUrl'),
        'is_playable': True,
        'info_type': 'video',
        'info': {
            'title': video.get('title'),
            'duration': int(video.get('durationSeconds')),
            'genre': video.get('genrePresse'),
            'plot': video.get('shortDescription'),
            'plotoutline': video.get('teaserText'),
            # year is not correctly used by kodi :(
            # the aired year will be used by kodi for production year :(
            'year': int(video.get('productionYear')),
            'country': [country['label'] for country in video.get('productionCountries')],
            'director': video.get('director'),
            'aired': str(airdate)
        },
        'properties': {
            'fanart_image': video.get('imageUrl'),
        },
        'context_menu': [
            (plugin.get_string(30021), actions.background(plugin.url_for('download', vid=programId))),
            (plugin.get_string(30020), actions.background(plugin.url_for('enqueue', vid=programId)))
        ],
    }
    return item


def create_video(vid, downloading=False):
    chosen_quality = quality if not downloading else download_quality

    data = load_json(video_json.format(id=vid, lang=language))['videoJsonPlayer']
    filtered = []
    video = None

    # we try every quality (starting from the preferred one)
    # if it is not found, try every other from highest to lowest
    for q in [quality_map[chosen_quality]] + [i for i in ['SQ', 'EQ', 'HQ', 'MQ'] if i is not quality_map[chosen_quality]]:
        # vost preferred
        if prefer_vost:
            filtered = [item for item in data['VSR'].values() if match(item, q, True)]
        # no vost found or vost not preferred
        if len(filtered) == 0:
            filtered = [item for item in data['VSR'].values() if match(item, q)]

        # here len(filtered) sould be 1
        if len(filtered) == 1:
            video = filtered[0]
            break
    airdate = parse_date(data['VRA'][:-6], '%d/%m/%Y %H:%M:%S') if "VRA" in data else datetime.datetime.now()
    title = data['VTI'].encode('utf8')
    if "subtitle" in data:
        title += ' - {subtitle}'.format(subtitle=data['subtitle'].encode('utf8'))

    return {
        'label': data['caseProgram'] if downloading else None, #data['VTI'],
        'path': video['url'],
        'thumbnail': data['VTU']['IUR'],
        'info': {
            'title': title,
            'duration': str(data['VDU']),
            'genre': data['genre'].encode('utf8') if "genre" in data else None,
            'plot': data['V7T'].encode('utf8') if "V7T" in data else None,
            'aired': str(airdate)
        }
    }

# versionProg :
#       1 = Version langue URL
#       2 = Version inverse de langue URL
#       3 = VO-STF VOSTF
#       8 = VF-STMF ST sourds/mal
def match(item, chosen_quality, vost=False):
    return (item['mediaType'] == "mp4") and (item['quality'] == chosen_quality) and ((vost and item['versionProg'] == 3) or (not vost and item['versionProg'] == 1))


def load_json(url, params=None):
    r = requests.get(url, params=params, headers=headers)
    return r.json()


# cosmetic parse functions
def parse_date(datestr, format):
    date = None
    # workaround for datetime.strptime not working (NoneType ???)
    try:
        date = datetime.datetime.strptime(datestr, format)
    except TypeError:
        date = datetime.datetime.fromtimestamp(time.mktime(time.strptime(datestr, format)))
    return date


if __name__ == '__main__':
    plugin.run()
