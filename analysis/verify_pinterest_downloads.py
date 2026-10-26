"""Validate and organize the actual files returned by the signed-in in-app browser."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.contracts import public_url, save_json
from handnavigate.transfer.download import LIMITS, downloads_folder
from handnavigate.transfer.files import image_metadata

# These exact file names and Pin IDs were returned by the browser's downloadMedia.
files = [
('f7206b6a8e7aec1a86a48c053da6daa3','433471532879457482'),
('8339606ee6000d7c85fd89a9fa37167f','638596422193890233'),
('7045a5d2381cc470ced04eb6a6db075d','976084919254897891'),
('d128075c58738f2ade425a5a8edbed1d','425238389788354076'),
('a21da2f4a44246dabd1d41b7c4c22cb6','912330837029076302'),
('35045d044a1f4a15495ac9867103fb92','893542382298529850'),
('fda7c7db87bf5bbfb26ac9d9ad599c49','647955465109369054'),
('a88e5f864238e3e6e2b452b5eeb7b3d0','800655640056912891'),
('b3e1c008338732ae85d76ac557491bd7','895934919630081838'),
('9d46b4d538d552c3d163c4cb412bbaf3','1136103443536769318'),
('5adf2adb1b2e164eb88ac5b836adda25','357051076726339732'),
('23c86c5256d2571de56377ea66a13251','782430135308028405'),
('90ffb9b1b163b494575538e05a209f21','286893438760097949'),
('622024330c2f3ad4816786bae1787067','392235448786648096'),
('cf4c6533cf5c9e59fbc6b40532a50444','642537071884224675'),
('0f674db78018901501c6852e5e395d08','370210031891889790'),
('40c6f2390f3c94b4f8f490cadb248965','233694668156936339'),
('752e41eb8bea253912a4ca994802f0b4','1052646112897502934'),
('68828613cb1212fc4f3cad3452f9b399','1018165428268950918'),
('0fbd53c826baa95aae48b5fa97dd8ece','619033911280454021'),
]
downloads = downloads_folder().resolve()
folder = (downloads/'Pinterest-nature-landscape').resolve()
assert folder.is_relative_to(downloads)
folder.mkdir(exist_ok=True)
items = []
hashes = set()
for stem, pin in files:
    source = (downloads/(stem+'.jpg')).resolve()
    destination = (folder/(stem+'.jpg')).resolve()
    assert source.parent == downloads and destination.parent == folder
    current = source if source.exists() else destination
    data = current.read_bytes()
    meta = image_metadata(data, LIMITS)
    assert meta['sha256'] not in hashes, 'Duplicate downloaded image bytes'
    hashes.add(meta['sha256'])
    if current == source:
        if destination.exists():
            raise RuntimeError('Destination already exists; no file was overwritten')
        source.rename(destination)
    assert sha256(destination.read_bytes()).hexdigest() == meta['sha256']
    image_url = 'https://i.pinimg.com/474x/'+stem[:2]+'/'+stem[2:4]+'/'+stem[4:6]+'/'+stem+'.jpg'
    items.append({**meta,'file':destination.name,'source_id':'https://in.pinterest.com/pin/'+pin+'/',
                  'image_url':image_url})
assert len(items) == len(hashes) == 20
request_url = 'https://www.pinterest.com/search/pins/?q=nature%20landscape'
result = {'schema':'handnavigate.local-download.v1','status':'VERIFIED','source':public_url(request_url),
          'request_sha256':sha256(request_url.encode()).hexdigest(),'requested':20,'downloaded':20,
          'folder':str(folder),'items':items,'error':None,'model_calls':0,
          'execution_backend':'signed-in in-app browser, DOM-derived Pin selectors and downloadMedia',
          'qualification_note':'Real Pinterest download completed through the existing in-app browser session. Standalone Chromium sign-in was not qualified by this run.'}
save_json(folder/'handnavigate-manifest.json',result)
save_json(ROOT/'runtime'/'pinterest-download'/'download-result.json',result)
save_json(ROOT/'evidence'/'pinterest-download'/'live-result.json',result)
print(json.dumps({'status':result['status'],'count':len(items),'unique_hashes':len(hashes),'folder':str(folder),
                  'total_bytes':sum(i['bytes'] for i in items),'minimum_width':min(i['width'] for i in items),
                  'minimum_height':min(i['height'] for i in items),'backend':result['execution_backend']},indent=2))
