var Q=Object.defineProperty,Z=Object.defineProperties;var V=Object.getOwnPropertyDescriptors;var A=Object.getOwnPropertySymbols;var L=Object.prototype.hasOwnProperty,I=Object.prototype.propertyIsEnumerable;var P=(e,t,a)=>t in e?Q(e,t,{enumerable:!0,configurable:!0,writable:!0,value:a}):e[t]=a,x=(e,t)=>{for(var a in t||(t={}))L.call(t,a)&&P(e,a,t[a]);if(A)for(var a of A(t))I.call(t,a)&&P(e,a,t[a]);return e},C=(e,t)=>Z(e,V(t));var X=(e,t)=>{var a={};for(var n in e)L.call(e,n)&&t.indexOf(n)<0&&(a[n]=e[n]);if(e!=null&&A)for(var n of A(e))t.indexOf(n)<0&&I.call(e,n)&&(a[n]=e[n]);return a};import{_ as g,l as v,F as ee,z as H,q as te,W as re,e as ie,i as ne,c as ae}from"./index-BAopxCLJ.js";var D="",E="",W="",_=[],M=new Map,F=g(e=>ne(e,ae()),"sanitizeText"),$=g(e=>{switch(e.type){case"terminal":return C(x({},e),{value:F(e.value)});case"nonterminal":return C(x({},e),{name:F(e.name)});case"sequence":return C(x({},e),{elements:e.elements.map($)});case"choice":return C(x({},e),{alternatives:e.alternatives.map($)});case"optional":return C(x({},e),{element:$(e.element)});case"repetition":return C(x({},e),{element:$(e.element),separator:e.separator?$(e.separator):void 0});case"special":return C(x({},e),{text:F(e.text)})}},"sanitizeAstNode"),oe=g(()=>{D="",E="",W="",_.length=0,M.clear(),te(),v.debug("[Railroad] Database cleared")},"clear"),G=g(e=>{D=F(e),v.debug("[Railroad] Title set:",e)},"setTitle"),U=g(()=>D,"getTitle"),le=g(e=>{const t=C(x({},e),{name:F(e.name),definition:$(e.definition),comment:e.comment?F(e.comment):void 0});v.debug("[Railroad] Adding rule:",t.name),M.has(t.name)&&v.warn(`[Railroad] Rule '${t.name}' is already defined. Overwriting.`),_.push(t),M.set(t.name,t)},"addRule"),se=g(()=>_,"getRules"),de=g(e=>M.get(e),"getRule"),ce=g(e=>{E=F(e).replace(/^\s+/g,""),v.debug("[Railroad] Accessibility title set:",e)},"setAccTitle"),me=g(()=>E,"getAccTitle"),he=g(e=>{W=F(e).replace(/\n\s+/g,`
`),v.debug("[Railroad] Accessibility description set:",e)},"setAccDescription"),pe=g(()=>W,"getAccDescription"),ue=G,ge=U,fe={clear:oe,setTitle:G,getTitle:U,addRule:le,getRules:se,getRule:de,setAccTitle:ce,getAccTitle:me,setAccDescription:he,getAccDescription:pe,setDiagramTitle:ue,getDiagramTitle:ge},T={compactMode:!1,padding:10,verticalSeparation:8,horizontalSeparation:10,arcRadius:10,fontSize:14,fontFamily:"monospace",terminalFill:"#FFFFC0",terminalStroke:"#000000",terminalTextColor:"#000000",nonTerminalFill:"#FFFFFF",nonTerminalStroke:"#000000",nonTerminalTextColor:"#000000",lineColor:"#000000",strokeWidth:2,markerFill:"#000000",commentFill:"#E8E8E8",commentStroke:"#888888",commentTextColor:"#666666",specialFill:"#F0E0FF",specialStroke:"#8800CC",ruleNameColor:"#000066",showMarkers:!0,markerRadius:5},Te=/^#(?:[\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$|^(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch)\([\d\s%+,./-]+\)$|^[a-z]+$/i,xe=/^[\w "',.-]+$/,we=new Set(["compactMode","padding","verticalSeparation","horizontalSeparation","arcRadius","fontSize","fontFamily","terminalFill","terminalStroke","terminalTextColor","nonTerminalFill","nonTerminalStroke","nonTerminalTextColor","lineColor","strokeWidth","markerFill","commentFill","commentStroke","commentTextColor","specialFill","specialStroke","ruleNameColor","showMarkers","markerRadius"]),j=g(e=>e?Object.keys(e).every(t=>t==="railroad"||we.has(t)):!1,"isRailroadStyleOptions"),ke=g(e=>e?"railroad"in e&&e.railroad?e.railroad:j(e)?e:{}:{},"extractRailroadOverrides"),ve=g(e=>{if(!e||j(e))return{};const o=e,{railroad:t,svgId:a,theme:n,look:r}=o;return X(o,["railroad","svgId","theme","look"])},"extractThemeOverrides"),p=g((e,t)=>{if(typeof e!="string")return t;const a=e.trim();return Te.test(a)?a:t},"sanitizeColorValue"),K=g((e,t)=>{if(typeof e!="string")return t;const a=e.trim();return xe.test(a)?a:t},"sanitizeFontFamilyValue"),R=g((e,t)=>{const a=typeof e=="number"?e:typeof e=="string"?Number.parseFloat(e):Number.NaN;return Number.isFinite(a)&&a>=0?a:t},"sanitizeNumberValue"),Ce=g(e=>{const t=typeof e=="number"?e:typeof e=="string"?Number.parseFloat(e):Number.NaN;return Number.isFinite(t)&&t>0?t:void 0},"parseThemeFontSize"),Se=g(e=>{var n,r,i,o,c,l,s,h,u,m,w,d,f;const t=K(e.fontFamily,T.fontFamily),a=(n=Ce(e.fontSize))!=null?n:T.fontSize;return C(x({},T),{fontFamily:t,fontSize:a,terminalFill:p((r=e.secondBkg)!=null?r:e.secondaryColor,T.terminalFill),terminalStroke:p((i=e.secondaryBorderColor)!=null?i:e.lineColor,T.terminalStroke),terminalTextColor:p((o=e.secondaryTextColor)!=null?o:e.textColor,T.terminalTextColor),nonTerminalFill:p((c=e.mainBkg)!=null?c:e.background,T.nonTerminalFill),nonTerminalStroke:p((l=e.primaryBorderColor)!=null?l:e.lineColor,T.nonTerminalStroke),nonTerminalTextColor:p((s=e.primaryTextColor)!=null?s:e.textColor,T.nonTerminalTextColor),lineColor:p(e.lineColor,T.lineColor),markerFill:p(e.lineColor,T.markerFill),commentFill:p((h=e.labelBackground)!=null?h:e.tertiaryColor,T.commentFill),commentStroke:p((u=e.tertiaryBorderColor)!=null?u:e.lineColor,T.commentStroke),commentTextColor:p((m=e.tertiaryTextColor)!=null?m:e.textColor,T.commentTextColor),specialFill:p((w=e.tertiaryColor)!=null?w:e.secondaryColor,T.specialFill),specialStroke:p((d=e.tertiaryBorderColor)!=null?d:e.secondaryBorderColor,T.specialStroke),ruleNameColor:p((f=e.titleColor)!=null?f:e.textColor,T.ruleNameColor)})},"buildThemeDefaults"),B=g(e=>{var i,o,c,l;const t=H(),a=x(x(x({},re()),(i=t.themeVariables)!=null?i:{}),ve(e)),n=Se(a),r=x(x({},(o=t.railroad)!=null?o:{}),ke(e));return{compactMode:(c=r.compactMode)!=null?c:n.compactMode,padding:R(r.padding,n.padding),verticalSeparation:R(r.verticalSeparation,n.verticalSeparation),horizontalSeparation:R(r.horizontalSeparation,n.horizontalSeparation),arcRadius:R(r.arcRadius,n.arcRadius),fontSize:R(r.fontSize,n.fontSize),fontFamily:K(r.fontFamily,n.fontFamily),terminalFill:p(r.terminalFill,n.terminalFill),terminalStroke:p(r.terminalStroke,n.terminalStroke),terminalTextColor:p(r.terminalTextColor,n.terminalTextColor),nonTerminalFill:p(r.nonTerminalFill,n.nonTerminalFill),nonTerminalStroke:p(r.nonTerminalStroke,n.nonTerminalStroke),nonTerminalTextColor:p(r.nonTerminalTextColor,n.nonTerminalTextColor),lineColor:p(r.lineColor,n.lineColor),strokeWidth:R(r.strokeWidth,n.strokeWidth),markerFill:p(r.markerFill,n.markerFill),commentFill:p(r.commentFill,n.commentFill),commentStroke:p(r.commentStroke,n.commentStroke),commentTextColor:p(r.commentTextColor,n.commentTextColor),specialFill:p(r.specialFill,n.specialFill),specialStroke:p(r.specialStroke,n.specialStroke),ruleNameColor:p(r.ruleNameColor,n.ruleNameColor),showMarkers:(l=r.showMarkers)!=null?l:n.showMarkers,markerRadius:R(r.markerRadius,n.markerRadius)}},"buildRailroadStyleOptions"),ze=g(e=>{const{fontFamily:t,fontSize:a,terminalFill:n,terminalStroke:r,terminalTextColor:i,nonTerminalFill:o,nonTerminalStroke:c,nonTerminalTextColor:l,lineColor:s,strokeWidth:h,markerFill:u,commentFill:m,commentStroke:w,commentTextColor:d,specialFill:f,specialStroke:N,ruleNameColor:y}=B(e);return`
  .railroad-diagram {
    font-family: ${t};
    font-size: ${a}px;
  }

  .railroad-terminal rect {
    fill: ${n};
    stroke: ${r};
    stroke-width: ${h}px;
  }

  .railroad-terminal text {
    fill: ${i};
    font-family: ${t};
    font-size: ${a}px;
    text-anchor: middle;
    dominant-baseline: middle;
  }

  .railroad-nonterminal rect {
    fill: ${o};
    stroke: ${c};
    stroke-width: ${h}px;
  }

  .railroad-nonterminal text {
    fill: ${l};
    font-family: ${t};
    font-size: ${a}px;
    text-anchor: middle;
    dominant-baseline: middle;
  }

  .railroad-line {
    stroke: ${s};
    stroke-width: ${h}px;
    fill: none;
  }

  .railroad-start circle,
  .railroad-end circle {
    fill: ${u};
  }

  .railroad-comment ellipse {
    fill: ${m};
    stroke: ${w};
    stroke-width: ${h}px;
  }

  .railroad-comment text {
    fill: ${d};
    font-style: italic;
    font-family: ${t};
    font-size: ${a}px;
    text-anchor: middle;
    dominant-baseline: middle;
  }

  .railroad-special rect {
    fill: ${f};
    stroke: ${N};
    stroke-width: ${h}px;
    stroke-dasharray: 5,3;
  }

  .railroad-special text {
    fill: ${l};
    font-family: ${t};
    font-size: ${a}px;
    text-anchor: middle;
    dominant-baseline: middle;
  }

  .railroad-rule-name {
    font-weight: bold;
    fill: ${y};
    font-family: ${t};
    font-size: ${a}px;
  }

  .railroad-group {
    /* Grouping container, no specific styles */
  }
