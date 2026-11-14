// "New client from documents": start a client file in the page from the documents the client delivers.
// The same steps as casefold/new_client.py + structure_chart.py, run on Relate in WebAssembly:
// read the documents into Chunks (text layer, or OCR with Tesseract compiled to WebAssembly), read the structure chart into
// Proposals that are STATED_IN a chunk of the chart, let the compliance officer confirm them, then review.
// Everything stays in this tab; nothing is sent anywhere. Test data only.
(function(){
const TEMPLATE='nl-kalmora-new';
const $=id=>document.getElementById(id),esc=s=>window.CF.esc(s),loadCase=id=>window.CF.loadCase(id),drawGraph=()=>window.CF.drawGraph();
const dbx=()=>window.CF.db;
const T=window.CasefoldChart;
const exec=(script,params)=>{const out=dbx().executeScript(script,JSON.stringify(params||{})).map(s=>JSON.parse(s));const e=out.find(r=>r.error);if(e)throw new Error(e.error);return out;};
const q=(c,p)=>{const r=JSON.parse(dbx().execute(c,p?JSON.stringify(p):null));if(r.error)throw new Error(r.error);return r.rows;};
const now=()=>new Date().toISOString().slice(0,19)+'Z';
const today=()=>new Date().toISOString().slice(0,10);
const sha256=async buf=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buf))).map(b=>b.toString(16).padStart(2,'0')).join('');
let files=[];   // {file:File|Blob, name, type, status}

// ---- Cypher: the same statements as casefold/structure_chart.py, plus _vid so the page can draw the nodes
const DOC_SCRIPT=`MATCH (c:Client) MERGE (d:Document {id:$d.id}) SET d._vid='Document:' + $d.id, d.title=$d.title, d.file=$d.file, d.sha256=$d.sha256, d.pages=$d.pages,
  d.mime=$d.mime, d.ocr=$d.ocr, d.ocr_confidence=$d.ocr_confidence, d.text=$d.text, d.read_by=$d.read_by, d.uploaded=$now
MERGE (c)-[:HAS_DOCUMENT]->(d)
WITH d OPTIONAL MATCH (t:DocumentType {key:$d.doctype}) FOREACH (_ IN CASE WHEN t IS NULL THEN [] ELSE [1] END | MERGE (d)-[:OF_TYPE]->(t));
UNWIND $chunks AS k MATCH (d:Document {id:$d.id}) MERGE (x:Chunk {id:k.id}) SET x._vid='Chunk:' + k.id, x.page=k.page, x.text=k.text, x.bbox=k.bbox, x.kind=k.kind,
  x.confidence=k.confidence, x.lang=k.lang MERGE (d)-[:HAS_CHUNK]->(x)`;
const PROPOSE=`UNWIND $props AS p MATCH (k:Chunk {id:p.chunk}) MERGE (x:Proposal {id:p.id}) ON CREATE SET x.status='proposed'
  SET x._vid='Proposal:' + p.id, x.kind=p.kind, x.from_name=p.from_name, x.to_name=p.to_name, x.party_kind=p.party_kind, x.country=p.country, x.is_client=p.is_client,
      x.pct=p.pct, x.votes=p.votes, x.own_kind=p.own_kind, x.basis=p.basis, x.direction=p.direction, x.unclear=p.unclear, x.text=p.text,
      x.method='structure chart, vector PDF, read in the browser', x.made=$now
  MERGE (x)-[:STATED_IN]->(k)`;
