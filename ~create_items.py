#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Script to handle interwiki links based on Wikibase.

This script connects pages to Wikibase items using language links on the page.
If multiple language links are present, and they are connected to different
items, the bot skips. After connecting the page to an item, language links
can be removed from the page.

These command line parameters can be used to specify which pages to work on:

&params;

Furthermore, the following command line parameters are supported:

-clean            Clean pages.

-create           Create items.

-merge            Merge items.

-summary:         Use your own edit summary for cleaning the page.
"""

# (C) Pywikibot team, 2015-2019
#
# Distributed under the terms of the MIT license.
#
from __future__ import unicode_literals, division, absolute_import
import pywikibot as pwb
from pywikibot import pagegenerators, output, warning
from pywikibot.bot import ExistingPageBot, SingleSiteBot, suggest_help, WikidataBot
import sys

# This is required for the text that is shown when you run this script
# with the parameter -help.
docuReplacements = {'&params;': pagegenerators.parameterHelp}  # noqa: N816

# Allowed namespaces. main, project, template, category
# namespaces = [0, 4, 10, 14]
namespaces = [0]


# TODO: Some templates on pages, like csd, inuse and afd templates,
# should cause the bot to skip the page, see T134497


# class IWBot(ExistingPageBot, SingleSiteBot):
class IWBot(WikidataBot):
    """The bot for interwiki."""

    def __init__(self, **kwargs):
        """Initialize the bot."""
        self.availableOptions.update({
            'clean': False,
            'create': False,
            'merge': False,
            'summary': None,
            'ignore_ns': False,  # used by interwikidata_tests only
        })
        super().__init__(**kwargs)
        self.repo = self.site.data_repository()

    def treat_page(self):
        """Check page."""
        if (self.current_page.namespace() not in namespaces
                and not self.getOption('ignore_ns')):
            output('{page} is not in allowed namespaces, skipping'
                .format(page=self.current_page.title(
                as_link=True)))
            return False
        self.iwlangs = pwb.textlib.getLanguageLinks(
            self.current_page.text, insite=self.current_page.site)
        if not self.iwlangs:
            output('No interlanguagelinks on {page}'.format(
                page=self.current_page.title(as_link=True)))
            return False
        try:
            item = pwb.ItemPage.fromPage(self.current_page)
        except pwb.NoPage:
            item = None

        if item is None:
            item = self.try_to_add()
            item = self.create_item()

    def create_item(self):
        """Create item in repo for current_page."""
        data = {'sitelinks':
                    {self.site.dbName():
                         {'site': self.site.dbName(),
                          'title': self.current_page.title()}
                     },
                'labels':
                    {self.site.lang:
                         {'language': self.site.lang,
                          'value': self.current_page.title()}
                     }
                }
        for site, page in self.iwlangs.items():
            if not page.exists():
                continue
            dbname = site.dbName()
            title = page.title()
            data['sitelinks'][dbname] = {'site': dbname, 'title': title}
            data['labels'][site.lang] = {'language': site.lang, 'value': title}
        summary = ('Bot: New item with sitelink(s) from '
                   + self.current_page.title(as_link=True, insite=self.repo))

        item = pwb.ItemPage(self.repo)
        item.editEntity(data, new='item', summary=summary)
        output('Created item {item}'.format(item=item.getID()))
        return item

    def handle_complicated(self):
        """
        Handle pages when they have interwiki conflict.

        When this method returns True it means conflict has resolved
        and it's okay to clean old interwiki links.
        This method should change self.current_item and fix conflicts.
        Change it in subclasses.
        """
        return False

    def clean_page(self):
        """Clean interwiki links from the page."""
        if not self.iwlangs:
            return
        dbnames = [iw_site.dbName() for iw_site in self.iwlangs]
        if set(dbnames) - set(self.current_item.sitelinks.keys()):
            if not self.handle_complicated():
                warning('Interwiki conflict in {}, skipping...'
                        .format(self.current_page.title(as_link=True)))
                return False
        output('Cleaning up the page')
        new_text = pwb.textlib.removeLanguageLinks(
            self.current_page.text, site=self.current_page.site)
        self.put_current(new_text, summary=self.getOption('summary'))

    def get_items(self):
        """Return all items of pages linked through the interwiki."""
        wd_data = set()
        for iw_page in self.iwlangs.values():
            if not iw_page.exists():
                warning('Interwiki {} does not exist, skipping...'
                        .format(iw_page.title(as_link=True)))
                continue
            try:
                wd_data.add(pwb.ItemPage.fromPage(iw_page))
            except pwb.NoPage:
                output('Interwiki {} does not have an item'
                       .format(iw_page.title(as_link=True)))
        return wd_data

    def try_to_add(self):
        """Add current page in repo."""
        wd_data = self.get_items()
        if not wd_data:
            # will create a new item with interwiki
            return None
        if len(wd_data) > 1:
            warning('Interwiki conflict in {}, skipping...'
                    .format(self.current_page.title(as_link=True)))
            return False
        item = list(wd_data).pop()
        if self.current_page.site.dbName() in item.sitelinks:
            warning('Interwiki conflict in {}, skipping...'
                    .format(item.title(as_link=True)))
            return False
        output('Adding link to ' + item.title())
        item.setSitelink(self.current_page, summary='Added ' + (
            self.current_page.title(as_link=True, insite=item.site)))
        return item

    # def try_to_merge(self, item):
    #     """Merge two items."""
    #     wd_data = self.get_items()
    #     if not wd_data:
    #         # todo: add links to item
    #         return None
    #     if len(wd_data) > 1:
    #         warning('Interwiki conflict in {}, skipping...'
    #                 .format(self.current_page.title(as_link=True)))
    #         return False
    #     target_item = list(wd_data).pop()
    #     try:
    #         item.mergeInto(target_item)
    #     except pwb.data.api.APIError:
    #         # warning already printed by the API
    #         return False
    #     else:
    #         target_item.get(force=True)
    #         return target_item


sql = """
SELECT page_namespace,  page_title
FROM ruwikisource_p.page
    JOIN ruwikisource_p.categorylinks ON cl_from = page_id
          AND cl_to IN ('ЭСГ', 'МСЭ2', 'РЭСБ', 'ТЭ1', 'НЭС', 'ППБЭС:ВТ', 'НСТ', 'ПБЭ', 'ВЭЛ:ВТ', 'НЭСГ', 'ГСС:ДО')
          AND page_namespace = 0
          AND NOT (page_title LIKE 'НСТ/%/ДО' OR page_title LIKE 'ЭСГ/%/ДО')    
    LEFT JOIN ruwikisource_p.categorylinks c ON c.cl_from = page_id  -- категории исключения
        AND (LOWER(c.cl_to) LIKE '%перенаправлени%' OR c.cl_to = 'Викиданные:Страницы_с_элементами')
