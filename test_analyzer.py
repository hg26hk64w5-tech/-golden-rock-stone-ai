import unittest
import os

from analyzer import analyze_pdf, merge_project_register, PdfReadError

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'AR-509.pdf')


@unittest.skipUnless(os.path.exists(FIXTURE), 'fixtures/AR-509.pdf sample drawing not present')
class AnalyzerRealDrawingTests(unittest.TestCase):
    """Regression tests against a real, anonymized-free project sheet (the villa's own
    AR-509 Roof Floor External Wall Finish Layout) rather than a synthetic one-line PDF,
    since the thing actually worth protecting against regressions is the legend-table
    reader's behaviour on a real B8/AMEC title block."""

    def setUp(self):
        self.result = analyze_pdf(FIXTURE)

    def test_sheet_number_from_filename(self):
        self.assertEqual(self.result.sheet_number, 'AR-509')

    def test_all_legend_codes_detected(self):
        expected = {'EWAL-01', 'EWAL-02', 'EWAL-03', 'ECLM-01', 'EWHL-01',
                    'EWMB-01', 'EWPR-01', 'EWPT-01', 'EWST-01', 'EWST-02'}
        self.assertEqual(set(self.result.detected_codes), expected)

    def test_travertine_code_full_description_and_thickness(self):
        ewmb = next(m for m in self.result.materials if m.code == 'EWMB-01')
        self.assertIn('BEIGE TRAVERTINE ROMANO CLASSICO', ewmb.name)
        self.assertEqual(ewmb.category, 'Natural Stone')
        self.assertEqual(ewmb.thickness_mm, 20.0)

    def test_only_natural_stone_codes_become_zone_candidates(self):
        zone_codes = {z.material_code for z in self.result.zones}
        self.assertEqual(zone_codes, {'EWMB-01', 'EWST-01', 'EWST-02'})
        for z in self.result.zones:
            self.assertEqual(z.status, 'RFI_REQUIRED')
            self.assertEqual(z.sheet, 'AR-509')
            self.assertEqual(z.zone_id, f'AR-509-{z.material_code}')

    def test_levels_extracted_with_unit_tag(self):
        self.assertTrue(any('T.O.P' in lvl or 'TOP' in lvl.upper() for lvl in self.result.levels))

    def test_merge_project_register_single_file(self):
        reg = merge_project_register([self.result], project_name='Test Project')
        self.assertEqual(reg.sheets_analyzed, ['AR-509'])
        self.assertEqual(len(reg.zones), 3)
        self.assertTrue(any('substrate' in item.lower() for item in reg.rfi_required))


class AnalyzerFallbackCodeTests(unittest.TestCase):
    """The inline fallback (used when a sheet has no LEGEND/Code/Description table)
    must not mistake a drawing or revision reference (e.g. "AR-509", "TD-02") for a
    material code -- it is restricted to this project's E** convention."""

    def test_fallback_regex_rejects_non_material_references(self):
        from analyzer import FALLBACK_CODE_RE
        self.assertIsNone(FALLBACK_CODE_RE.search('Drawing B8-D139-IFC-AR-509'))
        self.assertIsNone(FALLBACK_CODE_RE.search('Red clouds indicate changes from TD-02.'))

    def test_fallback_regex_accepts_material_codes(self):
        from analyzer import FALLBACK_CODE_RE
        self.assertIsNotNone(FALLBACK_CODE_RE.search('Refer to EWMB-01 for stone finish.'))
        self.assertIsNotNone(FALLBACK_CODE_RE.search('EFST-02 travertine floor tile.'))


class PdfReadErrorTests(unittest.TestCase):
    def test_invalid_pdf_raises_pdfreaderror(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(b'not a real pdf')
            path = tmp.name
        try:
            with self.assertRaises(PdfReadError):
                analyze_pdf(path)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
