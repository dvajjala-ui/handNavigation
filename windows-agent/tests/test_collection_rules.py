import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent)]
from core.collections import CollectionDB, config


def db_without_connection():
    """A CollectionDB whose connect() would fail, so passing means no database was touched."""
    handle=CollectionDB.__new__(CollectionDB)
    handle.values={}
    def boom():raise AssertionError('No database access is allowed in this test.')
    handle.connect=boom
    return handle


class CollectionRuleTests(unittest.TestCase):
    def env(self,**override):
        values={'SUPABASE_URL':'https://kyvowdxtwazxhsdjajpm.supabase.co',
                'SUPABASE_SECRET_KEY':'sb_secret_test','SUPABASE_DB_HOST':'db.test',
                'SUPABASE_DB_USER':'postgres','SUPABASE_DB_PASSWORD':'x','SUPABASE_DB_NAME':'postgres'}
        values.update(override)
        file=Path(self.folder)/'.env'
        file.write_text('\n'.join(f'{k}={v}' for k,v in values.items() if v is not None),encoding='utf-8')
        return str(file)

    def setUp(self):
        self._temp=tempfile.TemporaryDirectory();self.folder=self._temp.name
        self.environ={k:v for k,v in os.environ.items() if not k.startswith(('SUPABASE_','REDDIT_'))}
        for key in list(os.environ):
            if key.startswith(('SUPABASE_','REDDIT_')):os.environ.pop(key)

    def tearDown(self):
        os.environ.clear();os.environ.update(self.environ);self._temp.cleanup()

    def test_plain_env_file_is_required_and_validated_before_any_use(self):
        self.assertEqual(config(self.env())['SUPABASE_URL'],'https://kyvowdxtwazxhsdjajpm.supabase.co')
        for path in (str(Path(self.folder)/'missing.env'),self.env(SUPABASE_DB_PASSWORD=''),
                     self.env(SUPABASE_SECRET_KEY='sb_publishable_test')):
            with self.subTest(path=path),self.assertRaises((RuntimeError,ValueError)):config(path)

    def test_only_the_configured_project_endpoint_is_accepted(self):
        for url in ('http://kyvowdxtwazxhsdjajpm.supabase.co','https://evil.test/',
                    'https://kyvowdxtwazxhsdjajpm.supabase.co.other.test','https://other.supabase.co'):
            with self.subTest(url=url),self.assertRaises(ValueError):config(self.env(SUPABASE_URL=url))

    def test_reddit_never_reaches_the_database_without_approved_oauth(self):
        job={'name':'Daily reddit','source':'reddit','topic_key':'travel','image_count':5,
             'daily_time':'09:00','timezone':'Asia/Kolkata'}
        with self.assertRaisesRegex(ValueError,'approved OAuth'):db_without_connection().create_job(job)

    def test_unscheduled_or_malformed_jobs_are_rejected_before_insert(self):
        db=db_without_connection()
        base={'name':'Daily','source':'pinterest','topic_key':'travel','image_count':5,'daily_time':'09:00'}
        cases={'unknown source':{'source':'instagram'},'count out of range':{'image_count':0},
               'no topic and not random':{'topic_key':None,'random_topic':False},
               'bad time':{'daily_time':'9am'},'blank name':{'name':''},'bad timezone':{'timezone':'Mars/Phobos'}}
        for label,change in cases.items():
            with self.subTest(label=label),self.assertRaises(ValueError):db.create_job({**base,**change})

    def test_only_pinterest_or_reddit_can_be_stored_as_a_source(self):
        with self.assertRaises(ValueError):
            db_without_connection().store_image('0'*32,'instagram','travel','https://x','https://y',b'not an image')

    def test_editing_a_job_uses_the_same_bounds_and_fails_before_any_update(self):
        db=db_without_connection()
        base={'name':'Daily','source':'pinterest','topic_key':'travel','image_count':20,'daily_time':'09:00'}
        for label,change in (('count above twenty',{'image_count':21}),('non-integer count',{'image_count':'20'}),
                             ('time without minutes',{'daily_time':'0900'}),('name too long',{'name':'x'*121})):
            with self.subTest(label=label),self.assertRaises(ValueError):db.update_job('0'*32,{**base,**change})
        with self.assertRaises(AssertionError):db.update_job('0'*32,{**base,'image_count':3})


if __name__=='__main__':unittest.main()