WHERE c.cl_to IS  NULL;
"""

def get_pages_from_db():
    from pywikibot.data import mysql
    generator = mysql.mysql_query(sql)
    return generator


def pagegenerator(args: list = None):
    """ Get list of pages which using 'Template:infobox former country'
        без кавычек имена станиц/категорий в параметрах
    """
    # args = ['-family:wikipedia', '-lang:en', '-ns:0'] + [f'-transcludes:{tpl}' for tpl in tpl_names]
    gen_factory = pwb.pagegenerators.GeneratorFactory()
    local_args = pwb.handle_args(args)
    for arg in local_args:
        gen_factory.handleArg(arg)
    gen = gen_factory.getCombinedGenerator(preload=False)
    return gen


def main(*args):
    """
    Process command line arguments and invoke bot.

    If args is an empty list, sys.argv is used.

    @param args: command line arguments
    @type args: str
    """
    # generator = get_pages_from_db()
    # pages = tuple(generator)
    base_args = ['-family:wikisource', '-lang:ru', '-ns:0', '-format:"{page.can_title}"']
    args = [
        '-summary:creating WD item',
        f'-mysqlquery:{sql}']
    args = base_args + args + sys.argv[1:]
    gen = pagegenerator(args)

    # site = pwb.Site('ru', 'wikisource', user='textworkerBot')
    # k = tuple(gen)
    if gen:
        bot = IWBot(generator=gen,
                    # site=site,
                    # **options
                    )
        bot.run()
    else:
        suggest_help(missing_generator=True)
        return False


if __name__ == '__main__':
    main()
