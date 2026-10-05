let STAFF_DATA={version:1,meta:{},schools:{}},staffLoadError=false;
function staffFor(r){return STAFF_DATA.schools[String(r.kurum_kodu)]||null;}
function staffMatch(r,value){const s=staffFor(r);if(!value)return true;if(value==='listed')return !!s;if(value==='unknown')return !s;if(value==='permanent')return !!s?.permanent_listed;if(value==='assigned')return !!s?.assigned_listed;return true;}
function staffDifference(r){const s=staffFor(r);return s&&Number.isFinite(r.norm)?r.norm-s.listed_count:null;}
function staffNumber(n){return Number.isInteger(n)?fmt(n):'—';}
function staffReportValues(r){const s=staffFor(r);return s?[s.listed_count,s.permanent_listed??'',s.assigned_listed??'',s.unspecified_listed??'',staffDifference(r)??'',s.source_url,s.checked_at,s.as_of||'Belirtilmemiş']:Array(8).fill('');}
function staffCells(r){
 const s=staffFor(r);if(!s)return '<td><span class="reason">Veri yok</span></td><td><span class="reason">— / —</span></td><td class="numeric">—</td>';
 const source=esc(s.source_url),date=new Date(s.checked_at).toLocaleDateString('tr-TR'),diff=staffDifference(r);
 return '<td><strong>'+fmt(s.listed_count)+'</strong><span class="reason">Listede görünen; güncellik doğrulanmadı</span><a class="staff-source" href="'+source+'" target="_blank" rel="noopener noreferrer">Personel listesi ↗</a><span class="reason">Kontrol: '+esc(date)+'</span></td><td>'+staffNumber(s.permanent_listed)+' / '+staffNumber(s.assigned_listed)+'<span class="reason">Türü belirtilmeyen: '+staffNumber(s.unspecified_listed)+'</span></td><td class="numeric">'+(diff===null?'—':(diff>0?'+':'')+fmt(diff))+'<span class="reason">Listeye göre*</span></td>';
}
function updateStaffSummary(){
 const records=filtered.map(r=>({r,s:staffFor(r)})).filter(x=>x.s),comparable=records.filter(x=>Number.isFinite(x.r.norm));
 $('staffKnownSchools').textContent=fmt(records.length);
 $('staffListedTotal').textContent=fmt(records.reduce((n,x)=>n+x.s.listed_count,0));
 $('staffComparable').textContent=fmt(comparable.length);
 $('staffComparedNorm').textContent=fmt(comparable.reduce((n,x)=>n+x.r.norm,0));
 $('staffComparedListed').textContent=fmt(comparable.reduce((n,x)=>n+x.s.listed_count,0));
 const m=STAFF_DATA.meta;
 $('staffCoverage').textContent=staffLoadError?'Personel verisi yüklenemedi. Okul normları gösteriliyor; mevcut personel sonucu üretilmedi.':'Tarama kapsamı: '+fmt(m.scanned_schools||0)+' / '+fmt(m.total_schools||55216)+' kurum. '+(m.complete?'İlk teşkilat sayfası taraması tamamlandı.':'Tarama devam ediyor; bu yayındaki veriler ara sonuçtur.');
 $('retryStaff').hidden=!staffLoadError;
}
async function loadStaffData(){
 try{const compressed=typeof DecompressionStream==='function';const res=await fetch((compressed?'data/staff-v1.json.gz':'data/staff-v1.json')+'?v=20261005-1');if(!res.ok)throw Error('staff-fetch');const p=compressed?await new Response(res.body.pipeThrough(new DecompressionStream('gzip'))).json():await res.json();
 if(Array.isArray(p.columns)&&Array.isArray(p.rows))p.schools=Object.fromEntries(p.rows.map(row=>[String(row[0]),Object.fromEntries(p.columns.slice(1).map((key,i)=>[key,row[i+1]]))]));
 if(p.version!==1||!p.schools||!p.meta)throw Error('staff-format');
 const safe={};for(const [code,s] of Object.entries(p.schools)){if(!/^\d+$/.test(code)||!Number.isInteger(s.listed_count)||s.listed_count<1)continue;
 try{const url=new URL(s.source_url);if(url.protocol!=='https:'&&url.protocol!=='http:')continue;if(!url.hostname.endsWith('.meb.k12.tr'))continue;}catch{continue;}
 if(!Number.isFinite(Date.parse(s.checked_at)))continue;
 if(['permanent_listed','assigned_listed','unspecified_listed'].some(k=>s[k]!=null&&(!Number.isInteger(s[k])||s[k]<0)))continue;
 if((s.permanent_listed||0)+(s.assigned_listed||0)+(s.unspecified_listed||0)!==s.listed_count)continue;safe[code]=s;}
 STAFF_DATA={...p,schools:safe};staffLoadError=false;
 }catch{staffLoadError=true;STAFF_DATA={version:1,meta:{},schools:{}};}
}
