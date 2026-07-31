var K=(t,n,g)=>new Promise((A,l)=>{var u=a=>{try{e(g.next(a))}catch(s){l(s)}},i=a=>{try{e(g.throw(a))}catch(s){l(s)}},e=a=>a.done?A(a.value):Promise.resolve(a.value).then(u,i);e((g=g.apply(t,n)).next())});import{p as it}from"./chunk-JWPE2WC7-w7wDsKu7.js";import{R as b,J as G,b5 as st,g as ot,s as lt,a as ct,b as gt,p as ut,o as dt,_ as h,l as W,c as pt,B as ht,F as ft,a1 as mt,e as vt,q as xt,D as yt}from"./index-BAopxCLJ.js";import{p as St}from"./cynefin-VYW2F7L2-B5BkO96E.js";import{d as Q}from"./arc-DGk_LH2Z.js";import{o as wt}from"./ordinal-Cboi1Yqb.js";import"./index.js";import"./init-Gi6I4Gst.js";function At(t,n){return n<t?-1:n>t?1:n>=t?0:NaN}function Ct(t){return t}function $t(){var t=Ct,n=At,g=null,A=b(0),l=b(G),u=b(0);function i(e){var a,s=(e=st(e)).length,f,C,T=0,m=new Array(s),o=new Array(s),v=+A.apply(this,arguments),E=Math.min(G,Math.max(-G,l.apply(this,arguments)-v)),k,F=Math.min(Math.abs(E)/s,u.apply(this,arguments)),d=F*(E<0?-1:1),$;for(a=0;a<s;++a)($=o[m[a]=a]=+t(e[a],a,e))>0&&(T+=$);for(n!=null?m.sort(function(M,x){return n(o[M],o[x])}):g!=null&&m.sort(function(M,x){return g(e[M],e[x])}),a=0,C=T?(E-s*d)/T:0;a<s;++a,v=k)f=m[a],$=o[f],k=v+($>0?$*C:0)+d,o[f]={data:e[f],index:a,value:$,startAngle:v,endAngle:k,padAngle:F};return o}return i.value=function(e){return arguments.length?(t=typeof e=="function"?e:b(+e),i):t},i.sortValues=function(e){return arguments.length?(n=e,g=null,i):n},i.sort=function(e){return arguments.length?(g=e,n=null,i):g},i.startAngle=function(e){return arguments.length?(A=typeof e=="function"?e:b(+e),i):A},i.endAngle=function(e){return arguments.length?(l=typeof e=="function"?e:b(+e),i):l},i.padAngle=function(e){return arguments.length?(u=typeof e=="function"?e:b(+e),i):u},i}var Dt=yt.pie,I={sections:new Map,showData:!1},H=I.sections,V=I.showData,Tt=structuredClone(Dt),bt=h(()=>structuredClone(Tt),"getConfig"),kt=h(()=>{H=new Map,V=I.showData,xt()},"clear"),zt=h(({label:t,value:n})=>{if(n<0)throw new Error(`"${t}" has invalid value: ${n}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);H.has(t)||(H.set(t,n),W.debug(`added new section: ${t}, with value: ${n}`))},"addSection"),Et=h(()=>H,"getSections"),Mt=h(t=>{V=t},"setShowData"),Rt=h(()=>V,"getShowData"),Y={getConfig:bt,clear:kt,setDiagramTitle:dt,getDiagramTitle:ut,setAccTitle:gt,getAccTitle:ct,setAccDescription:lt,getAccDescription:ot,addSection:zt,getSections:Et,setShowData:Mt,getShowData:Rt},Ft=h((t,n)=>{it(t,n),n.setShowData(t.showData),t.sections.map(n.addSection)},"populateDb"),Lt={parse:h(t=>K(void 0,null,function*(){const n=yield St("pie",t);W.debug(n),Ft(n,Y)}),"parse")},_t=h(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieCircle.highlighted{
    scale: 1.05;
    opacity: 1;
  }
  .pieCircle.highlightedOnHover:hover{
    transition-duration: 250ms;
    scale: 1.05;
    opacity: 1;
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),Ht=_t,Nt=h(t=>{const n=[...t.values()].reduce((l,u)=>l+u,0),g=[...t.entries()].map(([l,u])=>({label:l,value:u})).filter(l=>l.value/n*100>=1);return $t().value(l=>l.value).sort(null)(g)},"createPieArcs"),Ot=h((t,n,g,A)=>{var X,Z;W.debug(`rendering pie chart
`+t);const l=A.db,u=pt(),i=ht(l.getConfig(),u.pie),e=40,a=18,s=4,f=450,C=f,T=ft(n),m=T.append("g");m.attr("transform","translate("+C/2+","+f/2+")");const{themeVariables:o}=u;let[v]=mt(o.pieOuterStrokeWidth);v!=null||(v=2);const E=i.legendPosition,k=i.textPosition,F=i.donutHole>0&&i.donutHole<=.9?i.donutHole:0,d=Math.min(C,f)/2-e,$=Q().innerRadius(F*d).outerRadius(d),M=Q().innerRadius(d*k).outerRadius(d*k),x=m.append("g");x.append("circle").attr("cx",0).attr("cy",0).attr("r",d+v/2).attr("class","pieOuterCircle");const L=l.getSections(),tt=Nt(L),et=[o.pie1,o.pie2,o.pie3,o.pie4,o.pie5,o.pie6,o.pie7,o.pie8,o.pie9,o.pie10,o.pie11,o.pie12];let N=0;L.forEach(r=>{N+=r});const U=tt.filter(r=>(r.data.value/N*100).toFixed(0)!=="0"),O=wt(et).domain([...L.keys()]);x.selectAll("mySlices").data(U).enter().append("path").attr("d",$).attr("fill",r=>O(r.data.label)).attr("class",r=>{let c="pieCircle";return i.highlightSlice==="hover"?c+=" highlightedOnHover":i.highlightSlice===r.data.label&&(c+=" highlighted"),c}),x.selectAll("mySlices").data(U).enter().append("text").text(r=>(r.data.value/N*100).toFixed(0)+"%").attr("transform",r=>"translate("+M.centroid(r)+")").style("text-anchor","middle").attr("class","slice");const at=m.append("text").text(l.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText"),R=[...L.entries()].map(([r,c])=>({label:r,value:c})),D=m.selectAll(".legend").data(R).enter().append("g").attr("class","legend");D.append("rect").attr("width",a).attr("height",a).style("fill",r=>O(r.label)).style("stroke",r=>O(r.label)),D.append("text").attr("x",a+s).attr("y",a-s).text(r=>l.getShowData()?`${r.label} [${r.value}]`:r.label);const z=Math.max(...D.selectAll("text").nodes().map(r=>{var c;return(c=r==null?void 0:r.getBoundingClientRect().width)!=null?c:0}));let _=f,P=C+e;const p=a+s,B=R.length*p;switch(E){case"center":D.attr("transform",(r,c)=>{const y=p*R.length/2,S=-z/2-(a+s),w=c*p-y;return"translate("+S+","+w+")"});break;case"top":_+=B,D.attr("transform",(r,c)=>{const y=d,S=-z/2-(a+s),w=c*p-y;return`translate(${S}, ${w})`}),x.attr("transform",()=>`translate(0, ${B+p})`);break;case"bottom":_+=B,D.attr("transform",(r,c)=>{const y=-d-p,S=-z/2-(a+s),w=c*p-y;return"translate("+S+","+w+")"});break;case"left":P+=a+s+z,D.attr("transform",(r,c)=>{const y=p*R.length/2,S=-d-(a+s),w=c*p-y;return"translate("+S+","+w+")"}),x.attr("transform",()=>`translate(${z+a+s}, 0)`);break;case"right":default:P+=a+s+z,D.attr("transform",(r,c)=>{const y=p*R.length/2,S=12*a,w=c*p-y;return"translate("+S+","+w+")"});break}const j=(Z=(X=at.node())==null?void 0:X.getBoundingClientRect().width)!=null?Z:0,rt=C/2-j/2,nt=C/2+j/2,q=Math.min(0,rt),J=Math.max(P,nt)-q;T.attr("viewBox",`${q} 0 ${J} ${_}`),vt(T,_,J,i.useMaxWidth)},"draw"),Pt={draw:Ot},Xt={parser:Lt,db:Y,renderer:Pt,styles:Ht};export{Xt as diagram};
