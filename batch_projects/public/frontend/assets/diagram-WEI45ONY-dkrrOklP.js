var _=Object.defineProperty;var b=Object.getOwnPropertySymbols;var D=Object.prototype.hasOwnProperty,E=Object.prototype.propertyIsEnumerable;var A=(a,t,e)=>t in a?_(a,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):a[t]=e,C=(a,t)=>{for(var e in t||(t={}))D.call(t,e)&&A(a,e,t[e]);if(b)for(var e of b(t))E.call(t,e)&&A(a,e,t[e]);return a};var M=(a,t,e)=>new Promise((r,s)=>{var o=n=>{try{i(e.next(n))}catch(c){s(c)}},l=n=>{try{i(e.throw(n))}catch(c){s(c)}},i=n=>n.done?r(n.value):Promise.resolve(n.value).then(o,l);i((e=e.apply(a,t)).next())});import{p as z}from"./chunk-JWPE2WC7-w7wDsKu7.js";import{s as P,g as G,p as B,o as W,a as V,b as H,_ as d,F as j,q,B as w,z as L,D as N,l as U,W as X,e as Y}from"./index-BAopxCLJ.js";import{p as Z}from"./cynefin-VYW2F7L2-B5BkO96E.js";import"./index.js";var h={showLegend:!0,ticks:5,max:null,min:0,graticule:"circle"},T={axes:[],curves:[],options:h},m=structuredClone(T),J=N.radar,K=d(()=>w(C(C({},J),L().radar)),"getConfig"),S=d(()=>m.axes,"getAxes"),Q=d(()=>m.curves,"getCurves"),tt=d(()=>m.options,"getOptions"),et=d(a=>{m.axes=a.map(t=>{var e;return{name:t.name,label:(e=t.label)!=null?e:t.name}})},"setAxes"),at=d(a=>{m.curves=a.map(t=>{var e;return{name:t.name,label:(e=t.label)!=null?e:t.name,entries:rt(t.entries)}})},"setCurves"),rt=d(a=>{if(a[0].axis==null)return a.map(e=>e.value);const t=S();if(t.length===0)throw new Error("Axes must be populated before curves for reference entries");return t.map(e=>{const r=a.find(s=>{var o;return((o=s.axis)==null?void 0:o.$refText)===e.name});if(r===void 0)throw new Error("Missing entry for axis "+e.label);return r.value})},"computeCurveEntries"),st=d(a=>{var e,r,s,o,l,i,n,c,p,u;const t=a.reduce((g,x)=>(g[x.name]=x,g),{});m.options={showLegend:(r=(e=t.showLegend)==null?void 0:e.value)!=null?r:h.showLegend,ticks:(o=(s=t.ticks)==null?void 0:s.value)!=null?o:h.ticks,max:(i=(l=t.max)==null?void 0:l.value)!=null?i:h.max,min:(c=(n=t.min)==null?void 0:n.value)!=null?c:h.min,graticule:(u=(p=t.graticule)==null?void 0:p.value)!=null?u:h.graticule}},"setOptions"),nt=d(()=>{q(),m=structuredClone(T)},"clear"),f={getAxes:S,getCurves:Q,getOptions:tt,setAxes:et,setCurves:at,setOptions:st,getConfig:K,clear:nt,setAccTitle:H,getAccTitle:V,setDiagramTitle:W,getDiagramTitle:B,getAccDescription:G,setAccDescription:P},ot=d(a=>{z(a,f);const{axes:t,curves:e,options:r}=a;f.setAxes(t),f.setCurves(e),f.setOptions(r)},"populate"),it={parse:d(a=>M(void 0,null,function*(){const t=yield Z("radar",a);U.debug(t),ot(t)}),"parse")},lt=d((a,t,e,r)=>{var $;const s=r.db,o=s.getAxes(),l=s.getCurves(),i=s.getOptions(),n=s.getConfig(),c=s.getDiagramTitle(),p=j(t),u=ct(p,n),g=($=i.max)!=null?$:Math.max(...l.map(y=>Math.max(...y.entries))),x=i.min,v=Math.min(n.width,n.height)/2;dt(u,o,v,i.ticks,i.graticule),ut(u,o,v,n),O(u,o,l,x,g,i.graticule,n),F(u,l,i.showLegend,n),u.append("text").attr("class","radarTitle").text(c).attr("x",0).attr("y",-n.height/2-n.marginTop)},"draw"),ct=d((a,t)=>{var o;const e=t.width+t.marginLeft+t.marginRight,r=t.height+t.marginTop+t.marginBottom,s={x:t.marginLeft+t.width/2,y:t.marginTop+t.height/2};return Y(a,r,e,(o=t.useMaxWidth)!=null?o:!0),a.attr("viewBox",`0 0 ${e} ${r}`).attr("overflow","visible"),a.append("g").attr("transform",`translate(${s.x}, ${s.y})`)},"drawFrame"),dt=d((a,t,e,r,s)=>{if(s==="circle")for(let o=0;o<r;o++){const l=e*(o+1)/r;a.append("circle").attr("r",l).attr("class","radarGraticule")}else if(s==="polygon"){const o=t.length;for(let l=0;l<r;l++){const i=e*(l+1)/r,n=t.map((c,p)=>{const u=2*p*Math.PI/o-Math.PI/2,g=i*Math.cos(u),x=i*Math.sin(u);return`${g},${x}`}).join(" ");a.append("polygon").attr("points",n).attr("class","radarGraticule")}}},"drawGraticule"),ut=d((a,t,e,r)=>{const s=t.length;for(let o=0;o<s;o++){const l=t[o].label,i=2*o*Math.PI/s-Math.PI/2,n=Math.cos(i),c=Math.sin(i);a.append("line").attr("x1",0).attr("y1",0).attr("x2",e*r.axisScaleFactor*n).attr("y2",e*r.axisScaleFactor*c).attr("class","radarAxisLine");const p=n>.01?"start":n<-.01?"end":"middle",u=c>.01?"hanging":c<-.01?"auto":"central",g=4;a.append("text").text(l).attr("x",e*r.axisLabelFactor*n+g*n).attr("y",e*r.axisLabelFactor*c+g*c).attr("text-anchor",p).attr("dominant-baseline",u).attr("class","radarAxisLabel")}},"drawAxes");function O(a,t,e,r,s,o,l){const i=t.length,n=Math.min(l.width,l.height)/2;e.forEach((c,p)=>{if(c.entries.length!==i)return;const u=c.entries.map((g,x)=>{const v=2*Math.PI*x/i-Math.PI/2,$=k(g,r,s,n),y=$*Math.cos(v),I=$*Math.sin(v);return{x:y,y:I}});o==="circle"?a.append("path").attr("d",R(u,l.curveTension)).attr("class",`radarCurve-${p}`):o==="polygon"&&a.append("polygon").attr("points",u.map(g=>`${g.x},${g.y}`).join(" ")).attr("class",`radarCurve-${p}`)})}d(O,"drawCurves");function k(a,t,e,r){const s=Math.min(Math.max(a,t),e);return r*(s-t)/(e-t)}d(k,"relativeRadius");function R(a,t){const e=a.length;let r=`M${a[0].x},${a[0].y}`;for(let s=0;s<e;s++){const o=a[(s-1+e)%e],l=a[s],i=a[(s+1)%e],n=a[(s+2)%e],c={x:l.x+(i.x-o.x)*t,y:l.y+(i.y-o.y)*t},p={x:i.x-(n.x-l.x)*t,y:i.y-(n.y-l.y)*t};r+=` C${c.x},${c.y} ${p.x},${p.y} ${i.x},${i.y}`}return`${r} Z`}d(R,"closedRoundCurve");function F(a,t,e,r){if(!e)return;const s=(r.width/2+r.marginRight)*3/4,o=-(r.height/2+r.marginTop)*3/4,l=20;t.forEach((i,n)=>{const c=a.append("g").attr("transform",`translate(${s}, ${o+n*l})`);c.append("rect").attr("width",12).attr("height",12).attr("class",`radarLegendBox-${n}`),c.append("text").attr("x",16).attr("y",0).attr("class","radarLegendText").text(i.label)})}d(F,"drawLegend");var pt={draw:lt},gt=d((a,t)=>{let e="";for(let r=0;r<a.THEME_COLOR_LIMIT;r++){const s=a[`cScale${r}`];e+=`
		.radarCurve-${r} {
			color: ${s};
			fill: ${s};
			fill-opacity: ${t.curveOpacity};
			stroke: ${s};
			stroke-width: ${t.curveStrokeWidth};
		}
		.radarLegendBox-${r} {
			fill: ${s};
			fill-opacity: ${t.curveOpacity};
			stroke: ${s};
		}
		`}return e},"genIndexStyles"),xt=d(a=>{const t=X(),e=L(),r=w(t,e.themeVariables),s=w(r.radar,a);return{themeVariables:r,radarOptions:s}},"buildRadarStyleOptions"),mt=d(({radar:a}={})=>{const{themeVariables:t,radarOptions:e}=xt(a);return`
	.radarTitle {
		font-size: ${t.fontSize};
		color: ${t.titleColor};
		dominant-baseline: hanging;
		text-anchor: middle;
	}
	.radarAxisLine {
		stroke: ${e.axisColor};
		stroke-width: ${e.axisStrokeWidth};
	}
	.radarAxisLabel {
		font-size: ${e.axisLabelFontSize}px;
		color: ${e.axisColor};
	}
	.radarGraticule {
		fill: ${e.graticuleColor};
		fill-opacity: ${e.graticuleOpacity};
		stroke: ${e.graticuleColor};
		stroke-width: ${e.graticuleStrokeWidth};
	}
	.radarLegendText {
		text-anchor: start;
		font-size: ${e.legendFontSize}px;
		dominant-baseline: hanging;
	}
	${gt(t,e)}
	`},"styles"),Ct={parser:it,db:f,renderer:pt,styles:mt};export{Ct as diagram};
