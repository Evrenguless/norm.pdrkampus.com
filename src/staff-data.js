let STAFF_DATA={version:1,meta:{},schools:{}},staffLoadError=false;
function staffFor(r){return STAFF_DATA.schools[String(r.kurum_kodu)]||null;}
function staffMatch(r,value){const s=staffFor(r);if(!value)return true;if(value==='zeroListed')return r.norm===0&&(s?.listed_count||0)>0;if(value==='zeroListedOne')return r.norm===0&&s?.listed_count===1;if(value==='zeroListedMultiple')return r.norm===0&&(s?.listed_count||0)>1;if(value==='normNoRecord')return normWithoutStaffRecord(r);if(value==='review')return !!r.staffEstimated;if(value==='shortage')return !staffLoadError&&Number.isFinite(r.norm)&&r.norm>(s?.listed_count||0);if(value==='listed')return !!s;if(value==='unknown')return !s;if(value==='permanent')return !!s?.permanent_listed;if(value==='assigned')return !!s?.assigned_listed;return true;}
function normWithoutStaffRecord(r){return !staffLoadError&&Number.isFinite(r.norm)&&r.norm>0&&!staffFor(r);}
function missingStaffLabel(r){return normWithoutStaffRecord(r)?'Normu var, web sitesinde rehber öğretmen kaydı bulunamadı':'Web kaydı bulunamadı';}
function staffDifference(r){const s=staffFor(r);return s&&Number.isFinite(r.norm)?r.norm-s.listed_count:null;}
function staffNumber(n){return Number.isInteger(n)?fmt(n):'—';}
function staffReportValues(r){const s=staffFor(r);return s?[s.listed_count,s.source_url,s.checked_at,r.norm===0?'Kontrol gerekli':'Güncellik doğrulanmadı']:staffLoadError?['','','','Personel verisi yüklenemedi']:[0,'','',missingStaffLabel(r)+'; personel sayısı doğrulanmadı'];}
function staffScanDate(r){const record=staffFor(r),review=STAFF_DATA.reviewed_schools?.[String(r.kurum_kodu)];const value=review?.checked_at||record?.checked_at||STAFF_DATA.meta.exported_at;return value&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleDateString('tr-TR'):'—';}
function schoolSourceCell(r){const value=r.web_sitesi||r.kaynak_url||staffFor(r)?.source_url;try{const url=new URL(/^https?:/.test(value)?value:'https://'+value);if(!url.hostname.endsWith('.meb.k12.tr')||!['http:','https:'].includes(url.protocol))return '—';return '<a href="'+esc(url.href)+'" target="_blank" rel="noopener noreferrer">MEB okul sitesi ↗</a>';}catch{return '—';}}
function staffCells(r){const s=staffFor(r);const count=staffLoadError?'—':s?fmt(s.listed_count):normWithoutStaffRecord(r)?'<span class="reason">Norm hesaplandı ama Rehber Öğretmen verisine ulaşılamadı</span>':'0';return '<td class="pdr-count-cell">'+(staffLoadError||normWithoutStaffRecord(r)?count:'<span class="pdr-count">'+count+'</span>')+'</td><td>'+esc(staffScanDate(r))+'</td>';}
function updateStaffSummary(){}
async function loadStaffData(){
 try{const compressed=typeof DecompressionStream==='function';const res=await fetch((compressed?'data/staff-v1.json.gz':'data/staff-v1.json')+'?v=20261006-release');if(!res.ok)throw Error('staff-fetch');const p=compressed?await new Response(res.body.pipeThrough(new DecompressionStream('gzip'))).json():await res.json();
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

function applyStaffEstimates(){
 allRows=allRows.map(row=>{
  const r=row.originalRecord||row,s=staffFor(r);if(!s||!Number.isFinite(r.norm)||s.listed_count<=r.norm)return r;
  const level=r.kademe,step=level==='Özel Eğitim'?100:500,threshold=level==='Özel Eğitim'?25:level==='İlkokul'?300:level==='Meslekî Eğitim Merkezi'?200:150;
  if(!['Anaokulu','İlkokul','Ortaokul','Lise','Özel Eğitim','Meslekî Eğitim Merkezi'].includes(level))return r;
  const count=s.listed_count,lower=count===1?threshold:(count-1)*step,upper=count*step-1;
  const estimate=lower+1+(Number(r.kurum_kodu)%Math.min(19,upper-lower));
  const override={value:estimate,verified:false},code=String(r.kurum_kodu),had=Object.hasOwn(STUDENT_OVERRIDES,code),old=STUDENT_OVERRIDES[code];
  STUDENT_OVERRIDES[code]=override;const computed=normFor({...r,ogrenci_sayisi:estimate,ogrenci_sayilari:estimate});if(had)STUDENT_OVERRIDES[code]=old;else delete STUDENT_OVERRIDES[code];
  if(computed.norm!==count)return r;
  return {...r,originalRecord:r,staffEstimated:true,ogrenci_sayisi_etkin:estimate,ogrenci_sayisi_alt_100:false,ogrenci_sayisi_gosterim:fmt(estimate)+' · Tahmini',norm:computed.norm,status:'Personel varsayımı',reason:'Web listesinde '+fmt(count)+' PDR kaydı esas alınarak üretilen varsayımsal öğrenci sayısı. Kaynak öğrenci: '+r.ogrenci_sayisi_gosterim+'; kaynak norm: '+fmt(r.norm)+'. Gerçek öğrenci sayısı doğrulanmadı.'};
 });
}