const CONFIRM=`UNWIND [p IN $parties WHERE NOT p.is_client] AS p MERGE (x:Party {id:p.pid}) ON CREATE SET x._vid='Party:' + p.pid, x.name=p.name, x.kind=p.kind, x.country=p.country, x.pep=false, x.listed=false;
MATCH (x:Party {kind:'Person'}) SET x:Person;
MATCH (x:Party {kind:'Company'}) SET x:Company;
MATCH (x:Party {kind:'Foundation'}) SET x:Foundation;
MATCH (x:Party {kind:'Group'}) SET x:Group;
UNWIND $rels AS r MATCH (a:Party {id:r.from}) MATCH (b) WHERE (b:Party AND b.id = r.to) OR (b:Client AND r.to = 'client')
  FOREACH (_ IN CASE WHEN r.type = 'OWNS' THEN [1] ELSE [] END | MERGE (a)-[x:OWNS]->(b) SET x.pct=r.pct, x.votes=r.votes, x.kind=r.own_kind, x.lender=false, x.source=r.doc, x.where=r.where, x.evidence=r.chunk)
  FOREACH (_ IN CASE WHEN r.type = 'CONTROLS' THEN [1] ELSE [] END | MERGE (a)-[x:CONTROLS]->(b) SET x.basis=r.basis, x.means=r.means, x.source=r.doc, x.where=r.where, x.evidence=r.chunk)
  FOREACH (_ IN CASE WHEN r.type = 'BOARD_OF' THEN [1] ELSE [] END | MERGE (a)-[x:BOARD_OF]->(b) SET x.votes=r.votes, x.source=r.doc, x.where=r.where, x.evidence=r.chunk);
UNWIND $rels AS r MATCH (d:Document {id:r.doc}), (a:Party {id:r.from}) MERGE (d)-[:MENTIONS]->(a);
UNWIND $ids AS i MATCH (p:Proposal {id:i}) SET p.status='confirmed', p.confirmed_by=$by, p.confirmed_at=$now;
UNWIND $parties AS p MATCH (x:Proposal {id:p.prop}) MATCH (n) WHERE (n:Party AND n.id = p.pid) OR (n:Client AND p.is_client) MERGE (x)-[:CREATED]->(n)`;
const REQUIRED=`MATCH (c:Client)-[q:REQUIRES]->(t:DocumentType)
OPTIONAL MATCH (d:Document)-[:OF_TYPE]->(t)
OPTIONAL MATCH (c)-[:SUBJECT_TO]->(o:Obligation)-[:PROVEN_BY]->(t)
OPTIONAL MATCH (a:Article)-[:IMPOSES]->(o)
OPTIONAL MATCH (c)-[:HAS_TRIGGER]->(g:RiskTrigger)-[:ADDS_REQUIREMENT]->(t)
OPTIONAL MATCH (c)-[:HAS_LEGAL_FORM]->(f:LegalForm)-[:REQUIRES_DOC]->(t)
RETURN t.name AS type, collect(DISTINCT d.id + ' ' + d.title) AS present, collect(DISTINCT a.ref) AS articles,
       collect(DISTINCT g.name) AS triggers, collect(DISTINCT f.abbr) AS legal_form
ORDER BY size(present) > 0, type`;

// ---- reading files
let tess=null;
const loadScript=src=>new Promise((ok,no)=>{const s=document.createElement('script');s.src=src;s.onload=ok;s.onerror=()=>no(new Error('could not load '+src));document.head.appendChild(s);});
async function ocrWorker(log){if(tess)return tess;
 if(!window.Tesseract)await loadScript('vendor/tesseract/tesseract.min.js');
 const abs=p=>new URL(p,location.href).href;
 log('Starting Tesseract (WebAssembly) with Dutch and English…');
 tess=await window.Tesseract.createWorker(['nld','eng'],1,{workerPath:abs('vendor/tesseract/ocr-worker.js'),workerBlobURL:false,cacheMethod:'none',corePath:abs('vendor/tesseract/tesseract-core-simd-lstm.wasm.js'),
   langPath:abs('vendor/tesseract/lang'),gzip:true,logger:m=>{if(m.status==='recognizing text'&&m.progress)log(`OCR… ${Math.round(m.progress*100)}%`);}});
 return tess;}
async function ocrImage(img,page,id,log){const w=await ocrWorker(log);const r=await w.recognize(img,{},{blocks:true,text:true});
 const paras=(r.data.blocks||[]).flatMap(b=>b.paragraphs||[]).filter(p=>p.text&&p.text.trim());
 return paras.map((p,i)=>({id:`${id}-p${page}-c${i+1}`,page,text:p.text.trim().replace(/\s+\n/g,'\n'),bbox:[p.bbox.x0,p.bbox.y0,p.bbox.x1,p.bbox.y1],kind:'ocr',confidence:Math.round(p.confidence),lang:'nld+eng'}));}