`},"getStyles"),z,k=(z=class{constructor(){this.d=""}moveTo(t,a){return this.d+=`M ${t} ${a} `,this}lineTo(t,a){return this.d+=`L ${t} ${a} `,this}horizontalTo(t){return this.d+=`H ${t} `,this}verticalTo(t){return this.d+=`V ${t} `,this}arcTo(t,a,n,r,i,o,c){return this.d+=`A ${t} ${a} ${n} ${r?1:0} ${i?1:0} ${o} ${c} `,this}build(){return this.d.trim()}},g(z,"PathBuilder"),z),b,Fe=(b=class{constructor(t,a=B()){this.textCache=new Map,this.svg=t,this.config=a}measureText(t){if(this.textCache.has(t))return this.textCache.get(t);const a=this.svg.append("text").attr("font-family",this.config.fontFamily).attr("font-size",this.config.fontSize).text(t),n=a.node().getBBox(),r={width:n.width,height:n.height};return a.remove(),this.textCache.set(t,r),r}renderTerminal(t,a){const n=this.measureText(a),r=n.width+this.config.padding*2,i=n.height+this.config.padding*2,o=t.append("g").attr("class","railroad-terminal");return o.append("rect").attr("x",0).attr("y",0).attr("width",r).attr("height",i).attr("rx",10).attr("ry",10),o.append("text").attr("x",r/2).attr("y",i/2).text(a),{element:o.node(),dimensions:{width:r,height:i,up:i/2,down:i/2}}}renderNonTerminal(t,a){const n=this.measureText(a),r=n.width+this.config.padding*2,i=n.height+this.config.padding*2,o=t.append("g").attr("class","railroad-nonterminal");return o.append("rect").attr("x",0).attr("y",0).attr("width",r).attr("height",i),o.append("text").attr("x",r/2).attr("y",i/2).text(a),{element:o.node(),dimensions:{width:r,height:i,up:i/2,down:i/2}}}renderSequence(t,a){const n=a.map(s=>this.renderExpression(t,s));let r=0,i=0,o=0;for(const s of n)r+=s.dimensions.width,i=Math.max(i,s.dimensions.up),o=Math.max(o,s.dimensions.down);r+=(n.length-1)*this.config.horizontalSeparation;const c=t.append("g").attr("class","railroad-sequence");let l=0;for(let s=0;s<n.length;s++){const h=n[s],u=i-h.dimensions.up;if(c.node().appendChild(h.element).setAttribute("transform",`translate(${l}, ${u})`),s<n.length-1){const w=l+h.dimensions.width,d=w+this.config.horizontalSeparation,f=i;c.append("path").attr("class","railroad-line").attr("d",new k().moveTo(w,f).lineTo(d,f).build())}l+=h.dimensions.width+this.config.horizontalSeparation}return{element:c.node(),dimensions:{width:r,height:i+o,up:i,down:o}}}renderChoice(t,a){const n=a.map(m=>this.renderExpression(t,m));let r=0,i=0;for(const m of n)r=Math.max(r,m.dimensions.width),i+=m.dimensions.height;i+=(n.length-1)*this.config.verticalSeparation;const o=this.config.arcRadius,c=o*4,l=r+c,s=t.append("g").attr("class","railroad-choice");let h=0;const u=i/2;for(const m of n){const w=h,d=w+m.dimensions.up,f=o*2+(r-m.dimensions.width)/2;s.node().appendChild(m.element).setAttribute("transform",`translate(${f}, ${w})`);const y=new k,S=d>u;d===u?y.moveTo(0,u).lineTo(f,d):y.moveTo(0,u).arcTo(o,o,0,!1,S,o,u+(S?o:-o)).lineTo(o,d-(S?o:-o)).arcTo(o,o,0,!1,!S,o*2,d).lineTo(f,d),s.append("path").attr("class","railroad-line").attr("d",y.build());const O=new k,Y=f+m.dimensions.width,J=l-o*2;d===u?O.moveTo(Y,d).lineTo(l,u):O.moveTo(Y,d).lineTo(J,d).arcTo(o,o,0,!1,!S,l-o,d+(S?-o:o)).lineTo(l-o,u+(S?o:-o)).arcTo(o,o,0,!1,S,l,u),s.append("path").attr("class","railroad-line").attr("d",O.build()),h+=m.dimensions.height+this.config.verticalSeparation}return{element:s.node(),dimensions:{width:l,height:i,up:u,down:i-u}}}renderOptional(t,a){const n=this.renderExpression(t,a),r=this.config.arcRadius,i=r*2,o=n.dimensions.width+r*4,c=n.dimensions.height+i,l=t.append("g").attr("class","railroad-optional"),s=r*2,h=i;l.node().appendChild(n.element).setAttribute("transform",`translate(${s}, ${h})`);const m=h+n.dimensions.up,w=new k().moveTo(0,m).lineTo(r*2,m);l.append("path").attr("class","railroad-line").attr("d",w.build());const d=new k().moveTo(s+n.dimensions.width,m).lineTo(o,m);l.append("path").attr("class","railroad-line").attr("d",d.build());const f=new k().moveTo(0,m).arcTo(r,r,0,!1,!1,r,m-r).lineTo(r,r).arcTo(r,r,0,!1,!0,r*2,0).lineTo(o-r*2,0).arcTo(r,r,0,!1,!0,o-r,r).lineTo(o-r,m-r).arcTo(r,r,0,!1,!1,o,m);return l.append("path").attr("class","railroad-line").attr("d",f.build()),{element:l.node(),dimensions:{width:o,height:c,up:m,down:c-m}}}renderRepetition(t,a,n){const r=this.renderExpression(t,a),i=this.config.arcRadius,o=i*2,c=r.dimensions.width+i*4,l=n===0,s=r.dimensions.height+o+(l?o:0),h=t.append("g").attr("class","railroad-repetition"),u=i*2,m=l?o:0;h.node().appendChild(r.element).setAttribute("transform",`translate(${u}, ${m})`);const d=m+r.dimensions.up;h.append("path").attr("class","railroad-line").attr("d",new k().moveTo(0,d).lineTo(i*2,d).build()),h.append("path").attr("class","railroad-line").attr("d",new k().moveTo(u+r.dimensions.width,d).lineTo(c,d).build());const f=m+r.dimensions.height+i,N=new k().moveTo(u+r.dimensions.width,d).arcTo(i,i,0,!1,!0,u+r.dimensions.width+i,d+i).lineTo(u+r.dimensions.width+i,f).arcTo(i,i,0,!1,!0,u+r.dimensions.width,f+i).lineTo(i*2,f+i).arcTo(i,i,0,!1,!0,i,f).lineTo(i,d+i).arcTo(i,i,0,!1,!0,i*2,d);if(h.append("path").attr("class","railroad-line").attr("d",N.build()),l){const y=new k().moveTo(0,d).arcTo(i,i,0,!1,!1,i,d-i).lineTo(i,i).arcTo(i,i,0,!1,!0,i*2,0).lineTo(c-i*2,0).arcTo(i,i,0,!1,!0,c-i,i).lineTo(c-i,d-i).arcTo(i,i,0,!1,!1,c,d);h.append("path").attr("class","railroad-line").attr("d",y.build())}return{element:h.node(),dimensions:{width:c,height:s,up:d,down:s-d}}}renderSpecial(t,a){const n=this.measureText("? "+a+" ?"),r=n.width+this.config.padding*2,i=n.height+this.config.padding*2,o=t.append("g").attr("class","railroad-special");return o.append("rect").attr("x",0).attr("y",0).attr("width",r).attr("height",i),o.append("text").attr("x",r/2).attr("y",i/2).text("? "+a+" ?"),{element:o.node(),dimensions:{width:r,height:i,up:i/2,down:i/2}}}renderExpression(t,a){switch(a.type){case"terminal":return this.renderTerminal(t,a.value);case"nonterminal":return this.renderNonTerminal(t,a.name);case"sequence":return this.renderSequence(t,a.elements);case"choice":return this.renderChoice(t,a.alternatives);case"optional":return this.renderOptional(t,a.element);case"repetition":return this.renderRepetition(t,a.element,a.min);case"special":return this.renderSpecial(t,a.text);default:throw new Error(`Unknown node type: ${a.type}`)}}renderRule(t,a){const n=this.svg.append("g").attr("class","railroad-rule").attr("transform",`translate(0, ${a})`),r=t.name+" =",i=this.measureText(r).width+20,o=i+20,c=n.append("g"),l=this.renderExpression(c,t.definition),s=Math.max(20,l.dimensions.up),h=s-l.dimensions.up;return c.attr("transform",`translate(${o}, ${h})`),n.append("g").attr("class","railroad-rule-name-group").append("text").attr("class","railroad-rule-name").attr("x",0).attr("y",s).text(r),n.append("g").attr("class","railroad-start").append("circle").attr("cx",i).attr("cy",s).attr("r",this.config.markerRadius),n.append("g").attr("class","railroad-end").append("circle").attr("cx",o+l.dimensions.width+10).attr("cy",s).attr("r",this.config.markerRadius),n.append("path").attr("class","railroad-line").attr("d",new k().moveTo(i+this.config.markerRadius,s).lineTo(o,s).build()),n.append("path").attr("class","railroad-line").attr("d",new k().moveTo(o+l.dimensions.width,s).lineTo(o+l.dimensions.width+10-this.config.markerRadius,s).build()),{height:Math.max(40,h+l.dimensions.height+this.config.padding*2),width:o+l.dimensions.width+10+this.config.markerRadius}}renderDiagram(t){let a=this.config.padding,n=0;for(const r of t){const i=this.renderRule(r,a);a+=i.height+this.config.verticalSeparation,n=Math.max(n,i.width)}return{width:n+this.config.padding*2,height:a+this.config.padding}}},g(b,"RailroadRenderer"),b),q=g((e,t,a)=>{ie(e,t.height,t.width,a),e.attr("viewBox",`0 0 ${t.width} ${t.height}`)},"configureRailroadSvgSize"),ye=g((e,t,a)=>{var n;v.debug(`[Railroad] Rendering diagram
`+e);try{const r=ee(t);r.attr("class","railroad-diagram");const i=H().railroad,o=(n=i==null?void 0:i.useMaxWidth)!=null?n:!0,c=fe.getRules();if(v.debug(`[Railroad] Rendering ${c.length} rules`),c.length===0){v.warn("[Railroad] No rules to render"),q(r,{height:100,width:200},o);return}const s=new Fe(r,B()).renderDiagram(c);q(r,s,o),v.debug("[Railroad] Render complete")}catch(r){throw v.error("[Railroad] Render error:",r),r}},"draw"),be={draw:ye};export{fe as d,ze as g,be as r};
