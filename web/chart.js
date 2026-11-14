// Read a structure chart (a vector PDF) in the browser, with the same rules as casefold/structure_chart.py:
// boxes are the PDF's rectangles, relations are its line paths, the arrowhead decides the direction, the nearest text is the label.
// Coordinates are reported like pdfplumber's: x from the left, "top" from the top of the page, in points.
(function(root){
const near=(p,q,t=1.5)=>Math.abs(p[0]-q[0])<=t&&Math.abs(p[1]-q[1])<=t;
const segDist=(p,a,b)=>{const dx=b[0]-a[0],dy=b[1]-a[1];const t=(dx===0&&dy===0)?0:Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)));return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);};
const mul=(m,n)=>[m[0]*n[0]+m[2]*n[1],m[1]*n[0]+m[3]*n[1],m[0]*n[2]+m[2]*n[3],m[1]*n[2]+m[3]*n[3],m[0]*n[4]+m[2]*n[5]+m[4],m[1]*n[4]+m[3]*n[5]+m[5]];
const apply=(m,x,y)=>[m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5]];

async function readChart(pdfjsLib,data){
 const OPS=pdfjsLib.OPS;const pdf=await pdfjsLib.getDocument({data,isEvalSupported:false}).promise;
 const boxes=[],rels=[];
 for(let pno=1;pno<=pdf.numPages;pno++){
  const page=await pdf.getPage(pno);const H=page.view[3]-page.view[1];
  const ol=await page.getOperatorList();
  let ctm=[1,0,0,1,0,0],dash=false;const stack=[];let path=[];const rects=[],segs=[],heads=[];
  for(let i=0;i<ol.fnArray.length;i++){const fn=ol.fnArray[i],a=ol.argsArray[i];
   if(fn===OPS.save)stack.push([ctm,dash]);
   else if(fn===OPS.restore){const s=stack.pop();if(s){ctm=s[0];dash=s[1];}}
   else if(fn===OPS.transform)ctm=mul(ctm,a);
   else if(fn===OPS.setDash)dash=!!(a[0]&&a[0].length);
   else if(fn===OPS.constructPath){const ops=a[0],c=a[1];let k=0,cur=null,start=null;
    for(const op of ops){
     if(op===OPS.rectangle){const [x,y,w,h]=c.slice(k,k+4);k+=4;const p1=apply(ctm,x,y),p2=apply(ctm,x+w,y+h);path.push({rect:[Math.min(p1[0],p2[0]),Math.min(p1[1],p2[1]),Math.max(p1[0],p2[0]),Math.max(p1[1],p2[1])]});}
     else if(op===OPS.moveTo){cur=apply(ctm,c[k],c[k+1]);start=cur;k+=2;path.push({poly:[cur]});}
     else if(op===OPS.lineTo){const p=apply(ctm,c[k],c[k+1]);k+=2;const last=path[path.length-1];if(last&&last.poly)last.poly.push(p);cur=p;}
     else if(op===OPS.curveTo){k+=6;}else if(op===OPS.curveTo2||op===OPS.curveTo3){k+=4;}
     else if(op===OPS.closePath){const last=path[path.length-1];if(last&&last.poly){last.closed=true;}}
    }}
   else if([OPS.stroke,OPS.closeStroke,OPS.fill,OPS.eoFill,OPS.fillStroke,OPS.eoFillStroke,OPS.closeFillStroke,OPS.closeEOFillStroke,OPS.endPath].includes(fn)){
    const filled=[OPS.fill,OPS.eoFill,OPS.fillStroke,OPS.eoFillStroke,OPS.closeFillStroke,OPS.closeEOFillStroke].includes(fn),stroked=fn!==OPS.fill&&fn!==OPS.eoFill&&fn!==OPS.endPath;
    for(const s of path){
     if(s.rect){if(stroked)rects.push(s.rect);}
     else if(s.poly){const xs=s.poly.map(p=>p[0]),ys=s.poly.map(p=>p[1]);const w=Math.max(...xs)-Math.min(...xs),h=Math.max(...ys)-Math.min(...ys);
      if(filled&&(s.closed||s.poly.length>=3)&&w<16&&h<16)heads.push(s.poly);
      else if(stroked)for(let j=0;j+1<s.poly.length;j++)segs.push([s.poly[j],s.poly[j+1],dash]);}}
    path=[];}
  }
  // to pdfplumber-like coordinates: top = H - y
  const T=p=>[p[0],H-p[1]];
  const R=rects.filter(r=>r[2]-r[0]>40&&r[3]-r[1]>15).map(r=>({x0:r[0],x1:r[2],top:H-r[3],bottom:H-r[1]}));
  const S=segs.map(s=>[T(s[0]),T(s[1]),s[2]]),HD=heads.map(h=>h.map(T));
  const tc=await page.getTextContent();
  const words=tc.items.filter(it=>it.str&&it.str.trim()).map(it=>{const x=it.transform[4],y=it.transform[5],h=Math.abs(it.transform[3])||it.height;return {text:it.str.trim(),x0:x,x1:x+it.width,top:H-y-h*0.8,bottom:H-y+h*0.2};});
  const inside=(w,r)=>{const cx=(w.x0+w.x1)/2,cy=(w.top+w.bottom)/2;return cx>=r.x0-1&&cx<=r.x1+1&&cy>=r.top-1&&cy<=r.bottom+1;};
  const lines=ws=>{const out=[];for(const w of [...ws].sort((a,b)=>Math.round(a.top)-Math.round(b.top)||a.x0-b.x0)){const l=out.find(l=>Math.abs(l.top-w.top)<2&&w.x0-l.x1>=-1&&w.x0-l.x1<9);
    if(l){l.words.push(w);l.x1=w.x1;l.bottom=Math.max(l.bottom,w.bottom);}else out.push({words:[w],x0:w.x0,x1:w.x1,top:w.top,bottom:w.bottom});}
   out.forEach(l=>l.text=l.words.map(w=>w.text).join(' '));return out;};
  const pb=[];
  for(const r of R){const ls=lines(words.filter(w=>inside(w,r))).sort((a,b)=>a.top-b.top);if(!ls.length)continue;
   pb.push({page:pno,bbox:[r.x0,r.top,r.x1,r.bottom].map(v=>Math.round(v*10)/10),name:ls[0].text,detail:ls.slice(1).map(l=>l.text).join(' · '),text:ls.map(l=>l.text).join(' / ')});}
  const boxAt=p=>pb.find(b=>b.bbox[0]-4<=p[0]&&p[0]<=b.bbox[2]+4&&b.bbox[1]-4<=p[1]&&p[1]<=b.bbox[3]+4);
  // join segments that meet at a bend in open space
  const parent=S.map((_,i)=>i);const rootOf=i=>{while(parent[i]!==i){parent[i]=parent[parent[i]];i=parent[i];}return i;};
  const ends=[];S.forEach((s,i)=>{ends.push([i,s[0]]);ends.push([i,s[1]]);});
  for(const [i,e] of ends){if(boxAt(e))continue;const meet=ends.filter(([j,f])=>j!==i&&near(e,f));if(meet.length===1)parent[rootOf(i)]=rootOf(meet[0][0]);}
  const groups={};S.forEach((_,i)=>{(groups[rootOf(i)]=groups[rootOf(i)]||[]).push(i);});
  const pageRels=[];
  for(const idx of Object.values(groups)){const ss=idx.map(i=>S[i]);const pts=ss.flatMap(s=>[s[0],s[1]]);const free=pts.filter(p=>pts.filter(q=>near(p,q)).length===1);if(free.length!==2)continue;
   const arrow=free.map(e=>HD.some(h=>h.some(v=>near(e,v,2.5))));const b0=boxAt(free[0]),b1=boxAt(free[1]);if(!b0||!b1||b0===b1)continue;
   let src,dst,how='arrow';if(arrow[0]&&!arrow[1]){src=b1;dst=b0;}else if(arrow[1]&&!arrow[0]){src=b0;dst=b1;}else{[src,dst]=b0.bbox[1]<b1.bbox[1]?[b0,b1]:[b1,b0];how='position (no arrow: the upper box owns the lower)';}
   pageRels.push({page:pno,src,dst,how,dashed:ss.some(s=>s[2]),segs:ss.map(s=>[s[0],s[1]]),labels:[]});}
  const free=lines(words.filter(w=>!R.some(r=>inside(w,r))));
  for(const l of free){const anchors=[[l.x0,(l.top+l.bottom)/2],[l.x1,(l.top+l.bottom)/2]];let best=null,bd=99;
   for(const r of pageRels){const d=Math.min(...r.segs.flatMap(([a,b])=>anchors.map(p=>segDist(p,a,b))));if(d<bd){bd=d;best=r;}}
   if(best&&bd<32)best.labels.push(l);}
  for(const r of pageRels){r.label=r.labels.sort((a,b)=>a.top-b.top).map(l=>l.text).join(' ');
   const xs=r.segs.flat().concat(r.labels.flatMap(l=>[[l.x0,l.top],[l.x1,l.bottom]]));
   r.bbox=[Math.min(...xs.map(p=>p[0])),Math.min(...xs.map(p=>p[1])),Math.max(...xs.map(p=>p[0])),Math.max(...xs.map(p=>p[1]))].map(v=>Math.round(v*10)/10);}
  boxes.push(...pb);rels.push(...pageRels);
 }
 return {boxes,rels,pages:pdf.numPages};
}