async function pdfDoc(buf){window.pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';return window.pdfjsLib.getDocument({data:new Uint8Array(buf)}).promise;}
async function readDocument(f,id,log){const buf=await f.file.arrayBuffer();const ext=f.name.toLowerCase().split('.').pop();let chunks=[],pages=1,ocr=false,mime='';
 if(ext==='pdf'){mime='application/pdf';const pdf=await pdfDoc(buf.slice(0));pages=pdf.numPages;
  for(let p=1;p<=pages;p++){const pg=await pdf.getPage(p);const tc=await pg.getTextContent();const txt=tc.items.map(i=>i.str+(i.hasEOL?'\n':' ')).join('').trim();
   if(txt.length>20){txt.split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean).forEach((s,i)=>chunks.push({id:`${id}-p${p}-c${i+1}`,page:p,text:s,bbox:null,kind:'text',confidence:100,lang:'und'}));}
   else{ocr=true;log(`${f.name}: page ${p} has no text layer, OCR…`);const vp=pg.getViewport({scale:300/72});const cv=document.createElement('canvas');cv.width=vp.width;cv.height=vp.height;
    await pg.render({canvasContext:cv.getContext('2d'),viewport:vp}).promise;chunks.push(...await ocrImage(cv,p,id,log));}}}
 else if(['png','jpg','jpeg','gif','bmp','webp'].includes(ext)){mime='image/'+(ext==='jpg'?'jpeg':ext);ocr=true;log(`${f.name}: OCR…`);chunks=await ocrImage(f.file,1,id,log);}
 else{mime='text/plain';const t=new TextDecoder().decode(buf);t.split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean).forEach((s,i)=>chunks.push({id:`${id}-p1-c${i+1}`,page:1,text:s,bbox:null,kind:'text',confidence:100,lang:'und'}));}
 const conf=chunks.length?Math.round(chunks.reduce((a,c)=>a+(c.confidence||0),0)/chunks.length):null;
 exec(DOC_SCRIPT,{d:{id,title:f.title||f.name,file:f.name,sha256:await sha256(buf),pages,mime,ocr,ocr_confidence:ocr?conf:null,doctype:f.type,
   text:chunks.map(c=>c.text).join('\n'),read_by:ocr?'Tesseract 5 (WebAssembly, nld+eng) in this page':'pdf.js text layer in this page'},chunks,now:now()});
 return `${f.name}: ${chunks.length} chunks${ocr?` (OCR, mean confidence ${conf})`:''}`;}
async function readChartFile(f,id,log){const buf=await f.file.arrayBuffer();const r=await T.readChart(window.pdfjsLib,new Uint8Array(buf.slice(0)));
 if(!r.boxes.length)throw new Error(`${f.name}: no boxes found; is this a vector PDF? A scanned chart cannot be read this way.`);
 const client=q('MATCH (c:Client) RETURN c.name AS n')[0].n;const chunks=[],props=[];let n=0;
 r.boxes.forEach((b,i)=>{const p=T.partyOf(b,client);const cid=`${id}-p${b.page}-box${i+1}`;chunks.push({id:cid,page:b.page,text:b.text,bbox:b.bbox,kind:'chart_box',confidence:100,lang:'und'});
  props.push({id:`SC-${++n}`,chunk:cid,kind:'party',from_name:p.name,to_name:null,party_kind:p.kind,country:p.country,is_client:p.client,text:b.text});});
 r.rels.forEach((x,i)=>{const rel=T.relationOf(x.label);const cid=`${id}-p${x.page}-line${i+1}`;const text=`${x.src.name} → ${x.dst.name}: ${x.label||'(no label)'}`;
  chunks.push({id:cid,page:x.page,text,bbox:x.bbox,kind:'chart_line',confidence:100,lang:'und'});
  props.push({id:`SC-${++n}`,chunk:cid,kind:rel.type,from_name:x.src.name,to_name:x.dst.name,pct:rel.pct??null,votes:rel.votes??null,own_kind:rel.kind||null,basis:rel.basis||null,direction:x.how,unclear:!!rel.unclear,text});});
 exec(DOC_SCRIPT,{d:{id,title:f.title||'Structure chart (delivered by the client)',file:f.name,sha256:await sha256(buf),pages:r.pages,mime:'application/pdf',ocr:false,ocr_confidence:null,doctype:'structure_chart',
   text:chunks.map(c=>c.text).join('\n'),read_by:'structure chart reader (pdf.js vector paths) in this page'},chunks,now:now()});
 exec(PROPOSE,{props,now:now()});
 return `${f.name}: ${r.boxes.length} boxes and ${r.rels.length} lines → ${props.length} proposals`;}

