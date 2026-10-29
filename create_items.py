#!/usr/bin/env python3
# (C) Vladis13, 2020
# (C) Pywikibot team, 2014-2020
#
# Distributed under the terms of the MIT license.
#
from __future__ import absolute_import, division, unicode_literals
from textwrap import fill
import sys
import json
import datetime
import pywikibot
from pywikibot import pagegenerators
from create_items_bot import NewItemBot


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

    bot = NewItemBot(generator, settings, prefixes, **options)
    user = pywikibot.User(bot.site, bot.site.username())
    if bot.opt['touch'] == 'newly' and 'autoconfirmed' not in user.groups():
        pywikibot.warning(fill(
            'You are logged in as {}, an account that is '
            'not in the autoconfirmed group on {}. Script '
            'will not touch pages linked to newly created '
            'items to avoid triggering edit rates or '
            'captcha. Use -touch param to force this.'
                .format(user.username, bot.site.sitename)))
        bot.opt['touch'] = False
    bot.run()
    return True


def make_sql(lastedit_days: int):
    # ("БСЭ1", "БСЭ2", "БЭЮ", "ВЭЛ:ВТ", "ГСС:ДО", "МСЭ2", "НСТ", "НЭС", "НЭСГ", "ПБЭ", "ППБЭС:ВТ", "РЭСБ", "ТЭ1", "ЭСГ")
    # x = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')

    categories = ','.join(['"%s"' % d['category_of_articles'].replace(' ', '_') for prefix, d in prefixes.items()])
    #  'БЭЮ', 'БСЭ1' мелкие словарные статьи или масса перенаправлений
    sql = f"""
    SELECT page_namespace, page_title
    FROM page
    WHERE EXISTS (
        SELECT 1 FROM categorylinks cl
        WHERE cl.cl_from = page.page_id
          AND EXISTS (
              SELECT 1 FROM linktarget lt2
              WHERE lt2.lt_id = cl.cl_target_id
                AND lt2.lt_title IN ({categories.replace(' ', '_')})
          )
    )
    AND NOT EXISTS (
        SELECT 1 FROM categorylinks cl
        JOIN linktarget lt ON lt.lt_id = cl.cl_target_id
        WHERE cl.cl_from = page.page_id
          AND (lt.lt_title = 'Викиданные:Страницы_с_элементами'
               OR lt.lt_title LIKE '%еренаправлени%')
    )
    AND page_latest IN (
        SELECT rev_id FROM revision
        WHERE rev_timestamp < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL {lastedit_days} DAY)
    )
    AND page_namespace = 0
    AND page_is_redirect = 0
    """.replace('\n', ' ').strip()

    return sql


def pagegenerator(args: list[str]):
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
        elif gen_factory.handle_arg(arg):
            pass
        else:
            options[arg[1:].lower()] = True

    generator = gen_factory.getCombinedGenerator(preload=True)
    return generator, options


if __name__ == '__main__':

    """ для локального запуска запустить:
    ssh -L 4712:ruwikisource.web.db.svc.wikimedia.cloud:3306 vladi2016@login.toolforge.org -i "/home/vladislav/.ssh/id_rsa"
    """

    WS = pywikibot.Site(fam='wikisource', code='ru')
    j = pywikibot.Page(WS, 'MediaWiki:Настройки бота для создания элементов ВД.json')
    settings = json.loads(j.text)
    if not settings['bot_enabled']:
        pywikibot.error('exit, bot is disabled')
        exit()

    prefixes = {prefix: d for prefix, d in settings['prefixes'].items() if d['active']}
    if not prefixes:
        pywikibot.error('no enabled encyclopedias to work, no active prefixes')
        exit()

    base_args = ['-family:wikisource', '-lang:ru', '-ns:0']
    args = [
        '-mysqlquery:%s' % make_sql(lastedit_days=settings["lastedit_days"]),
    ]
    # args = ['-page:ЕЭБЕ/Шамир, камень']
    # args = ['-file:/tmp/t.txt']
    # settings["lastedit_days"] = 0

    args = base_args + args + sys.argv[1:]

    main(args, settings, prefixes)

# для settings.json
# "pattern_of_disambig_in_item_description": "{note}. {main_description}",
