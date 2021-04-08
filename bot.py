from __future__ import absolute_import, division, unicode_literals
from datetime import timedelta
import json
import re
import pywikibot
from pywikibot.bot import WikidataBot
from pywikibot.exceptions import (LockedPage, NoCreateError, NoPage, PageSaveRelatedError)
import logger

logger = logger.get_logger("bot")


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


class NewItemRobot(WikidataBot):
    """A bot to create new items."""

    treat_missing_item = True

    def __init__(self, generator, settings: dict, prefixes: dict, **kwargs):
        """Only accepts options defined in availableOptions."""
        self.availableOptions.update({
            'always': True,
            'lastedit_days': settings.get('lastedit_days'),
            'touch': 'newly',  # Can be False, newly (pages linked to newly
            # created items) or True (touch all pages)
        })

        super().__init__(**kwargs)
        self.generator = generator
        self.lastEdit = self.getOption('lastedit_days')
        self.lastEditBefore = self.site.server_time() - timedelta(days=self.lastEdit)
        pywikibot.output(
            'Last edit is set to {0} days so only pages last edited'
            '\nbefore {1} will be considered.'.format(
                self.lastEdit, self.lastEditBefore.isoformat()))
        self.enc_metas = get_enc_metas(self.site, self.repo)
        # self.prefixes = settings['prefixes']
        self.prefixes = prefixes
        # self.pattern_of_disambig_in_item_description = settings['pattern_of_disambig_in_item_description']

    def treat_page_and_item(self, page, item):
        """Treat page/item."""
        if self.filter_off(page, item):
            return

        page.p = Pagedata(page, self.enc_metas, self.prefixes)
        if page.p.is_bad:
            return
        pywikibot.stdout('page.p done')

        data = self.make_item_header(page)
        claims = self.make_claims(page)

        item = self.create_item_for_page(page, data=data, callback=lambda _, exc: self._callback(page, exc))
        self.add_claims(item, claims)

    def add_claims(self, item, claims):
        """Treat each page."""
        for claim in claims:
            # The generator might yield pages from multiple sites
            # site = page.site if page is not None else None
            self.user_add_claim(item, claim)  # self.exists_arg

    def create_item_for_page(self, page, data=None, summary=None, **kwargs):
        """
        в pywikibot.bot.create_item_for_page() метка всеровно переименовывается как pagename
        заменено своей функцией
        """
        if not summary:
            # FIXME: i18n
            summary = ('Bot: New item with sitelink from %s'
                       % page.title(as_link=True, insite=self.repo))

        if data is None:
            data = {}
        data.setdefault('sitelinks', {}).update({
            page.site.dbName(): {
                'site': page.site.dbName(),
                'title': page.title()
            }
        })
        pywikibot.output('Creating item for %s...' % page)
        item = pywikibot.ItemPage(page.site.data_repository())
        kwargs.setdefault('show_diff', False)
        result = self.user_edit_entity(item, data, summary=summary, **kwargs)
        if result:
            return item
        else:
            return None

    def make_item_header(self, page) -> dict:
        p = page.p
        RU = 'ru'
        data = {
            'labels': {RU: {'language': RU, 'value': p.pagename.replace('/ДО', '').replace('/ВТ', '')}},
            'descriptions': {lng: p.item_label[lng] for lng in ['en', RU]},
            'aliases': {RU: [p.article_title]}}
        return data

    def make_claims(self, page) -> list:
        p = page.p
        properties = [
            ['P31', 'Q13433827'],  # 'это частный случай понятия' : энциклопедическая статья
            ['P1476', ['ru', p.article_title_no_disambig or p.article_title]],
            ['P1433', p.enc_meta['id']],  # 'опубликовано в'
            ['P407', 'Q7737'],  # язык произведения или его названия : русский
        ]

        claims = []
        for pid, value in properties:
            claim = pywikibot.Claim(self.repo, pid)
            if claim.type == 'wikibase-item':
                target = pywikibot.ItemPage(self.repo, value)
            elif claim.type == 'string':
                target = value
            elif claim.type == 'monolingualtext':
                lang, string = value
                target = pywikibot.WbMonolingualText(string, lang)
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

    def filter_off(self, page, item) -> bool:
        if item and item.exists():
            pywikibot.output('{0} already has an item: {1}.'
                             .format(page, item))
            return True

        if page.isRedirectPage():
            pywikibot.output('{0} is a redirect page. Skipping.'.format(page))
            return True

        if page.editTime() > self.lastEditBefore:
            pywikibot.output(
                'Last edit on {0} was on {1}.\nToo recent. Skipping.'
                    .format(page, page.editTime().isoformat()))
            return True
        if page.isCategoryRedirect():
            pywikibot.output('{0} is a category redirect. Skipping.'
                             .format(page))
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
        except PageSaveRelatedError:
            pywikibot.error('Page {0} not saved.'.format(
                page.title(as_link=True)))

    def _callback(self, page, exc):
        if exc is None and self.getOption('touch'):
            self._touch_page(page)


def get_enc_metas(WS, WD):
    j = pywikibot.Page(WS, 'MediaWiki:Encyclopedias_settings.json')
    other_sources = json.loads(j.text)
    enc_metas = {}
    for n in other_sources:
        n['wditem'] = pywikibot.ItemPage(WD, n['id'])
        pname = n['argument']
        enc_metas[pname] = n
    return enc_metas