// ---- UI
const D=()=>$('ncBody');
function typeOptions(sel){const ts=q("MATCH (t:DocumentType) RETURN t.key AS k, t.name AS n ORDER BY n");return ts.map(t=>`<option value="${esc(t.k)}"${t.k===sel?' selected':''}>${esc(t.n)}</option>`).join('');}
function guessType(name){const stem=name.toLowerCase().replace(/\.[^.]+$/,'').replace(/[-_ ]?\d+$/,'');const keys=q("MATCH (t:DocumentType) RETURN t.key AS k").map(r=>r.k);return keys.includes(stem)?stem:'other';}
function drawFiles(){$('ncDocs').innerHTML=files.length?`<table><thead><tr><th>File</th><th>Document type</th><th>Status</th></tr></thead><tbody>${files.map((f,i)=>`<tr><td>${esc(f.name)}</td><td><select data-i="${i}" aria-label="Document type of ${esc(f.name)}">${typeOptions(f.type)}</select></td><td>${esc(f.status||'not read yet')}</td></tr>`).join('')}</tbody></table>`:'<div class="note">No documents yet. Choose the client\'s files, or use the example documents.</div>';
 $('ncDocs').querySelectorAll('select').forEach(s=>s.onchange=()=>{files[+s.dataset.i].type=s.value;});$('ncRead').disabled=!files.some(f=>!f.done);}
