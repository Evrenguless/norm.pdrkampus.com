import unittest,tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from sitemap_tools import render_sitemaps,read_urlset,eligible_outputs,TAG
BASE='https://pdrkampus.com'
class SitemapTests(unittest.TestCase):
 def test_url_count_split_and_roundtrip(self):
  urls=[BASE+'/konu/topic-'+str(n)+'/' for n in range(7)]
  outputs=render_sitemaps(urls,BASE,max_urls=3)
  self.assertEqual(len(outputs),4)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'CNAME').write_text('pdrkampus.com')
   for name,content in outputs.items():
    file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(content)
   self.assertEqual({n.text for n in read_urlset(root).iter(TAG+'loc')},set(urls))
 def test_byte_limit_split_and_xml_escaping(self):
  urls=[BASE+'/konu/'+str(i)+'-'+'a'*100+'&b/' for i in range(6)]
  outputs=render_sitemaps(urls,BASE,max_bytes=650)
  shards=[s for name,s in outputs.items() if name!='sitemap.xml']
  self.assertGreater(len(shards),1)
  self.assertTrue(all(len(s.encode())<=650 for s in shards))
  self.assertEqual({n.text for s in shards for n in ET.fromstring(s).iter(TAG+'loc')},set(urls))
 def test_parameters_external_and_traversal_rejected(self):
  for url in [BASE+'/?q=x',BASE+'/#x','https://other.example/a/',BASE+'/../private/']:
   with self.assertRaises(ValueError):render_sitemaps([url],BASE)
 def test_only_real_self_canonical_pages_and_editorial_gate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'CNAME').write_text('pdrkampus.com')
   tree=ET.Element(TAG+'urlset')
   for name,title,meta,canonical in [('good','Unique','','good'),('noindex','Hidden','<meta name="robots" content="noindex">','noindex'),('alias','Alias','','good'),('one','Same','','one'),('two','Same','','two'),('missing','Missing','','missing')]:
    node=ET.SubElement(tree,TAG+'url');ET.SubElement(node,TAG+'loc').text=BASE+'/'+name+'/'
    if name=='missing':continue
    file=root/name/'index.html';file.parent.mkdir();file.write_text('<title>'+title+'</title><meta name="description" content="Source">'+meta+'<link rel="canonical" href="'+BASE+'/'+canonical+'/"><main><h1>'+title+'</h1><p>'+'Source content. '*20+'</p></main>')
   outputs,excluded=eligible_outputs(root,tree)
   urls={n.text for name,s in outputs.items() if name!='sitemap.xml' for n in ET.fromstring(s).iter(TAG+'loc')}
   self.assertEqual(urls,{BASE+'/good/'})
   self.assertEqual(len(excluded),5)
   # A partial re-publication must still see the other held edition on disk.
   partial=ET.Element(TAG+'urlset');node=ET.SubElement(partial,TAG+'url');ET.SubElement(node,TAG+'loc').text=BASE+'/one/'
   _,held=eligible_outputs(root,partial)
   self.assertEqual(held[BASE+'/one/'],'ambiguous_title_needs_editorial_review')
if __name__=='__main__':unittest.main()