const COUNTRIES={'netherlands':'NL','the netherlands':'NL','nederland':'NL','curaçao':'CW','curacao':'CW','cyprus':'CY','panama':'PA','british virgin islands':'VG','bvi':'VG','malta':'MT','luxembourg':'LU','belgium':'BE','germany':'DE','united kingdom':'GB','jersey':'JE','guernsey':'GG','cayman islands':'KY','switzerland':'CH','ireland':'IE','united states':'US','aruba':'AW','sint maarten':'SX'};
const KINDS={'person':'Person','natural person':'Person','company':'Company','foundation':'Foundation','stichting':'Foundation','trust':'Group','partnership':'Group','association':'Group'};
const SUFFIX=/\b(B\.?V\.?|N\.?V\.?|Ltd\.?|Limited|S\.?A\.?|GmbH|LLC|Inc\.?|Corp\.?|plc|Holding[s]?)\b/i;
const norm=s=>(s||'').toLowerCase().replace(/[^a-z0-9]/g,'');
function partyOf(box,clientName){const d=box.detail.toLowerCase();
 let kind=null;for(const [k,v] of Object.entries(KINDS))if(new RegExp('\\b'+k+'\\b').test(d)){kind=v;break;}
 if(!kind)kind=SUFFIX.test(box.name)?'Company':box.name.toLowerCase().startsWith('stichting')?'Foundation':'Person';
 let country=null;for(const [k,v] of Object.entries(COUNTRIES).sort((a,b)=>b[0].length-a[0].length))if(d.includes(k)){country=v;break;}
 return {name:box.name,kind,country,client:d.split(' · ').includes('client')||norm(box.name)===norm(clientName)};}
function relationOf(label){const t=label.toLowerCase();let m=t.match(/(\d+(?:[.,]\d+)?)\s*%/);let pct=m?parseFloat(m[1].replace(',','.')):null;
 if(/\bveto\b|\bcontrol|\bzeggenschap|\bdecision right/.test(t))return {type:'CONTROLS',basis:label,means:'as drawn in the structure chart'};
 if(/\bboard\b|\bbestuur/.test(t)){const v=t.match(/(\d+)\s*%\s*of\s*(?:the\s*)?votes/);return {type:'BOARD_OF',votes:v?parseInt(v[1]):pct};}
 if(/depositary receipt|certificat/.test(t))return {type:'OWNS',pct,votes:/no votes|without vot|zonder stem/.test(t)?0:pct,kind:'economic'};
 if(pct===null)return {type:'OWNS',pct:null,votes:null,kind:'legal',unclear:true};
 return {type:'OWNS',pct,votes:pct,kind:'legal'};}
const slug=name=>'P_'+name.toUpperCase().replace(/[^A-Z0-9]+/g,'_').replace(/^_|_$/g,'').slice(0,40);
root.CasefoldChart={readChart,partyOf,relationOf,norm,slug};
})(typeof window!=='undefined'?window:globalThis);