function drawProps(){const rows=q(`MATCH (p:Proposal)-[:STATED_IN]->(k:Chunk)<-[:HAS_CHUNK]-(d:Document) RETURN p.id AS id, p.status AS status, p.kind AS kind, p.from_name AS frm, p.to_name AS to, p.party_kind AS pk,
   p.country AS country, p.is_client AS client, p.pct AS pct, p.votes AS votes, p.basis AS basis, p.unclear AS unclear, d.id AS doc, k.page AS page, k.bbox AS bbox`).sort((a,b)=>+a.id.split('-')[1]-+b.id.split('-')[1]);
 if(!rows.length){$('ncProps').innerHTML='<div class="note">No structure chart read yet.</div>';$('ncPropBtns').hidden=true;return;}
 const what=r=>r.kind==='party'?`<b>${esc(r.frm)}</b> · ${esc(r.pk)}${r.country?' · '+esc(r.country):''}${r.client?' · <i>the client</i>':''}`:
  r.kind==='OWNS'?`<b>${esc(r.frm)}</b> owns <b>${esc(r.to)}</b>: ${r.pct??'?'}% of the shares, ${r.votes??'?'}% of the votes${r.unclear?' <span class="warn">(label unclear: check)</span>':''}`:
  r.kind==='CONTROLS'?`<b>${esc(r.frm)}</b> controls <b>${esc(r.to)}</b>: ${esc(r.basis)}`:`<b>${esc(r.frm)}</b> is on the board of <b>${esc(r.to)}</b>: exercises ${r.votes}% of the votes`;
 $('ncProps').innerHTML=`<table><thead><tr><th></th><th>Id</th><th>The chart says</th><th>Where in the chart</th><th>Status</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.status==='confirmed'?'ok':r.status==='rejected'?'rej':''}">
  <td>${r.status==='proposed'?`<input type="checkbox" data-id="${esc(r.id)}" checked aria-label="select ${esc(r.id)}">`:''}</td><td class="mono">${esc(r.id)}</td><td>${what(r)}</td>
  <td class="mono">${esc(r.doc)} p.${r.page} (${Math.round(r.bbox[0])}, ${Math.round(r.bbox[1])})</td><td>${esc(r.status)}</td></tr>`).join('')}</tbody></table>`;
 $('ncPropBtns').hidden=!rows.some(r=>r.status==='proposed');}
function confirmProps(ids){const rows=q(`MATCH (p:Proposal)-[:STATED_IN]->(k:Chunk)<-[:HAS_CHUNK]-(d:Document) RETURN p.id AS id, p.status AS status, p.kind AS kind, p.from_name AS frm, p.to_name AS to,
   p.party_kind AS pk, p.country AS country, p.is_client AS client, p.pct AS pct, p.votes AS votes, p.own_kind AS own_kind, p.basis AS basis, d.id AS doc, k.id AS chunk, k.page AS page, k.bbox AS bbox`);
 const chosen=rows.filter(r=>r.status==='proposed'&&ids.includes(r.id));if(!chosen.length)return 0;
 const existing=Object.fromEntries(q('MATCH (p:Party) RETURN p.id AS id, p.name AS name').map(r=>[T.norm(r.name),r.id]));const client=T.norm(q('MATCH (c:Client) RETURN c.name AS n')[0].n);
 const partyRows=Object.fromEntries(rows.filter(r=>r.kind==='party').map(r=>[T.norm(r.frm),r]));
 const pid=name=>T.norm(name)===client?'client':existing[T.norm(name)]||T.slug(name);
 const parties=[],rels=[];const add=pr=>{if(pr&&pr.status==='proposed'&&!parties.some(p=>p.prop===pr.id))parties.push({prop:pr.id,pid:pid(pr.frm),name:pr.frm,kind:pr.pk,country:pr.country,is_client:!!pr.client||pid(pr.frm)==='client'});};
 chosen.filter(r=>r.kind==='party').forEach(add);
 chosen.filter(r=>r.kind!=='party').forEach(r=>{add(partyRows[T.norm(r.frm)]);add(partyRows[T.norm(r.to)]);
  rels.push({type:r.kind,from:pid(r.frm),to:pid(r.to),pct:r.pct,votes:r.votes,own_kind:r.own_kind||'legal',basis:r.basis,means:'as drawn in the structure chart',chunk:r.chunk,doc:r.doc,
   where:`structure chart p.${r.page}, line at (${Math.round(r.bbox[0])},${Math.round(r.bbox[1])})`});});
 const all=[...new Set([...chosen.map(r=>r.id),...parties.map(p=>p.prop)])];
 exec(CONFIRM,{parties,rels,ids:all,by:'compliance officer (in this page)',now:now()});return all.length;}
function review(){if(!q('MATCH (d:Document) RETURN count(d) AS n')[0].n){$('ncReview').innerHTML='<div class="note">The review appears once the client\'s documents are read into the graph (step 02). It then compares the required documents with what was delivered, and the beneficial owners with the UBO register.</div>';return;}
 const on=today();const req=q(REQUIRED);const miss=req.filter(r=>!r.present.length);
 const conf=q("MATCH ()-[r:OWNS|CONTROLS|BOARD_OF]->() RETURN count(r) AS n")[0].n;const open=q("MATCH (p:Proposal {status:'proposed'}) RETURN count(p) AS n")[0].n;
 let ubos=[];if(conf){const u=window.CF.QUERIES.find(x=>x.id==='03');ubos=q(u.cypher,{on});}
 const gaps=ubos.filter(u=>u.ubo&&u.declaration!=='declared');
 const basis=r=>[...r.articles,...r.legal_form.filter(Boolean).map(x=>'legal form '+x),...r.triggers.map(x=>'risk: '+x)].join('; ')||'rule of the office';
 const reqText=[...miss.map(r=>`- ${r.type}${r.articles.length?' ('+r.articles.slice(0,2).join('; ')+')':''}`),...gaps.map(u=>`- Please explain why ${u.person} is not in the UBO declaration / UBO register: the structure chart you delivered makes ${u.person} a beneficial owner (${u.grounds_met.join(', ')}).`)].join('\n');
 $('ncReview').innerHTML=`<div class="kpis"><div><b>${req.length-miss.length}</b> of ${req.length} required documents present</div><div><b>${miss.length}</b> missing</div>${conf?`<div><b>${ubos.filter(u=>u.ubo).length}</b> beneficial owners</div><div class="${gaps.length?'warn':''}"><b>${gaps.length}</b> not declared</div>`:'<div>beneficial owners: after the structure is confirmed (step 03)</div>'}</div>
  <h5>Beneficial owners${conf?'':' (not determined yet)'}</h5>${conf?`<table><thead><tr><th>Person</th><th>Shares</th><th>Votes</th><th>Control</th><th>Grounds met</th><th>UBO register / declaration</th></tr></thead><tbody>${ubos.map(u=>`<tr class="${u.ubo&&u.declaration!=='declared'?'gap':''}"><td>${u.ubo?'<b>':''}${esc(u.person)}${u.ubo?'</b>':''}</td><td>${u.ownership}%</td><td>${u.votes}%</td><td>${u.control_other_means?'yes':'no'}</td><td>${esc(u.grounds_met.join(', ')||'–')}</td><td>${esc(u.declaration)}</td></tr>`).join('')}</tbody></table>${open?`<div class="note">${open} proposals from the structure chart are not confirmed yet.</div>`:''}`
   :`<div class="note">The structure is not confirmed yet: ${open} proposals from the structure chart wait for the compliance officer.</div>`}
  <h5>Required documents</h5><table><thead><tr><th></th><th>Document type</th><th>In the file</th><th>Basis</th></tr></thead><tbody>${req.map(r=>`<tr><td>${r.present.length?'✓':'<span class="warn">✗</span>'}</td><td>${esc(r.type)}</td><td>${esc(r.present.join(', ')||'missing')}</td><td>${esc(basis(r))}</td></tr>`).join('')}</tbody></table>
  <h5>Request to the client</h5><textarea id="ncReq" rows="7" aria-label="Request to the client">${esc(reqText)}</textarea><div><button class="b" id="ncCopy" type="button">Copy</button> <span class="note">The decision stays with the compliance officer.</span></div>`;
 $('ncCopy').onclick=async()=>{try{await navigator.clipboard.writeText($('ncReq').value);$('ncCopy').textContent='Copied';}catch(e){$('ncReq').select();}};}
function refresh(){drawProps();review();drawGraph();}
const log=t=>{$('ncLog').textContent=t;};
async function start(){await loadCase(TEMPLATE);files=[];
 const c=q("MATCH (c:Client) OPTIONAL MATCH (c)-[:HAS_LEGAL_FORM]->(f:LegalForm) OPTIONAL MATCH (c)-[:CLIENT_OF]->(i:Institution) RETURN c.name AS name, f.name AS lf, c.risk_band AS risk, i.name AS office")[0];
 $('ncClient').innerHTML=`<b>${esc(c.name)}</b> · ${esc(c.lf||'')}${c.risk?' · risk '+esc(c.risk):''} · client of ${esc(c.office||'')}<br><span class="note">A fresh client file: no documents, no structure yet. Fictitious test client.</span>`;
 drawFiles();refresh();$('ncLog').textContent='';$('ncDrawer').hidden=false;}
async function readAll(){$('ncRead').disabled=true;try{
  const nextId=()=>{const ids=q('MATCH (d:Document) RETURN d.id AS id').map(r=>r.id).filter(i=>/^D\d+$/.test(i)).map(i=>+i.slice(1));return 'D'+(1+Math.max(0,...ids));};
  for(const f of files.filter(f=>!f.done)){f.status='reading…';drawFiles();const id=nextId();
   f.status=f.type==='structure_chart'?await readChartFile(f,id,log):await readDocument(f,id,log);f.done=true;drawFiles();}
  log('Read into the graph. Check the proposals from the structure chart, then confirm them.');refresh();}
 catch(e){log(e.message);console.error(e);}finally{drawFiles();}}
function init(){
 const btn=$('newClient');if(!btn)return;btn.onclick=()=>start().catch(e=>{console.error(e);$('ncDrawer').hidden=false;$('ncLog').textContent=e.message;});
 $('ncClose').onclick=()=>{$('ncDrawer').hidden=true;};
 $('ncFiles').onchange=e=>{for(const f of e.target.files)files.push({file:f,name:f.name,type:guessType(f.name)});e.target.value='';drawFiles();};
 $('ncExample').onclick=async()=>{for(const n of ['structure_chart.pdf','ubo_register_extract.png']){if(files.some(f=>f.name===n))continue;
   const b=await (await fetch('data/examples/'+n)).blob();files.push({file:b,name:n,type:guessType(n),title:n==='structure_chart.pdf'?'Structuurschema groep (aangeleverd door de client)':'Uittreksel UBO-register'});}drawFiles();};
 $('ncRead').onclick=readAll;
 $('ncConfirmSel').onclick=()=>{const ids=[...$('ncProps').querySelectorAll('input[type=checkbox]:checked')].map(x=>x.dataset.id);const n=confirmProps(ids);log(`${n} proposals confirmed.`);refresh();};
 $('ncConfirmAll').onclick=()=>{const ids=q("MATCH (p:Proposal {status:'proposed'}) RETURN p.id AS id").map(r=>r.id);const n=confirmProps(ids);log(`${n} proposals confirmed.`);refresh();};
 $('ncReject').onclick=()=>{const ids=[...$('ncProps').querySelectorAll('input[type=checkbox]:checked')].map(x=>x.dataset.id);
   exec("UNWIND $ids AS i MATCH (p:Proposal {id:i}) WHERE p.status = 'proposed' SET p.status='rejected', p.rejected_by='compliance officer (in this page)', p.rejected_at=$now",{ids,now:now()});refresh();};
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('ncDrawer').hidden)$('ncClose').click();});}
window.casefoldNewClient={start,readAll,confirmProps,review};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else setTimeout(init,0);
})();
