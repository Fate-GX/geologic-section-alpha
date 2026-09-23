import tempfile
import unittest
from pathlib import Path
import sys

from pypdf import PdfReader, PdfWriter

ADVANCED = Path(__file__).resolve().parents[1]
if str(ADVANCED) not in sys.path:
    sys.path.insert(0, str(ADVANCED))
from advanced_visual_qa import _normalize_landscape_pdf


class LandscapePdfNormalizationTests(unittest.TestCase):
    def test_portrait_wrapper_becomes_unrotated_landscape(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"portrait.pdf"
            target=Path(folder)/"landscape.pdf"
            writer=PdfWriter()
            writer.add_blank_page(width=841.89,height=1190.55)
            with source.open("wb") as stream:
                writer.write(stream)

            _normalize_landscape_pdf(source,target)

            page=PdfReader(target).pages[0]
            self.assertLess(float(page.mediabox.width),float(page.mediabox.height))
            self.assertEqual(int(page.get("/Rotate",0))%360,270)

    def test_existing_landscape_page_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"landscape_source.pdf"
            target=Path(folder)/"landscape_target.pdf"
            writer=PdfWriter()
            writer.add_blank_page(width=1190.55,height=841.89)
            with source.open("wb") as stream:
                writer.write(stream)

            _normalize_landscape_pdf(source,target)

            page=PdfReader(target).pages[0]
            self.assertAlmostEqual(float(page.mediabox.width),1190.55,places=2)
            self.assertAlmostEqual(float(page.mediabox.height),841.89,places=2)

    def test_landscape_box_drops_stale_portrait_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"rotated_landscape_source.pdf"
            target=Path(folder)/"rotated_landscape_target.pdf"
            writer=PdfWriter()
            page=writer.add_blank_page(width=1190.55,height=841.89)
            page.rotate(-90)
            with source.open("wb") as stream:
                writer.write(stream)
            _normalize_landscape_pdf(source,target)
            page=PdfReader(target).pages[0]
            self.assertGreater(float(page.mediabox.width),float(page.mediabox.height))
            self.assertEqual(int(page.get("/Rotate",0))%360,0)


if __name__ == "__main__":
    unittest.main()
