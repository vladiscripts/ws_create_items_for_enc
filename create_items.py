#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script creates new items on Wikidata based on certain criteria.

* When was the (Wikipedia) page created?
* When was the last edit on the page?
* Does the page contain interwiki's?

This script understands various command-line arguments:

-lastedit         The minimum number of days that has passed since the page was
                  last edited.

-pageage          The minimum number of days that has passed since the page was
                  created.

-touch            Do a null edit on every page which has a wikibase item.
                  Be careful, this option can trigger edit rates or captachas
                  if your account is not autoconfirmed.

"""
#
# (C) Multichill, 2014
# (C) Pywikibot team, 2014-2019
#
# Distributed under the terms of the MIT license.
#
from __future__ import absolute_import, division, unicode_literals
from datetime import timedelta
from textwrap import fill
import sys
import json
import re
import datetime, pytz
from typing import List
import pywikibot
from pywikibot import pagegenerators
from bot import NewItemRobot
from vladi_helpers.file_helpers import json_save_to_file, json_load_from_file


def main(args: list, settings: dict, prefixes: dict):
    """
    Process command line arguments and invoke bot.

    If args is an empty list, sys.argv is used.

    @param args: command line arguments
    @type args: str
    """
    generator, options = pagegenerator(args)
    if not generator:
        pywikibot.bot.suggest_help(missing_generator=True)
        return False

    bot = NewItemRobot(generator, settings, prefixes, **options)
    user = pywikibot.User(bot.site, bot.site.username())
    if bot.getOption('touch') == 'newly' \
            and 'autoconfirmed' not in user.groups():
        pywikibot.warning(fill(
            'You are logged in as {}, an account that is '
            'not in the autoconfirmed group on {}. Script '
            'will not touch pages linked to newly created '
            'items to avoid triggering edit rates or '
            'captachas. Use -touch param to force this.'
                .format(user.username, bot.site.sitename)))
        bot.options['touch'] = False
    bot.run()
    return True


def make_sql(lastedit_days:int):
    x = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')

    categories = ','.join(['"%s"' % d['category_of_articles'] for prefix, d in prefixes.items()])
    #  'БЭЮ', 'БСЭ1' мелкие словарные статьи или масса перенаправлений
    sql = f"""
    SELECT page_namespace,  page_title
    FROM ruwikisource_p.page
        JOIN ruwikisource_p.categorylinks 
            ON cl_from = page_id
            AND page_namespace = 0 
            AND cl_to IN ({categories})
            AND page_is_redirect = 0
        LEFT JOIN ruwikisource_p.categorylinks cw 
            ON cw.cl_from = page_id
            AND cw.cl_to = "Викиданные:Страницы_с_элементами"
        LEFT JOIN ruwikisource_p.categorylinks cr 
            ON cr.cl_from = page_id
            AND cr.cl_to LIKE "%еренаправлени%"
        JOIN revision
            ON page_latest = rev_id
            AND rev_timestamp < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL {lastedit_days} DAY)
    WHERE cw.cl_to IS NULL AND cr.cl_to IS NULL;
    """.replace('\n', ' ').strip()
    # INNER JOIN revision ON page_latest = rev_id
    #    AND rev_timestamp BETWEEN DATE_SUB(NOW(), INTERVAL {lastedit_days} DAY) AND NOW()

    # AND NOT (page_title LIKE 'НСТ/%/ДО' OR page_title LIKE 'ЭСГ/%/ДО')
    # AND cl_to IN ('ЭСГ', 'МСЭ2', 'РЭСБ', 'ТЭ1', 'НЭС', 'ППБЭС:ВТ', 'НСТ', 'ПБЭ', 'ВЭЛ:ВТ', 'НЭСГ', 'ГСС:ДО')
    return sql

    # sql = 'SELECT  page_namespace,  page_title FROM ruwikisource_p.page limit 10;'


def pagegenerator(args: List[str]):
    # Process global args and prepare generator args parser
    gen_factory = pagegenerators.GeneratorFactory()
    local_args = pywikibot.handle_args(args)
    # for arg in local_args:
    #     gen_factory.handleArg(arg)
    options = {}
    for arg in local_args:
        if arg.startswith(('-pageage_days:', '-lastedit_days:')):
            key, val = arg.split(':', 1)
            options[key[1:]] = int(val)
        elif gen_factory.handleArg(arg):
            pass
        else:
            options[arg[1:].lower()] = True

    generator = gen_factory.getCombinedGenerator(preload=True)
    return generator, options


if __name__ == '__main__':

    # WS = pywikibot.Site(fam='wikisource', code='ru')
    # j = pywikibot.Page(WS, 'MediaWiki:Настройки бота для создания элементов ВД.json')
    # settings = json.loads(j.text)
    settings = json_load_from_file('settings.json')
    if not settings['bot_enabled']:
        pywikibot.error('exit, bot is disabled')
        exit()

    prefixes = {prefix: d for prefix, d in settings['prefixes'].items() if d['active']}
    if not prefixes:
        pywikibot.error('not enabled encyclopedies to work, no prefixes actived')
        exit()

    base_args = ['-family:wikisource', '-lang:ru', '-ns:0']  # '-format:"{page.can_title}"'
    args = [
        # '-summary:creating WD item',
        '-mysqlquery:%s' % make_sql(lastedit_days=settings["lastedit_days"]),
        # '-file:pages.txt',
    ]

    args = base_args + args + sys.argv[1:]

    main(args, settings, prefixes)
    # main(' '.join(args))

# для settings.json
# "pattern_of_disambig_in_item_description": "{note}. {main_description}",
