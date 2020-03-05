#!/usr/bin/env python3
from __future__ import absolute_import, division, unicode_literals
from datetime import timedelta
from textwrap import fill
import json
import re
import pywikibot
from pywikibot.bot import WikidataBot, SingleSiteBot
from pywikibot.exceptions import (LockedPage, NoCreateError, NoPage, PageNotSaved)
from pywikibot import pagegenerators
from pprint import pprint
from typing import List
import sys
import datetime, pytz
# from bot import NewItemRobot
from vladi_helpers.file_helpers import json_save_to_file, json_load_from_file
import logger

logger = logger.get_logger("bot")

add_only_property_by_pagelist = True
add_only_property_by_pagelist = False


class Pagedata:
    def __init__(self, page, enc_metas, prefixes):
        self.pagename = page.title()
        self.pagename_spaceaboutslashes = self.pagename.replace('/', ' / ')
        self.rootpagename, _, self.subpagename = self.pagename.partition('/')
        prefix_settings = prefixes[self.rootpagename]
        # self.active = prefix_settings["active"]
        self.category_of_articles = prefix_settings["category_of_articles"]
        self.item_label = prefix_settings["item_label"]
        self.enc_meta = enc_metas[self.rootpagename]
        self.is_oldorph = True if '/ДО' in self.pagename else False
        self.pagename_pattern = self.enc_meta['titleDO'] if self.is_oldorph else self.enc_meta['titleVT']
        self.is_bad = False
        if ':ДО' in self.category_of_articles and not '/ДО' in self.pagename:
            logger.warning('категория ДО, но нет /ДО в названии страницы, пропускаем')
            self.is_bad = True
        elif not ':ДО' in self.category_of_articles and '/ДО' in self.pagename:
            logger.warning('категория не ДО, но есть /ДО в названии страницы, пропускаем')
            self.is_bad = True

        # пропуск шаблонов с символами regexp, во избежание ошибок
        self.is_bad = any((s for s in r'.?*+\()[]' if s in self.pagename_pattern))

        # Извлечение названия статьи из названия страницы
        m = re.search(self.pagename_pattern.replace('$1', '(.+)'), self.pagename)
        if m:
            self.article_title = m.group(1)
        else:
            self.is_bad = True

        # уточнение неоднозначностей в скобках
        self.disambig_note = self.article_title_no_disambig = None
        m = re.search(r'^(.+?)\s+\(([^()]+?)\)$', self.article_title)
        if m:
            self.article_title_no_disambig = m.group(1).strip()
            self.disambig_note = m.group(2).strip()


class ItemEditorRobot(WikidataBot):
    """A bot to create new items."""

    treat_missing_item = True

    def __init__(self, generator, settings: dict, prefixes: dict, **kwargs):
        """Only accepts options defined in availableOptions."""
        super().__init__(**kwargs)
        self.generator = generator
        self.enc_metas = get_enc_metas(self.site, self.repo)
        # self.prefixes = settings['prefixes']
        self.prefixes = prefixes

    def treat_page_and_item(self, page, item):
        """Treat page/item."""
        if self.filter_off(page, item):
            return

        page.p = Pagedata(page, self.enc_metas, self.prefixes)
        if page.p.is_bad:
            return

        item = page.data_item()
        data = self.make_item_header(page)

        # item.editEntity(self, data=data)

        item.get()
        if not ' / ' in item.labels['ru']:
            item.editLabels(data['labels'])
        item.editDescriptions(data['descriptions'])
        item.editAliases(data['aliases'])
        # result = self.user_edit_entity(item, data, show_diff=False, bot=True)

        claims = self.make_claims(page)
        self.add_claims(item, claims)
        pass

    def add_claims(self, item, claims) -> None:
        """Treat each page."""
        for claim in claims:
            self.user_add_claim_unless_exists(item, claim)
            if claim.id == 'P1476':
                for existing in item.claims.get('P1476', []):
                    # if 'ГСС/ДО' in existing.target.text \
                    #         and not existing.target_equals(claim.getTarget()):
                    if 'ГСС' in existing.target.text:
                        existing.changeTarget(value=claim.target)

    def make_item_header(self, page):
        p = page.p
        RU = 'ru'
        data = {
            'labels': {RU: {'language': RU, 'value': p.pagename.replace('/ДО', '').replace('/ВТ', '')}},
            # p.pagename_spaceaboutslashes
            'descriptions': {},  # {'en': 'encyclopedic article', 'ru': f'энциклопедическая статья'},
            'aliases': {RU: [p.article_title]},
            # 'sitelinks': [{'site': 'enwiki', 'title': 'Douglas Adams'}]
        }
        for lng in ['en', RU]:
            data['descriptions'][lng] = p.item_label[lng]
        return data

    def make_claims(self, page):
        p = page.p
        properties = [
            ['P31', 'Q13433827'],  # 'это частный случай понятия' : энциклопедическая статья
            ['P1476', ['ru', p.article_title_no_disambig or p.article_title]],
            ['P1433', p.enc_meta['id']],  # 'опубликовано в'
            ['P407', 'Q7737'],  # язык произведения или его названия : русский
        ]

        claims = []
        # repo = pywikibot.Site().data_repository()
        # for i in range(0, len(commandline_claims), 2):
        for pid, value in properties:
            claim = pywikibot.Claim(self.repo, pid)
            if claim.type == 'wikibase-item':
                target = pywikibot.ItemPage(self.repo, value)
            elif claim.type == 'string':
                target = value
            elif claim.type == 'monolingualtext':
                lang, string = value
                target = pywikibot.WbMonolingualText(string, lang)  # .toWikibase()
            elif claim.type == 'globe-coordinate':
                coord_args = [
                    float(c) for c in value.split(',')]
                if len(coord_args) >= 3:
                    precision = coord_args[2]
                else:
                    precision = 0.0001  # Default value (~10 m at equator)
                target = pywikibot.Coordinate(
                    coord_args[0], coord_args[1], precision=precision)
            else:
                raise NotImplementedError(
                    '{} datatype is not yet supported by claimit.py'.format(claim.type))
            claim.setTarget(target)
            claims.append(claim)
        return claims

    def filter_off(self, page, item):
        if not item and not item.exists():
            pywikibot.output('{0} already has an item: {1}.'
                             .format(page, item))
            if self.getOption('touch') is True:
                self._touch_page(page)
            return True

        if page.langlinks():
            # FIXME: Implement this
            pywikibot.output(
                'Found language links (interwiki links).\n'
                "Haven't implemented that yet so skipping.")
            return True

    @staticmethod
    def _touch_page(page):
        try:
            pywikibot.output('Doing a null edit on the page.')
            page.touch()
        except (NoCreateError, NoPage):
            pywikibot.error('Page {0} does not exist.'.format(
                page.title(as_link=True)))
        except LockedPage:
            pywikibot.error('Page {0} is locked.'.format(
                page.title(as_link=True)))
        except PageNotSaved:
            pywikibot.error('Page {0} not saved.'.format(
                page.title(as_link=True)))

    def _callback(self, page, exc):
        if exc is None and self.getOption('touch'):
            self._touch_page(page)


