import unittest
import re
from datetime import datetime, timezone
import pathlib
import pywikibot
from pywikibot import pagegenerators
from vladi_helpers.file_helpers import json_load_from_file, json_save_to_file, file_save, pickle_save_to_file, \
    pickle_load_from_file
import bot, create_items


class TestProblem1(unittest.TestCase):

    def setUp(self):
        self.settings = json_load_from_file('settings.json')
        # prefixes = {prefix: d for prefix, d in settings['prefixes'].items() if d['active']}
        self.prefixes = {prefix: d for prefix, d in self.settings['prefixes'].items()}
        self.base_args = ['-family:wikisource', '-lang:ru', '-ns:0', '-format:"{page.can_title}"']
        self.WS = pywikibot.Site(fam='wikisource', code='ru')
        self.WD = self.WS.data_repository()
        self.enc_metas = bot.get_enc_metas(self.WS, self.WD)

    @unittest.skip("skipping")
    def test_Pagedata(self):
        page = pywikibot.Page(self.WS, 'ГСС/ДО/Аягуз (город)')
        page.p = bot.Pagedata(page, self.enc_metas, self.prefixes)
        print()

    # @unittest.skip("skipping")
    def test_page_with_disambig(self):
        # args = self.base_args + [
        #     # '-file:pages.txt',
        #     '-page:ГСС/ДО/Аягуз (город)',
        # ]
        # page = pywikibot.Page(self.WS, 'ГСС/ДО/Аягуз (город)')
        page = pywikibot.Page(self.WS, 'ГСС/ДО/Аягыш')
        page.p = bot.Pagedata(page, self.enc_metas, self.prefixes)

        # create_items.main(args, self.settings, self.prefixes)
        b = bot.NewItemBot
        b.pattern_of_disambig_in_item_description = self.settings['pattern_of_disambig_in_item_description']
        data = b.make_item_header(bot.NewItemBot, page)
        print()

    @unittest.skip("skipping")
    def test_allInOne_sheet(self):
        d = self.d
        catname, scatname = d.catname, d.scatname
        outdir_base, f_dir = d.outdir_base, d.f_dir

        limit_rows = 100
        keywords_filter = None
        sort_reverse = True
        sort_by = None
        self.sheets.gigs_sorted_manyonesheet(
            self.gigs_formed_subcategory, sort_by, sort_reverse, limit_rows, keywords_filter)

        f_filename = f'top100allInOne_{catname}_{scatname}' + '_{datetime}.xlsx'
        self.fileops.save(self.sheets.wb, outdir_base=outdir_base, f_dir=f_dir, filename=f_filename)

        print()

    @unittest.skip("skipping")
    def test_sheets_makesave_subcategory(self):
        # run = fiverr_crawler.Run()
        # fiverr_crawler.Run().sheets_makesave_subcategory(
        self.run.sheets_makesave_subcategory(
            self.d.subcategory_meta, self.gigs_formed_subcategory, self.packages_formed_subcategory,
            limit_rows=20, keywords_filter='seo, plan')
        print()

    @unittest.skip("skipping")
    def test_format_filenames(self):
        cname, cid = "Graphics \u0026 Design", 3
        sname, sid = "Business Cards \u0026 Stationery", 56

        outdir_base = 'gigs'
        f_string = f'{cname}_{cid}_{sname}_{sid}'
        f_dir = '{datetime}_' + f'{cname}_{cid}'
        # f_dir = f'gigs_{cname}_{cid}'
        f_filename = '{datetime}_{string}.xlsx'
        self.fileops.format_path_output(f_string, f_dir, f_filename, outdir_general=outdir_base)

        fn_outpath_general = self.fileops.outdir_base
        fn_outpath = self.fileops.outdir
        fn_filename = self.fileops.filename
        fn_filepath = self.fileops.filepath
        print()

    @unittest.skip("skipping")
    def test_make_sheets_gigs_formed(self):
        self.sheets.gigs(self.gigs_formed_subcategory)
        f_dir = 'results'
        self.fileops.save(self.sheets.wb, f_string="gigs", f_dir=f_dir, filename='{string}_({datetime}).xlsx')

    @unittest.skip("skipping")
    def test_make_sheets_gigs_formed_sorted(self):
        d = self.d
        catname, scatname = d.catname, d.scatname
        outdir_base, f_dir = d.outdir_base, d.f_dir

        # Make resorted
        limit_rows = 100
        sort_reverse = True
        keywords_filter = None
        metafiles = (
            ('rating_count', 'top{limitrows}rating_count_{datetime}.xlsx'),
            ('rating_velocity', 'top{limitrows}rating_velocity_{datetime}.xlsx'),
            ('gig_created', 'top{limitrows}gig_created_{datetime}.xlsx'),
            ('fastest_delivery_time', 'top{limitrows}fastest_delivery_time_{datetime}.xlsx'),
            ('avg_delivery_time', 'top{limitrows}avg_delivery_time_{datetime}.xlsx'),
        )
        for sort_by, f_filename in metafiles:
            if sort_by in ['fastest_delivery_time', 'avg_delivery_time']:
                sort_reverse = False
            f_filename = f'{catname}_{scatname}_' + f_filename.replace('{limitrows}', str(limit_rows))

            self.sheets.gigs_sorted(self.gigs_formed_subcategory, sort_by, sort_reverse, limit_rows,
                                    keywords_filter)

            self.fileops.save(self.sheets.wb, outdir_base=outdir_base, f_dir=f_dir, filename=f_filename)

        print()


if __name__ == '__main__':
    unittest.main()
