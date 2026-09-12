import io
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main

FIXTURE=Path(__file__).parent/'fixtures'/'AR-509.pdf'

class UploadRegressionTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(main.app)
    def archive(self,name,data):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z: z.writestr(name,data)
        return b.getvalue()
    def test_zip_name_cannot_override_inner_sheet_number(self):
        data=self.archive('AR-509.pdf',FIXTURE.read_bytes())
        r=self.client.post('/api/project/upload-batch',files={'files':('AR-107.zip',data,'application/zip')})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['project_register']['sheets_analyzed'],['AR-509'])
    def test_windows_path_filename_preserved_safely(self):
        path=main._write_temp_pdf(b'test',r'C:\folder\AR-509.pdf')
        try: self.assertEqual(Path(path).name,'AR-509.pdf')
        finally: main._cleanup_temp_pdf(path)
    def test_member_limit_fails_cleanly(self):
        data=self.archive('large.pdf',b'12345')
        with patch.object(main,'MAX_MEMBER_BYTES',4):
            r=self.client.post('/api/project/upload-batch',files={'files':('files.zip',data)})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['files'][0]['status'],'ANALYSIS_FAILED')
    def test_pdf_size_limit(self):
        with patch.object(main,'MAX_MEMBER_BYTES',4):
            r=self.client.post('/analyze',files={'file':('drawing.pdf',b'12345')})
        self.assertEqual(r.status_code,413)
    def test_batch_size_limit(self):
        with patch.object(main,'MAX_UPLOAD_BYTES',4):
            r=self.client.post('/api/project/upload-batch',files={'files':('drawing.dwg',b'12345')})
        self.assertEqual(r.status_code,413)
    def test_bad_batch_clears_previous_live_register(self):
        main._last_register={'stale':'previous project'}
        r=self.client.post('/api/project/upload-batch',files={'files':('bad.zip',b'bad')})
        self.assertEqual(r.status_code,200)
        self.assertIsNone(main._last_register)
    def test_dwg_is_not_reported_as_analyzed(self):
        data=self.archive('wall.dwg',b'example')
        r=self.client.post('/api/project/upload-batch',files={'files':('project.zip',data)})
        self.assertIn('catalogued only',r.json()['files'][0]['status'])
        self.assertIsNone(r.json()['project_register'])