def get_enc_metas(WS, WD):
    # other_sources = parse_lua_to_dict(WD_utils.WS, 'Модуль:Другие источники', 'otherSources')
    # wikiprojects = parse_lua_to_dict(self.wd.WD, 'Модуль:Навигация-мини', 'projects')
    j = pywikibot.Page(WS, 'MediaWiki:Encyclopedias_settings.json')
    other_sources = json.loads(j.text)
    enc_metas = {}
    for n in other_sources:
        n['wditem'] = pywikibot.ItemPage(WD, n['id'])  # todo
        pname = n['argument']
        enc_metas[pname] = n
    return enc_metas


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

    bot = ItemEditorRobot(generator, settings, prefixes, **options)
    bot.add_only_property_by_pagelist = add_only_property_by_pagelist
    user = pywikibot.User(bot.site, bot.site.username())
    bot.run()
    return True


def make_sql():
    categories = ','.join(['"%s"' % d['category_of_articles'] for prefix, d in prefixes.items()])
    #  'БЭЮ', 'БСЭ1' мелкие словарные статьи или масса перенаправлений
    sql = f"""
    SELECT page_namespace,  page_title
    FROM ruwikisource_p.page
        JOIN ruwikisource_p.categorylinks ON cl_from = page_id
            AND cl_to IN ({categories})
            AND page_namespace = 0
        LEFT JOIN ruwikisource_p.categorylinks c ON c.cl_from = page_id
            AND c.cl_to = "Викиданные:Страницы_с_элементами"
    WHERE c.cl_to IS NOT NULL;
    """.replace('\n', ' ').strip()
    #             AND page_title LIKE '%(%'
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

    WS = pywikibot.Site(fam='wikisource', code='ru')
    j = pywikibot.Page(WS, 'MediaWiki:Настройки бота для создания элементов ВД.json')
    # settings = json.loads(j.text)
    settings = json_load_from_file('settings.json')
    if not settings['bot_enabled']:
        pywikibot.error('exit, bot is disabled')
        exit()

    prefixes = {prefix: d for prefix, d in settings['prefixes'].items() if d['active']}
    if not prefixes:
        pywikibot.error('not enabled encyclopedies to work, no prefixes actived')
        exit()

    base_args = ['-family:wikisource', '-lang:ru', '-ns:0', '-format:"{page.can_title}"']
    args = [
        # '-summary:creating WD item',
        '-mysqlquery:%s' % make_sql(),
        # '-file:pages.txt',
        # '-category:ГСС:ДО'
        # '-titleregex:\(',
    ]

    # t = datetime.datetime.strptime('20160405213538', '%Y%m%d%H%M%S')
    # t = t.astimezone(pytz.utc)

    # if add_only_property_by_pagelist:
    #     args = [
    #         # '-summary:creating WD item',
    #         # '-mysqlquery:%s' % sql.replace('\n', ' '),
    #         '-file:pages.txt',
    #     ]

    # args = [
    # '-summary:creating WD item',
    # '-mysqlquery:%s' % sql.replace('\n', ' '),
    # '-file:pages.txt',

    # '-usercontribs:textworkerBot',
    # '-limit:2000',
    # '-catfilter:ГСС:ДО',
    # ]

    args = base_args + args + sys.argv[1:]

    main(args, settings, prefixes)
    # main(' '.join(args))
