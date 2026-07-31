var Ct=Object.defineProperty;var rt=Object.getOwnPropertySymbols;var Dt=Object.prototype.hasOwnProperty,vt=Object.prototype.propertyIsEnumerable;var st=(t,e,n)=>e in t?Ct(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n,U=(t,e)=>{for(var n in e||(e={}))Dt.call(e,n)&&st(t,n,e[n]);if(rt)for(var n of rt(e))vt.call(e,n)&&st(t,n,e[n]);return t};var it=(t,e,n)=>new Promise((a,s)=>{var f=r=>{try{b(n.next(r))}catch(u){s(u)}},$=r=>{try{b(n.throw(r))}catch(u){s(u)}},b=r=>r.done?a(r.value):Promise.resolve(r.value).then(f,$);b((n=n.apply(t,e)).next())});import{p as kt}from"./chunk-JWPE2WC7-w7wDsKu7.js";import{s as Tt,g as At,p as Bt,o as St,a as Mt,b as zt,_ as c,l as X,F as Lt,e as Nt,q as Pt,B as Z,z as J,D as Wt,W as lt}from"./index-BAopxCLJ.js";import{p as It}from"./cynefin-VYW2F7L2-B5BkO96E.js";import"./index.js";var ft=c(()=>({domains:new Map,transitions:[]}),"createDefaultData"),H=ft(),Ft=c(()=>H.domains,"getDomains"),Rt=c(()=>H.transitions,"getTransitions"),_t=c(t=>{var e;if(t)for(const n of t){const a=n.domain,s=((e=n.items)!=null?e:[]).map(f=>({label:f.label}));H.domains.set(a,{name:a,items:s})}},"setDomains"),Vt=c(t=>{t&&(H.transitions=t.filter(e=>e.from===e.to?(X.warn(`Cynefin: self-loop transition on domain "${e.from}" is not meaningful and will be skipped.`),!1):!0).map(e=>({from:e.from,to:e.to,label:e.label||void 0})))},"setTransitions"),Et=c(()=>Z(U(U({},Wt.cynefin),J().cynefin)),"getConfig"),Ht=c(()=>{Pt(),H=ft()},"clear"),Y={getDomains:Ft,getTransitions:Rt,setDomains:_t,setTransitions:Vt,getConfig:Et,clear:Ht,setAccTitle:zt,getAccTitle:Mt,setDiagramTitle:St,getDiagramTitle:Bt,getAccDescription:At,setAccDescription:Tt},Gt=c(t=>{kt(t,Y),Y.setDomains(t.domains),Y.setTransitions(t.transitions)},"populate"),Yt={parse:c(t=>it(void 0,null,function*(){const e=yield It("cynefin",t);X.debug(e),Gt(e)}),"parse")};function E(t){let e=t+1831565813|0;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}c(E,"seededRandom");function dt(t){let e=0;for(let n=0;n<t.length;n++){const a=t.charCodeAt(n);e=(e<<5)-e+a,e|=0}return e}c(dt,"hashString");function mt(t,e){return typeof t=="number"&&Number.isFinite(t)&&t!==0?t:dt(e)}c(mt,"resolveSeed");function pt(t,e,n,a){const s=t/2,f=a!=null?a:t*.015,$=7,b=e/$,r=[];for(let o=0;o<=$;o++){const p=E(n+o*17)*f*2-f;r.push({x:s+p,y:o*b})}let u=`M${r[0].x},${r[0].y}`;for(let o=0;o<r.length-1;o++){const p=r[o],l=r[o+1],m=(p.y+l.y)/2,D=o%2===0?1:-1,x=f*1.5*D*E(n+o*31+7),F=p.x+x,R=m,_=l.x-x;u+=` C${F},${R} ${_},${m} ${l.x},${l.y}`}return u}c(pt,"generateFoldPath");function yt(t,e,n,a){const s=e/2,f=a!=null?a:e*.015,$=7,b=t/$,r=[];for(let o=0;o<=$;o++){const p=E(n+o*23)*f*2-f;r.push({x:o*b,y:s+p})}let u=`M${r[0].x},${r[0].y}`;for(let o=0;o<r.length-1;o++){const p=r[o],l=r[o+1],m=(p.x+l.x)/2,D=o%2===0?1:-1,x=f*1.5*D*E(n+o*37+11),F=m,R=p.y+x,_=m,L=l.y-x;u+=` C${F},${R} ${_},${L} ${l.x},${l.y}`}return u}c(yt,"generateHorizontalBoundary");function ut(t,e){const n=t/2,a=e*.5,s=e,f=t*.03;return[`M${n},${a}`,`C${n+f},${a+(s-a)*.2}`,`${n-f*1.5},${a+(s-a)*.55}`,`${n+f*.5},${a+(s-a)*.75}`,`C${n-f},${a+(s-a)*.85}`,`${n+f*.3},${a+(s-a)*.95}`,`${n},${s}`].join(" ")}c(ut,"generateCliffPath");function ht(t,e,n,a){return[`M${t-n},${e}`,`A${n},${a} 0 1,1 ${t+n},${e}`,`A${n},${a} 0 1,1 ${t-n},${e}`,"Z"].join(" ")}c(ht,"generateConfusionPath");var ct={complex:{model:"Probe → Sense → Respond",practice:"Emergent Practices"},complicated:{model:"Sense → Analyse → Respond",practice:"Good Practices"},clear:{model:"Sense → Categorise → Respond",practice:"Best Practices"},chaotic:{model:"Act → Sense → Respond",practice:"Novel Practices"},confusion:{model:"",practice:"Disorder"}},Xt=c((t,e)=>{const n=t/2,a=e/2;return{complex:{cx:n/2,cy:a/2,x:0,y:0,w:n,h:a},complicated:{cx:n+n/2,cy:a/2,x:n,y:0,w:n,h:a},chaotic:{cx:n/2,cy:a+a/2,x:0,y:a,w:n,h:a},clear:{cx:n+n/2,cy:a+a/2,x:n,y:a,w:n,h:a},confusion:{cx:n,cy:a,x:n*.7,y:a*.7,w:n*.6,h:a*.6}}},"getDomainLayouts"),jt=c(()=>{const t=lt(),e=J();return Z(t,e.themeVariables).cynefin},"getCynefinDomainColors"),Q=3,qt=c((t,e,n,a)=>{var nt;const s=a.db,f=s.getDomains(),$=s.getTransitions(),b=s.getDiagramTitle(),r=s.getAccTitle(),u=s.getAccDescription(),o=s.getConfig(),p=jt();X.debug("Rendering Cynefin diagram");const l=o.width,m=o.height,D=o.padding,x=o.showDomainDescriptions,F=o.boundaryAmplitude,R=l+D*2,_=m+D*2,L={complex:p.complexBg,complicated:p.complicatedBg,clear:p.clearBg,chaotic:p.chaoticBg,confusion:p.confusionBg},T=Lt(e);Nt(T,_,R,(nt=o.useMaxWidth)!=null?nt:!0),T.attr("viewBox",`0 0 ${R} ${_}`),r&&T.append("title").text(r),u&&T.append("desc").text(u);const A=T.append("g").attr("transform",`translate(${D}, ${D})`),V=Xt(l,m),K=mt(o.seed,e),xt=A.append("g").attr("class","cynefin-backgrounds"),j=["complex","complicated","chaotic","clear"];for(const d of j){const i=V[d];xt.append("rect").attr("class","cynefinDomain").attr("x",i.x).attr("y",i.y).attr("width",i.w).attr("height",i.h).attr("fill",L[d]).attr("fill-opacity",.4).attr("stroke","none")}const q=A.append("g").attr("class","cynefin-boundaries");q.append("path").attr("class","cynefinBoundary").attr("d",pt(l,m,K,F)).attr("fill","none"),q.append("path").attr("class","cynefinBoundary").attr("d",yt(l,m,K+100,F)).attr("fill","none"),q.append("path").attr("class","cynefinCliff").attr("d",ut(l,m)).attr("fill","none");const gt=l*.15,$t=m*.15;A.append("path").attr("class","cynefinConfusion").attr("d",ht(l/2,m/2,gt,$t)).attr("fill",L.confusion).attr("fill-opacity",.5);const O=A.append("g").attr("class","cynefin-labels");for(const d of j){const i=V[d];O.append("text").attr("class","cynefinDomainLabel").attr("x",i.cx).attr("y",x?i.cy-30:i.cy).attr("text-anchor","middle").attr("dominant-baseline","middle").text(d.charAt(0).toUpperCase()+d.slice(1))}if(O.append("text").attr("class","cynefinDomainLabel").attr("x",l/2).attr("y",x?m/2-10:m/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text("Confusion"),x){const d=A.append("g").attr("class","cynefin-subtitles");for(const i of j){const h=V[i],y=ct[i];d.append("text").attr("class","cynefinSubtitle").attr("x",h.cx).attr("y",h.cy-10).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.model),d.append("text").attr("class","cynefinSubtitle").attr("x",h.cx).attr("y",h.cy+5).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.practice)}d.append("text").attr("class","cynefinSubtitle").attr("x",l/2).attr("y",m/2+8).attr("text-anchor","middle").attr("dominant-baseline","middle").text(ct.confusion.practice)}const tt=A.append("g").attr("class","cynefin-items"),B=26,et=10,bt=["complex","complicated","chaotic","clear","confusion"];for(const d of bt){const i=f.get(d);if(!i||i.items.length===0)continue;const h=V[d],y=d==="confusion";let N=i.items,P=0;y&&i.items.length>Q&&(P=i.items.length-Q,N=i.items.slice(0,Q));let S;if(y){const w=x?22:14;S=h.cy+w}else S=h.cy+(x?25:15);if([...N].forEach((w,M)=>{const v=S+M*(B+4),z=tt.append("g"),W=z.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",B/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(w.label);let C=w.label.length*7;const g=W.node();if(g&&typeof g.getBBox=="function"){const G=g.getBBox();G.width>0&&(C=G.width)}const k=C+et*2,I=h.cx-k/2;z.attr("transform",`translate(${I}, ${v})`),z.insert("rect","text").attr("class","cynefinItem").attr("x",0).attr("y",0).attr("width",k).attr("height",B).attr("rx",4).attr("ry",4).attr("fill",L[d]).attr("fill-opacity",.95),W.attr("x",k/2).attr("y",B/2)}),P>0){const w=S+N.length*(B+4),M=`+${P} more`,v=tt.append("g"),z=v.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",B/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(M);let W=M.length*7;const C=z.node();if(C&&typeof C.getBBox=="function"){const I=C.getBBox();I.width>0&&(W=I.width)}const g=W+et*2,k=h.cx-g/2;v.attr("transform",`translate(${k}, ${w})`),v.insert("rect","text").attr("class","cynefinItemOverflow").attr("x",0).attr("y",0).attr("width",g).attr("height",B).attr("rx",4).attr("ry",4).attr("fill",L[d]).attr("fill-opacity",.6),z.attr("x",g/2).attr("y",B/2)}}if($.length>0){const d=T.select("defs").empty()?T.append("defs"):T.select("defs"),i=`cynefin-arrow-${e}`;d.append("marker").attr("id",i).attr("viewBox","0 0 10 10").attr("refX",9).attr("refY",5).attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto-start-reverse").append("path").attr("d","M 0 0 L 10 5 L 0 10 z").attr("class","cynefinArrowHead");const h=A.append("g").attr("class","cynefin-arrows");$.forEach(y=>{const N=V[y.from],P=V[y.to];if(!N||!P)return;if(y.from===y.to){X.warn(`Cynefin renderer: skipping self-loop on domain "${y.from}"`);return}const S=N.cx,w=N.cy,M=P.cx,v=P.cy,z=(S+M)/2,W=(w+v)/2,C=M-S,g=v-w,k=Math.sqrt(C*C+g*g),I=k*.15,G=-g/k,wt=C/k,at=z+G*I,ot=W+wt*I;h.append("path").attr("class","cynefinArrowLine").attr("d",`M${S},${w} Q${at},${ot} ${M},${v}`).attr("fill","none").attr("marker-end",`url(#${i})`),y.label&&h.append("text").attr("class","cynefinArrowLabel").attr("x",at).attr("y",ot-6).attr("text-anchor","middle").attr("dominant-baseline","auto").text(y.label)})}b&&A.append("text").attr("class","cynefinTitle").attr("x",l/2).attr("y",-D/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text(b)},"draw"),Ut={draw:qt},Qt=c(()=>{const t=lt(),e=J();return Z(t,e.themeVariables).cynefin},"getCynefinTheme"),Zt=c(()=>{const t=Qt();return`
	.cynefinDomain {
		stroke: none;
	}
	.cynefinDomainLabel {
		font-size: ${t.domainFontSize}px;
		font-weight: bold;
		fill: ${t.labelColor};
	}
	.cynefinSubtitle {
		font-size: ${t.itemFontSize-1}px;
		fill: ${t.textColor};
		font-style: italic;
	}
	.cynefinItem {
		fill-opacity: 0.95;
		stroke: ${t.boundaryColor};
		stroke-width: 1;
	}
	.cynefinItemText {
		font-size: ${t.itemFontSize}px;
		fill: ${t.textColor};
	}
	.cynefinItemOverflow {
		fill-opacity: 0.6;
		stroke: ${t.boundaryColor};
		stroke-width: 1;
		stroke-dasharray: 3 2;
	}
	.cynefinBoundary {
		stroke: ${t.boundaryColor};
		stroke-width: ${t.boundaryWidth};
		stroke-dasharray: 6 3;
	}
	.cynefinCliff {
		stroke: ${t.cliffColor};
		stroke-width: ${t.cliffWidth};
	}
	.cynefinConfusion {
		stroke: ${t.boundaryColor};
		stroke-width: 1.5;
		stroke-dasharray: 4 2;
	}
	.cynefinArrowLine {
		stroke: ${t.arrowColor};
		stroke-width: ${t.arrowWidth};
		fill: none;
	}
	.cynefinArrowHead {
		fill: ${t.arrowColor};
		stroke: none;
	}
	.cynefinArrowLabel {
		font-size: ${t.itemFontSize-1}px;
		fill: ${t.textColor};
	}
	.cynefinTitle {
		font-size: ${t.domainFontSize+2}px;
		font-weight: bold;
		fill: ${t.labelColor};
	}
	`},"styles"),Jt=Zt,ae={parser:Yt,db:Y,renderer:Ut,styles:Jt};export{ae as diagram};
