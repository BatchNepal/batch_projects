var Rt=(t,e,s)=>new Promise((a,i)=>{var o=h=>{try{d(s.next(h))}catch(g){i(g)}},c=h=>{try{d(s.throw(h))}catch(g){i(g)}},d=h=>h.done?a(h.value):Promise.resolve(h.value).then(o,c);d((s=s.apply(t,e)).next())});import{g as se}from"./chunk-XXDRQBXY-CS-jZRcH.js";import{s as ie}from"./chunk-VR4S4FIN-B1WdAQcT.js";import{_ as S,l as b,c as P,x as re,y as ae,a as ne,b as oe,g as le,s as ce,o as he,p as ue,a9 as de,k as X,q as fe,d as Dt,a5 as pe}from"./index-BAopxCLJ.js";import{f as Se}from"./chunk-32BRIVSS-DjCiUmD-.js";var Ct=function(){var t=S(function(W,l,f,n){for(f=f||{},n=W.length;n--;f[W[n]]=l);return f},"o"),e=[1,2],s=[1,3],a=[1,4],i=[2,4],o=[1,9],c=[1,11],d=[1,16],h=[1,17],g=[1,18],E=[1,19],m=[1,33],$=[1,20],B=[1,21],I=[1,22],C=[1,23],v=[1,24],p=[1,26],A=[1,27],D=[1,28],Y=[1,29],w=[1,30],G=[1,31],F=[1,32],O=[1,35],q=[1,36],H=[1,37],lt=[1,38],Q=[1,34],y=[1,4,5,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],ct=[1,4,5,14,15,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,39,40,41,45,48,51,52,53,54,57],Lt=[4,5,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],gt={trace:S(function(){},"trace"),yy:{},symbols_:{error:2,start:3,SPACE:4,NL:5,SD:6,document:7,line:8,statement:9,classDefStatement:10,styleStatement:11,cssClassStatement:12,idStatement:13,DESCR:14,"-->":15,HIDE_EMPTY:16,scale:17,WIDTH:18,COMPOSIT_STATE:19,STRUCT_START:20,STRUCT_STOP:21,STATE_DESCR:22,AS:23,ID:24,FORK:25,JOIN:26,CHOICE:27,CONCURRENT:28,note:29,notePosition:30,NOTE_TEXT:31,direction:32,acc_title:33,acc_title_value:34,acc_descr:35,acc_descr_value:36,acc_descr_multiline_value:37,CLICK:38,STRING:39,HREF:40,classDef:41,CLASSDEF_ID:42,CLASSDEF_STYLEOPTS:43,DEFAULT:44,style:45,STYLE_IDS:46,STYLEDEF_STYLEOPTS:47,class:48,CLASSENTITY_IDS:49,STYLECLASS:50,direction_tb:51,direction_bt:52,direction_rl:53,direction_lr:54,eol:55,";":56,EDGE_STATE:57,STYLE_SEPARATOR:58,left_of:59,right_of:60,$accept:0,$end:1},terminals_:{2:"error",4:"SPACE",5:"NL",6:"SD",14:"DESCR",15:"-->",16:"HIDE_EMPTY",17:"scale",18:"WIDTH",19:"COMPOSIT_STATE",20:"STRUCT_START",21:"STRUCT_STOP",22:"STATE_DESCR",23:"AS",24:"ID",25:"FORK",26:"JOIN",27:"CHOICE",28:"CONCURRENT",29:"note",31:"NOTE_TEXT",33:"acc_title",34:"acc_title_value",35:"acc_descr",36:"acc_descr_value",37:"acc_descr_multiline_value",38:"CLICK",39:"STRING",40:"HREF",41:"classDef",42:"CLASSDEF_ID",43:"CLASSDEF_STYLEOPTS",44:"DEFAULT",45:"style",46:"STYLE_IDS",47:"STYLEDEF_STYLEOPTS",48:"class",49:"CLASSENTITY_IDS",50:"STYLECLASS",51:"direction_tb",52:"direction_bt",53:"direction_rl",54:"direction_lr",56:";",57:"EDGE_STATE",58:"STYLE_SEPARATOR",59:"left_of",60:"right_of"},productions_:[0,[3,2],[3,2],[3,2],[7,0],[7,2],[8,2],[8,1],[8,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,3],[9,4],[9,1],[9,2],[9,1],[9,4],[9,3],[9,6],[9,1],[9,1],[9,1],[9,1],[9,4],[9,4],[9,1],[9,2],[9,2],[9,1],[9,5],[9,5],[10,3],[10,3],[11,3],[12,3],[32,1],[32,1],[32,1],[32,1],[55,1],[55,1],[13,1],[13,1],[13,3],[13,3],[30,1],[30,1]],performAction:S(function(l,f,n,T,_,r,V){var u=r.length-1;switch(_){case 3:return T.setRootDoc(r[u]),r[u];case 4:this.$=[];break;case 5:r[u]!="nl"&&(r[u-1].push(r[u]),this.$=r[u-1]);break;case 6:case 7:this.$=r[u];break;case 8:this.$="nl";break;case 12:this.$=r[u];break;case 13:const it=r[u-1];it.description=T.trimColon(r[u]),this.$=it;break;case 14:this.$={stmt:"relation",state1:r[u-2],state2:r[u]};break;case 15:const Tt=T.trimColon(r[u]);this.$={stmt:"relation",state1:r[u-3],state2:r[u-1],description:Tt};break;case 19:this.$={stmt:"state",id:r[u-3],type:"default",description:"",doc:r[u-1]};break;case 20:var M=r[u],Z=r[u-2].trim();if(r[u].match(":")){var ut=r[u].split(":");M=ut[0],Z=[Z,ut[1]]}this.$={stmt:"state",id:M,type:"default",description:Z};break;case 21:this.$={stmt:"state",id:r[u-3],type:"default",description:r[u-5],doc:r[u-1]};break;case 22:this.$={stmt:"state",id:r[u],type:"fork"};break;case 23:this.$={stmt:"state",id:r[u],type:"join"};break;case 24:this.$={stmt:"state",id:r[u],type:"choice"};break;case 25:this.$={stmt:"state",id:T.getDividerId(),type:"divider"};break;case 26:this.$={stmt:"state",id:r[u-1].trim(),note:{position:r[u-2].trim(),text:r[u].trim()}};break;case 29:this.$=r[u].trim(),T.setAccTitle(this.$);break;case 30:case 31:this.$=r[u].trim(),T.setAccDescription(this.$);break;case 32:this.$={stmt:"click",id:r[u-3],url:r[u-2],tooltip:r[u-1]};break;case 33:this.$={stmt:"click",id:r[u-3],url:r[u-1],tooltip:""};break;case 34:case 35:this.$={stmt:"classDef",id:r[u-1].trim(),classes:r[u].trim()};break;case 36:this.$={stmt:"style",id:r[u-1].trim(),styleClass:r[u].trim()};break;case 37:this.$={stmt:"applyClass",id:r[u-1].trim(),styleClass:r[u].trim()};break;case 38:T.setDirection("TB"),this.$={stmt:"dir",value:"TB"};break;case 39:T.setDirection("BT"),this.$={stmt:"dir",value:"BT"};break;case 40:T.setDirection("RL"),this.$={stmt:"dir",value:"RL"};break;case 41:T.setDirection("LR"),this.$={stmt:"dir",value:"LR"};break;case 44:case 45:this.$={stmt:"state",id:r[u].trim(),type:"default",description:""};break;case 46:this.$={stmt:"state",id:r[u-2].trim(),classes:[r[u].trim()],type:"default",description:""};break;case 47:this.$={stmt:"state",id:r[u-2].trim(),classes:[r[u].trim()],type:"default",description:""};break}},"anonymous"),table:[{3:1,4:e,5:s,6:a},{1:[3]},{3:5,4:e,5:s,6:a},{3:6,4:e,5:s,6:a},t([1,4,5,16,17,19,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],i,{7:7}),{1:[2,1]},{1:[2,2]},{1:[2,3],4:o,5:c,8:8,9:10,10:12,11:13,12:14,13:15,16:d,17:h,19:g,22:E,24:m,25:$,26:B,27:I,28:C,29:v,32:25,33:p,35:A,37:D,38:Y,41:w,45:G,48:F,51:O,52:q,53:H,54:lt,57:Q},t(y,[2,5]),{9:39,10:12,11:13,12:14,13:15,16:d,17:h,19:g,22:E,24:m,25:$,26:B,27:I,28:C,29:v,32:25,33:p,35:A,37:D,38:Y,41:w,45:G,48:F,51:O,52:q,53:H,54:lt,57:Q},t(y,[2,7]),t(y,[2,8]),t(y,[2,9]),t(y,[2,10]),t(y,[2,11]),t(y,[2,12],{14:[1,40],15:[1,41]}),t(y,[2,16]),{18:[1,42]},t(y,[2,18],{20:[1,43]}),{23:[1,44]},t(y,[2,22]),t(y,[2,23]),t(y,[2,24]),t(y,[2,25]),{30:45,31:[1,46],59:[1,47],60:[1,48]},t(y,[2,28]),{34:[1,49]},{36:[1,50]},t(y,[2,31]),{13:51,24:m,57:Q},{42:[1,52],44:[1,53]},{46:[1,54]},{49:[1,55]},t(ct,[2,44],{58:[1,56]}),t(ct,[2,45],{58:[1,57]}),t(y,[2,38]),t(y,[2,39]),t(y,[2,40]),t(y,[2,41]),t(y,[2,6]),t(y,[2,13]),{13:58,24:m,57:Q},t(y,[2,17]),t(Lt,i,{7:59}),{24:[1,60]},{24:[1,61]},{23:[1,62]},{24:[2,48]},{24:[2,49]},t(y,[2,29]),t(y,[2,30]),{39:[1,63],40:[1,64]},{43:[1,65]},{43:[1,66]},{47:[1,67]},{50:[1,68]},{24:[1,69]},{24:[1,70]},t(y,[2,14],{14:[1,71]}),{4:o,5:c,8:8,9:10,10:12,11:13,12:14,13:15,16:d,17:h,19:g,21:[1,72],22:E,24:m,25:$,26:B,27:I,28:C,29:v,32:25,33:p,35:A,37:D,38:Y,41:w,45:G,48:F,51:O,52:q,53:H,54:lt,57:Q},t(y,[2,20],{20:[1,73]}),{31:[1,74]},{24:[1,75]},{39:[1,76]},{39:[1,77]},t(y,[2,34]),t(y,[2,35]),t(y,[2,36]),t(y,[2,37]),t(ct,[2,46]),t(ct,[2,47]),t(y,[2,15]),t(y,[2,19]),t(Lt,i,{7:78}),t(y,[2,26]),t(y,[2,27]),{5:[1,79]},{5:[1,80]},{4:o,5:c,8:8,9:10,10:12,11:13,12:14,13:15,16:d,17:h,19:g,21:[1,81],22:E,24:m,25:$,26:B,27:I,28:C,29:v,32:25,33:p,35:A,37:D,38:Y,41:w,45:G,48:F,51:O,52:q,53:H,54:lt,57:Q},t(y,[2,32]),t(y,[2,33]),t(y,[2,21])],defaultActions:{5:[2,1],6:[2,2],47:[2,48],48:[2,49]},parseError:S(function(l,f){if(f.recoverable)this.trace(l);else{var n=new Error(l);throw n.hash=f,n}},"parseError"),parse:S(function(l){var f=this,n=[0],T=[],_=[null],r=[],V=this.table,u="",M=0,Z=0,ut=2,it=1,Tt=r.slice.call(arguments,1),k=Object.create(this.lexer),z={yy:{}};for(var Et in this.yy)Object.prototype.hasOwnProperty.call(this.yy,Et)&&(z.yy[Et]=this.yy[Et]);k.setInput(l,z.yy),z.yy.lexer=k,z.yy.parser=this,typeof k.yylloc=="undefined"&&(k.yylloc={});var _t=k.yylloc;r.push(_t);var te=k.options&&k.options.ranges;typeof z.yy.parseError=="function"?this.parseError=z.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function ee(R){n.length=n.length-2*R,_.length=_.length-R,r.length=r.length-R}S(ee,"popStack");function wt(){var R;return R=T.pop()||k.lex()||it,typeof R!="number"&&(R instanceof Array&&(T=R,R=T.pop()),R=f.symbols_[R]||R),R}S(wt,"lex");for(var L,K,N,mt,tt={},dt,U,Ot,ft;;){if(K=n[n.length-1],this.defaultActions[K]?N=this.defaultActions[K]:((L===null||typeof L=="undefined")&&(L=wt()),N=V[K]&&V[K][L]),typeof N=="undefined"||!N.length||!N[0]){var bt="";ft=[];for(dt in V[K])this.terminals_[dt]&&dt>ut&&ft.push("'"+this.terminals_[dt]+"'");k.showPosition?bt="Parse error on line "+(M+1)+`:
`+k.showPosition()+`
Expecting `+ft.join(", ")+", got '"+(this.terminals_[L]||L)+"'":bt="Parse error on line "+(M+1)+": Unexpected "+(L==it?"end of input":"'"+(this.terminals_[L]||L)+"'"),this.parseError(bt,{text:k.match,token:this.terminals_[L]||L,line:k.yylineno,loc:_t,expected:ft})}if(N[0]instanceof Array&&N.length>1)throw new Error("Parse Error: multiple actions possible at state: "+K+", token: "+L);switch(N[0]){case 1:n.push(L),_.push(k.yytext),r.push(k.yylloc),n.push(N[1]),L=null,Z=k.yyleng,u=k.yytext,M=k.yylineno,_t=k.yylloc;break;case 2:if(U=this.productions_[N[1]][1],tt.$=_[_.length-U],tt._$={first_line:r[r.length-(U||1)].first_line,last_line:r[r.length-1].last_line,first_column:r[r.length-(U||1)].first_column,last_column:r[r.length-1].last_column},te&&(tt._$.range=[r[r.length-(U||1)].range[0],r[r.length-1].range[1]]),mt=this.performAction.apply(tt,[u,Z,M,z.yy,N[1],_,r].concat(Tt)),typeof mt!="undefined")return mt;U&&(n=n.slice(0,-1*U*2),_=_.slice(0,-1*U),r=r.slice(0,-1*U)),n.push(this.productions_[N[1]][0]),_.push(tt.$),r.push(tt._$),Ot=V[n[n.length-2]][n[n.length-1]],n.push(Ot);break;case 3:return!0}}return!0},"parse")},Zt=function(){var W={EOF:1,parseError:S(function(f,n){if(this.yy.parser)this.yy.parser.parseError(f,n);else throw new Error(f)},"parseError"),setInput:S(function(l,f){return this.yy=f||this.yy||{},this._input=l,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:S(function(){var l=this._input[0];this.yytext+=l,this.yyleng++,this.offset++,this.match+=l,this.matched+=l;var f=l.match(/(?:\r\n?|\n).*/g);return f?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),l},"input"),unput:S(function(l){var f=l.length,n=l.split(/(?:\r\n?|\n)/g);this._input=l+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-f),this.offset-=f;var T=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),n.length-1&&(this.yylineno-=n.length-1);var _=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:n?(n.length===T.length?this.yylloc.first_column:0)+T[T.length-n.length].length-n[0].length:this.yylloc.first_column-f},this.options.ranges&&(this.yylloc.range=[_[0],_[0]+this.yyleng-f]),this.yyleng=this.yytext.length,this},"unput"),more:S(function(){return this._more=!0,this},"more"),reject:S(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},"reject"),less:S(function(l){this.unput(this.match.slice(l))},"less"),pastInput:S(function(){var l=this.matched.substr(0,this.matched.length-this.match.length);return(l.length>20?"...":"")+l.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:S(function(){var l=this.match;return l.length<20&&(l+=this._input.substr(0,20-l.length)),(l.substr(0,20)+(l.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:S(function(){var l=this.pastInput(),f=new Array(l.length+1).join("-");return l+this.upcomingInput()+`
`+f+"^"},"showPosition"),test_match:S(function(l,f){var n,T,_;if(this.options.backtrack_lexer&&(_={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(_.yylloc.range=this.yylloc.range.slice(0))),T=l[0].match(/(?:\r\n?|\n).*/g),T&&(this.yylineno+=T.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:T?T[T.length-1].length-T[T.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+l[0].length},this.yytext+=l[0],this.match+=l[0],this.matches=l,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(l[0].length),this.matched+=l[0],n=this.performAction.call(this,this.yy,this,f,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),n)return n;if(this._backtrack){for(var r in _)this[r]=_[r];return!1}return!1},"test_match"),next:S(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var l,f,n,T;this._more||(this.yytext="",this.match="");for(var _=this._currentRules(),r=0;r<_.length;r++)if(n=this._input.match(this.rules[_[r]]),n&&(!f||n[0].length>f[0].length)){if(f=n,T=r,this.options.backtrack_lexer){if(l=this.test_match(n,_[r]),l!==!1)return l;if(this._backtrack){f=!1;continue}else return!1}else if(!this.options.flex)break}return f?(l=this.test_match(f,_[T]),l!==!1?l:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:S(function(){var f=this.next();return f||this.lex()},"lex"),begin:S(function(f){this.conditionStack.push(f)},"begin"),popState:S(function(){var f=this.conditionStack.length-1;return f>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),_currentRules:S(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),topState:S(function(f){return f=this.conditionStack.length-1-Math.abs(f||0),f>=0?this.conditionStack[f]:"INITIAL"},"topState"),pushState:S(function(f){this.begin(f)},"pushState"),stateStackSize:S(function(){return this.conditionStack.length},"stateStackSize"),options:{"case-insensitive":!0},performAction:S(function(f,n,T,_){function r(){const V=n.yytext.indexOf("%%");if(V===0)return!1;if(V>0){const u=n.yytext.slice(0,V),M=n.yytext.slice(V);M&&f.lexer.unput(M),n.yytext=u}return!0}switch(S(r,"processId"),T){case 0:return 38;case 1:return 40;case 2:return 39;case 3:return 44;case 4:return 51;case 5:return 52;case 6:return 53;case 7:return 54;case 8:return 5;case 9:break;case 10:break;case 11:break;case 12:break;case 13:return this.pushState("SCALE"),17;case 14:return 18;case 15:this.popState();break;case 16:return this.begin("acc_title"),33;case 17:return this.popState(),"acc_title_value";case 18:return this.begin("acc_descr"),35;case 19:return this.popState(),"acc_descr_value";case 20:this.begin("acc_descr_multiline");break;case 21:this.popState();break;case 22:return"acc_descr_multiline_value";case 23:return this.pushState("CLASSDEF"),41;case 24:return this.popState(),this.pushState("CLASSDEFID"),"DEFAULT_CLASSDEF_ID";case 25:return this.popState(),this.pushState("CLASSDEFID"),42;case 26:return this.popState(),43;case 27:return this.pushState("CLASS"),48;case 28:return this.popState(),this.pushState("CLASS_STYLE"),49;case 29:return this.popState(),50;case 30:return this.pushState("STYLE"),45;case 31:return this.popState(),this.pushState("STYLEDEF_STYLES"),46;case 32:return this.popState(),47;case 33:return this.pushState("SCALE"),17;case 34:return 18;case 35:this.popState();break;case 36:this.pushState("STATE");break;case 37:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),25;case 38:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),26;case 39:return this.popState(),n.yytext=n.yytext.slice(0,-10).trim(),27;case 40:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),25;case 41:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),26;case 42:return this.popState(),n.yytext=n.yytext.slice(0,-10).trim(),27;case 43:return 51;case 44:return 52;case 45:return 53;case 46:return 54;case 47:this.pushState("STATE_STRING");break;case 48:return this.pushState("STATE_ID"),"AS";case 49:return r()?(this.popState(),"ID"):void 0;case 50:this.popState();break;case 51:return"STATE_DESCR";case 52:throw new Error('Error: State name must be a single word. Found: "'+n.yytext.trim()+'"');case 53:return 19;case 54:this.popState();break;case 55:return this.popState(),this.pushState("struct"),20;case 56:return this.popState(),21;case 57:break;case 58:return this.begin("NOTE"),29;case 59:return this.popState(),this.pushState("NOTE_ID"),59;case 60:return this.popState(),this.pushState("NOTE_ID"),60;case 61:this.popState(),this.pushState("FLOATING_NOTE");break;case 62:return this.popState(),this.pushState("FLOATING_NOTE_ID"),"AS";case 63:break;case 64:return"NOTE_TEXT";case 65:return r()?(this.popState(),"ID"):void 0;case 66:return r()?(this.popState(),this.pushState("NOTE_TEXT"),24):void 0;case 67:return this.popState(),n.yytext=n.yytext.substr(2).trim(),31;case 68:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),31;case 69:return 6;case 70:return 6;case 71:return 16;case 72:return 57;case 73:return r()?24:void 0;case 74:return n.yytext=n.yytext.trim(),14;case 75:return 15;case 76:return 28;case 77:return 58;case 78:return 5;case 79:return"INVALID"}},"anonymous"),rules:[/^(?:click\b)/i,/^(?:href\b)/i,/^(?:"[^"]*")/i,/^(?:default\b)/i,/^(?:.*direction\s+TB[^\n]*)/i,/^(?:.*direction\s+BT[^\n]*)/i,/^(?:.*direction\s+RL[^\n]*)/i,/^(?:.*direction\s+LR[^\n]*)/i,/^(?:[\n]+)/i,/^(?:[\s]+)/i,/^(?:((?!\n)\s)+)/i,/^(?:#[^\n]*)/i,/^(?:%%(?!\{)[^\n]*)/i,/^(?:scale\s+)/i,/^(?:\d+)/i,/^(?:\s+width\b)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:classDef\s+)/i,/^(?:DEFAULT\s+)/i,/^(?:\w+\s+)/i,/^(?:[^\n]*)/i,/^(?:class\s+)/i,/^(?:(\w+)+((,\s*\w+)*))/i,/^(?:[^\n]*)/i,/^(?:style\s+)/i,/^(?:[\w,]+\s+)/i,/^(?:[^\n]*)/i,/^(?:scale\s+)/i,/^(?:\d+)/i,/^(?:\s+width\b)/i,/^(?:state\s+)/i,/^(?:.*<<fork>>)/i,/^(?:.*<<join>>)/i,/^(?:.*<<choice>>)/i,/^(?:.*\[\[fork\]\])/i,/^(?:.*\[\[join\]\])/i,/^(?:.*\[\[choice\]\])/i,/^(?:.*direction\s+TB[^\n]*)/i,/^(?:.*direction\s+BT[^\n]*)/i,/^(?:.*direction\s+RL[^\n]*)/i,/^(?:.*direction\s+LR[^\n]*)/i,/^(?:["])/i,/^(?:\s*as\s+)/i,/^(?:[^\n\{]*)/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:\w+\s+\w+.*?\{)/i,/^(?:[^\n\s\{]+)/i,/^(?:\n)/i,/^(?:\{)/i,/^(?:\})/i,/^(?:[\n])/i,/^(?:note\s+)/i,/^(?:left of\b)/i,/^(?:right of\b)/i,/^(?:")/i,/^(?:\s*as\s*)/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:[^\n]*)/i,/^(?:\s*[^:\n\s\-]+)/i,/^(?:\s*:[^:\n;]+)/i,/^(?:[\s\S]*?\n\s*end note\b)/i,/^(?:stateDiagram\s+)/i,/^(?:stateDiagram-v2\s+)/i,/^(?:hide empty description\b)/i,/^(?:\[\*\])/i,/^(?:[^:\n\s\-\{]+)/i,/^(?:\s*:(?:[^:\n;]|:[^:\n;])+)/i,/^(?:-->)/i,/^(?:--)/i,/^(?::::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{LINE:{rules:[10,11,12],inclusive:!1},struct:{rules:[10,11,12,23,27,30,36,43,44,45,46,56,57,58,72,73,74,75,76,77],inclusive:!1},FLOATING_NOTE_ID:{rules:[65],inclusive:!1},FLOATING_NOTE:{rules:[62,63,64],inclusive:!1},NOTE_TEXT:{rules:[67,68],inclusive:!1},NOTE_ID:{rules:[66],inclusive:!1},NOTE:{rules:[59,60,61],inclusive:!1},STYLEDEF_STYLEOPTS:{rules:[],inclusive:!1},STYLEDEF_STYLES:{rules:[32],inclusive:!1},STYLE_IDS:{rules:[],inclusive:!1},STYLE:{rules:[31],inclusive:!1},CLASS_STYLE:{rules:[29],inclusive:!1},CLASS:{rules:[28],inclusive:!1},CLASSDEFID:{rules:[26],inclusive:!1},CLASSDEF:{rules:[24,25],inclusive:!1},acc_descr_multiline:{rules:[21,22],inclusive:!1},acc_descr:{rules:[19],inclusive:!1},acc_title:{rules:[17],inclusive:!1},SCALE:{rules:[14,15,34,35],inclusive:!1},ALIAS:{rules:[],inclusive:!1},STATE_ID:{rules:[49],inclusive:!1},STATE_STRING:{rules:[50,51],inclusive:!1},FORK_STATE:{rules:[],inclusive:!1},STATE:{rules:[10,11,12,37,38,39,40,41,42,47,48,52,53,54,55],inclusive:!1},ID:{rules:[10,11,12],inclusive:!1},INITIAL:{rules:[0,1,2,3,4,5,6,7,8,9,11,12,13,16,18,20,23,27,30,33,36,55,58,69,70,71,72,73,74,75,77,78,79],inclusive:!0}}};return W}();gt.lexer=Zt;function ht(){this.yy={}}return S(ht,"Parser"),ht.prototype=gt,gt.Parser=ht,new ht}();Ct.parser=Ct;var He=Ct,ye="TB",Gt="TB",It="dir",st="state",et="root",At="relation",ge="classDef",Te="style",Ee="applyClass",nt="default",Vt="divider",Mt="fill:none",Ut="fill: #333",Wt="c",jt="markdown",Ht="normal",kt="rect",vt="rectWithTitle",_e="stateStart",me="stateEnd",Nt="divider",$t="roundedWithTitle",be="note",De="noteGroup",ot="statediagram",ke="state",ve=`${ot}-${ke}`,zt="transition",Ce="note",Ae="note-edge",xe=`${zt} ${Ae}`,Le=`${ot}-${Ce}`,we="cluster",Oe=`${ot}-${we}`,Re="cluster-alt",Ie=`${ot}-${Re}`,Kt="parent",Xt="note",Ne="state",xt="----",$e=`${xt}${Xt}`,Ft=`${xt}${Kt}`,Jt=S((t,e=Gt)=>{if(!t.doc)return e;let s=e;for(const a of t.doc)a.stmt==="dir"&&(s=a.value);return s},"getDir"),Fe=S(function(t,e){return e.db.getClasses()},"getClasses"),Pe=S(function(t,e,s,a){return Rt(this,null,function*(){var m,$;b.info("REF0:"),b.info("Drawing state diagram (v2)",e);const{securityLevel:i,state:o,layout:c}=P();a.db.extract(a.db.getRootDocV2());const d=a.db.getData(),h=se(e,i);d.type=a.type,d.layoutAlgorithm=c,d.nodeSpacing=(o==null?void 0:o.nodeSpacing)||50,d.rankSpacing=(o==null?void 0:o.rankSpacing)||50,P().look==="neo"?d.markers=["barbNeo"]:d.markers=["barb"],d.diagramId=e,yield re(d,h);const E=8;try{(typeof a.db.getLinks=="function"?a.db.getLinks():new Map).forEach((I,C)=>{var F;const v=typeof C=="string"?C:typeof(C==null?void 0:C.id)=="string"?C.id:"",p=d.nodes.find(O=>O.id===v);if(!v){b.warn("⚠️ Invalid or missing stateId from key:",JSON.stringify(C));return}const A=(F=h.node())==null?void 0:F.querySelectorAll("g.node, g.rough-node");let D;if(A==null||A.forEach(O=>{var H;const q=(H=O.textContent)==null?void 0:H.trim();(O.id===(p==null?void 0:p.domId)||q===v)&&(D=O)}),!D){b.warn("⚠️ Could not find node matching text:",v);return}const Y=D.parentNode;if(!Y){b.warn("⚠️ Node has no parent, cannot wrap:",v);return}const w=document.createElementNS("http://www.w3.org/2000/svg","a"),G=I.url.replace(/^"+|"+$/g,"");if(w.setAttributeNS("http://www.w3.org/1999/xlink","xlink:href",G),w.setAttribute("target","_blank"),I.tooltip){const O=I.tooltip.replace(/^"+|"+$/g,"");w.setAttribute("title",O),D.setAttribute("title",O)}Y.replaceChild(w,D),w.appendChild(D),b.info("🔗 Wrapped node in <a> tag for:",v,I.url)})}catch(B){b.error("❌ Error injecting clickable links:",B)}ae.insertTitle(h,"statediagramTitleText",(m=o==null?void 0:o.titleTopMargin)!=null?m:25,a.db.getDiagramTitle()),ie(h,E,ot,($=o==null?void 0:o.useMaxWidth)!=null?$:!0)})},"draw"),ze={getClasses:Fe,draw:Pe,getDir:Jt},St=new Map,j=0;function yt(t="",e=0,s="",a=xt){const i=s!==null&&s.length>0?`${a}${s}`:"";return`${Ne}-${t}${i}-${e}`}S(yt,"stateDomId");var Be=S((t,e,s,a,i,o,c,d)=>{b.trace("items",e),e.forEach(h=>{var g;switch(h.stmt){case st:at(t,h,s,a,i,o,c,d);break;case nt:at(t,h,s,a,i,o,c,d);break;case At:{at(t,h.state1,s,a,i,o,c,d),at(t,h.state2,s,a,i,o,c,d);const E=c==="neo",m={id:"edge"+j,start:h.state1.id,end:h.state2.id,arrowhead:"normal",arrowTypeEnd:E?"arrow_barb_neo":"arrow_barb",style:Mt,labelStyle:"",label:X.sanitizeText((g=h.description)!=null?g:"",P()),arrowheadStyle:Ut,labelpos:Wt,labelType:jt,thickness:Ht,classes:zt,look:c};i.push(m),j++}break}})},"setupDoc"),Pt=S((t,e=Gt)=>{let s=e;if(t.doc)for(const a of t.doc)a.stmt==="dir"&&(s=a.value);return s},"getDir");function rt(t,e,s){if(!e.id||e.id==="</join></fork>"||e.id==="</choice>")return;e.cssClasses&&(Array.isArray(e.cssCompiledStyles)||(e.cssCompiledStyles=[]),e.cssClasses.split(" ").forEach(i=>{var c;const o=s.get(i);o&&(e.cssCompiledStyles=[...(c=e.cssCompiledStyles)!=null?c:[],...o.styles])}));const a=t.find(i=>i.id===e.id);a?Object.assign(a,e):t.push(e)}S(rt,"insertOrUpdateNode");function qt(t){var e,s;return(s=(e=t==null?void 0:t.classes)==null?void 0:e.join(" "))!=null?s:""}S(qt,"getClassesFromDbInfo");function Qt(t){var e;return(e=t==null?void 0:t.styles)!=null?e:[]}S(Qt,"getStylesFromDbInfo");var at=S((t,e,s,a,i,o,c,d)=>{var B,I,C;const h=e.id,g=s.get(h),E=qt(g),m=Qt(g),$=P();if(b.info("dataFetcher parsedItem",e,g,m),h!=="root"){let v=kt;e.start===!0?v=_e:e.start===!1&&(v=me),e.type!==nt&&(v=e.type),St.get(h)||St.set(h,{id:h,shape:v,description:X.sanitizeText(h,$),cssClasses:`${E} ${ve}`,cssStyles:m});const p=St.get(h);e.description&&(Array.isArray(p.description)?(p.shape=vt,p.description.push(e.description)):(B=p.description)!=null&&B.length&&p.description.length>0?(p.shape=vt,p.description===h?p.description=[e.description]:p.description=[p.description,e.description]):(p.shape=kt,p.description=e.description),p.description=X.sanitizeTextOrArray(p.description,$)),((I=p.description)==null?void 0:I.length)===1&&p.shape===vt&&(p.type==="group"?p.shape=$t:p.shape=kt),!p.type&&e.doc&&(b.info("Setting cluster for XCX",h,Pt(e)),p.type="group",p.isGroup=!0,p.dir=Pt(e),p.explicitDir=e.doc.some(D=>D.stmt==="dir"),p.shape=e.type===Vt?Nt:$t,p.cssClasses=`${p.cssClasses} ${Oe} ${o?Ie:""}`);const A={labelStyle:"",shape:p.shape,label:p.description,cssClasses:p.cssClasses,cssCompiledStyles:[],cssStyles:p.cssStyles,id:h,dir:p.dir,domId:yt(h,j),type:p.type,isGroup:p.type==="group",padding:8,rx:10,ry:10,look:c,labelType:"markdown"};if(A.shape===Nt&&(A.label=""),t&&t.id!=="root"&&(b.trace("Setting node ",h," to be child of its parent ",t.id),A.parentId=t.id),A.centerLabel=!0,e.note){const D={labelStyle:"",shape:be,label:e.note.text,labelType:"markdown",cssClasses:Le,cssStyles:[],cssCompiledStyles:[],id:h+$e+"-"+j,domId:yt(h,j,Xt),type:p.type,isGroup:p.type==="group",padding:(C=$.flowchart)==null?void 0:C.padding,look:c,position:e.note.position},Y=h+Ft,w={labelStyle:"",shape:De,label:e.note.text,cssClasses:p.cssClasses,cssStyles:[],id:h+Ft,domId:yt(h,j,Kt),type:"group",isGroup:!0,padding:16,look:c,position:e.note.position};j++,w.id=Y,D.parentId=Y,rt(a,w,d),rt(a,D,d),rt(a,A,d);let G=h,F=D.id;e.note.position==="left of"&&(G=D.id,F=h),i.push({id:G+"-"+F,start:G,end:F,arrowhead:"none",arrowTypeEnd:"",style:Mt,labelStyle:"",classes:xe,arrowheadStyle:Ut,labelpos:Wt,labelType:jt,thickness:Ht,look:c})}else rt(a,A,d)}e.doc&&(b.trace("Adding nodes children "),Be(e,e.doc,s,a,i,!o,c,d))},"dataFetcher"),Ye=S(()=>{St.clear(),j=0},"reset"),x={START_NODE:"[*]",START_TYPE:"start",END_NODE:"[*]",END_TYPE:"end",COLOR_KEYWORD:"color",FILL_KEYWORD:"fill",BG_FILL:"bgFill",STYLECLASS_SEP:","},Bt=S(()=>new Map,"newClassesList"),Yt=S(()=>({relations:[],states:new Map,documents:{}}),"newDoc"),pt=S(t=>JSON.parse(JSON.stringify(t)),"clone"),J,Ke=(J=class{constructor(e){this.version=e,this.nodes=[],this.edges=[],this.rootDoc=[],this.classes=Bt(),this.documents={root:Yt()},this.currentDocument=this.documents.root,this.startEndCount=0,this.dividerCnt=0,this.links=new Map,this.funs=[],this.getAccTitle=ne,this.setAccTitle=oe,this.getAccDescription=le,this.setAccDescription=ce,this.setDiagramTitle=he,this.getDiagramTitle=ue,this.clear(),this.setRootDoc=this.setRootDoc.bind(this),this.getDividerId=this.getDividerId.bind(this),this.setDirection=this.setDirection.bind(this),this.trimColon=this.trimColon.bind(this),this.bindFunctions=this.bindFunctions.bind(this)}extract(e){this.clear(!0);for(const i of Array.isArray(e)?e:e.doc)switch(i.stmt){case st:this.addState(i.id.trim(),i.type,i.doc,i.description,i.note);break;case At:this.addRelation(i.state1,i.state2,i.description);break;case ge:this.addStyleClass(i.id.trim(),i.classes);break;case Te:this.handleStyleDef(i);break;case Ee:this.setCssClass(i.id.trim(),i.styleClass);break;case"click":this.addLink(i.id,i.url,i.tooltip);break}const s=this.getStates(),a=P();Ye(),at(void 0,this.getRootDocV2(),s,this.nodes,this.edges,!0,a.look,this.classes);for(const i of this.nodes)if(Array.isArray(i.label)){if(i.description=i.label.slice(1),i.isGroup&&i.description.length>0)throw new Error(`Group nodes can only have label. Remove the additional description for node [${i.id}]`);i.label=i.label[0]}}handleStyleDef(e){const s=e.id.trim().split(","),a=e.styleClass.split(",");for(const i of s){let o=this.getState(i);if(!o){const c=i.trim();this.addState(c),o=this.getState(c)}o&&(o.styles=a.map(c=>{var d;return(d=c.replace(/;/g,""))==null?void 0:d.trim()}))}}setRootDoc(e){b.info("Setting root doc",e),this.rootDoc=e,this.version===1?this.extract(e):this.extract(this.getRootDocV2())}docTranslator(e,s,a){if(s.stmt===At){this.docTranslator(e,s.state1,!0),this.docTranslator(e,s.state2,!1);return}if(s.stmt===st&&(s.id===x.START_NODE?(s.id=e.id+(a?"_start":"_end"),s.start=a):s.id=s.id.trim()),s.stmt!==et&&s.stmt!==st||!s.doc)return;const i=[];let o=[];for(const c of s.doc)if(c.type===Vt){const d=pt(c);d.doc=pt(o),i.push(d),o=[]}else o.push(c);if(i.length>0&&o.length>0){const c={stmt:st,id:de(),type:"divider",doc:pt(o)};i.push(pt(c)),s.doc=i}s.doc.forEach(c=>this.docTranslator(s,c,!0))}getRootDocV2(){return this.docTranslator({id:et,stmt:et},{id:et,stmt:et,doc:this.rootDoc},!0),{id:et,doc:this.rootDoc}}addState(e,s=nt,a=void 0,i=void 0,o=void 0,c=void 0,d=void 0,h=void 0){const g=e==null?void 0:e.trim();if(!this.currentDocument.states.has(g))b.info("Adding state ",g,i),this.currentDocument.states.set(g,{stmt:st,id:g,descriptions:[],type:s,doc:a,note:o,classes:[],styles:[],textStyles:[]});else{const E=this.currentDocument.states.get(g);if(!E)throw new Error(`State not found: ${g}`);E.doc||(E.doc=a),E.type||(E.type=s)}if(i&&(b.info("Setting state description",g,i),(Array.isArray(i)?i:[i]).forEach(m=>this.addDescription(g,m.trim()))),o){const E=this.currentDocument.states.get(g);if(!E)throw new Error(`State not found: ${g}`);E.note=o,E.note.text=X.sanitizeText(E.note.text,P())}c&&(b.info("Setting state classes",g,c),(Array.isArray(c)?c:[c]).forEach(m=>this.setCssClass(g,m.trim()))),d&&(b.info("Setting state styles",g,d),(Array.isArray(d)?d:[d]).forEach(m=>this.setStyle(g,m.trim()))),h&&(b.info("Setting state styles",g,d),(Array.isArray(h)?h:[h]).forEach(m=>this.setTextStyle(g,m.trim())))}clear(e){this.nodes=[],this.edges=[],this.funs=[this.setupToolTips.bind(this)],this.documents={root:Yt()},this.currentDocument=this.documents.root,this.startEndCount=0,this.classes=Bt(),e||(this.links=new Map,fe())}getState(e){return this.currentDocument.states.get(e)}getStates(){return this.currentDocument.states}logDocuments(){b.info("Documents = ",this.documents)}getRelations(){return this.currentDocument.relations}addLink(e,s,a){this.links.set(e,{url:s,tooltip:a}),b.warn("Adding link",e,s,a)}getLinks(){return this.links}startIdIfNeeded(e=""){return e===x.START_NODE?(this.startEndCount++,`${x.START_TYPE}${this.startEndCount}`):e}startTypeIfNeeded(e="",s=nt){return e===x.START_NODE?x.START_TYPE:s}endIdIfNeeded(e=""){return e===x.END_NODE?(this.startEndCount++,`${x.END_TYPE}${this.startEndCount}`):e}endTypeIfNeeded(e="",s=nt){return e===x.END_NODE?x.END_TYPE:s}addRelationObjs(e,s,a=""){const i=this.startIdIfNeeded(e.id.trim()),o=this.startTypeIfNeeded(e.id.trim(),e.type),c=this.startIdIfNeeded(s.id.trim()),d=this.startTypeIfNeeded(s.id.trim(),s.type);this.addState(i,o,e.doc,e.description,e.note,e.classes,e.styles,e.textStyles),this.addState(c,d,s.doc,s.description,s.note,s.classes,s.styles,s.textStyles),this.currentDocument.relations.push({id1:i,id2:c,relationTitle:X.sanitizeText(a,P())})}addRelation(e,s,a){if(typeof e=="object"&&typeof s=="object")this.addRelationObjs(e,s,a);else if(typeof e=="string"&&typeof s=="string"){const i=this.startIdIfNeeded(e.trim()),o=this.startTypeIfNeeded(e),c=this.endIdIfNeeded(s.trim()),d=this.endTypeIfNeeded(s);this.addState(i,o),this.addState(c,d),this.currentDocument.relations.push({id1:i,id2:c,relationTitle:a?X.sanitizeText(a,P()):void 0})}}addDescription(e,s){var o;const a=this.currentDocument.states.get(e),i=s.startsWith(":")?s.replace(":","").trim():s;(o=a==null?void 0:a.descriptions)==null||o.push(X.sanitizeText(i,P()))}cleanupLabel(e){return e.startsWith(":")?e.slice(2).trim():e.trim()}getDividerId(){return this.dividerCnt++,`divider-id-${this.dividerCnt}`}addStyleClass(e,s=""){this.classes.has(e)||this.classes.set(e,{id:e,styles:[],textStyles:[]});const a=this.classes.get(e);s&&a&&s.split(x.STYLECLASS_SEP).forEach(i=>{const o=i.replace(/([^;]*);/,"$1").trim();if(RegExp(x.COLOR_KEYWORD).exec(i)){const d=o.replace(x.FILL_KEYWORD,x.BG_FILL).replace(x.COLOR_KEYWORD,x.FILL_KEYWORD);a.textStyles.push(d)}a.styles.push(o)})}getClasses(){return this.classes}setupToolTips(e){const s=Se();Dt(e).select("svg").selectAll("g.node, g.rough-node").on("mouseover",o=>{var g;const c=Dt(o.currentTarget),d=c.attr("title");if(d===null)return;const h=(g=o.currentTarget)==null?void 0:g.getBoundingClientRect();s.transition().duration(200).style("opacity",".9"),s.style("left",window.scrollX+h.left+(h.right-h.left)/2+"px").style("top",window.scrollY+h.bottom+"px"),s.html(pe.sanitize(d)),c.classed("hover",!0)}).on("mouseout",o=>{s.transition().duration(500).style("opacity",0),Dt(o.currentTarget).classed("hover",!1)})}setCssClass(e,s){e.split(",").forEach(a=>{var o;let i=this.getState(a);if(!i){const c=a.trim();this.addState(c),i=this.getState(c)}(o=i==null?void 0:i.classes)==null||o.push(s)})}setStyle(e,s){var a,i;(i=(a=this.getState(e))==null?void 0:a.styles)==null||i.push(s)}setTextStyle(e,s){var a,i;(i=(a=this.getState(e))==null?void 0:a.textStyles)==null||i.push(s)}bindFunctions(e){this.funs.forEach(s=>{s(e)})}getDirectionStatement(){return this.rootDoc.find(e=>e.stmt===It)}getDirection(){var e,s;return(s=(e=this.getDirectionStatement())==null?void 0:e.value)!=null?s:ye}setDirection(e){const s=this.getDirectionStatement();s?s.value=e:this.rootDoc.unshift({stmt:It,value:e})}trimColon(e){return e.startsWith(":")?e.slice(1).trim():e.trim()}getData(){const e=P();return{nodes:this.nodes,edges:this.edges,other:{},config:e,direction:Jt(this.getRootDocV2())}}getConfig(){return P().state}},S(J,"StateDB"),J.relationType={AGGREGATION:0,EXTENSION:1,COMPOSITION:2,DEPENDENCY:3},J),Ge=S(t=>{var e;return`
defs [id$="-barbEnd"] {
    fill: ${t.transitionColor};
    stroke: ${t.transitionColor};
  }
g.stateGroup text {
  fill: ${t.nodeBorder};
  stroke: none;
  font-size: 10px;
}
g.stateGroup text {
  fill: ${t.textColor};
  stroke: none;
  font-size: 10px;

}
g.stateGroup .state-title {
  font-weight: bolder;
  fill: ${t.stateLabelColor};
}

g.stateGroup rect {
  fill: ${t.mainBkg};
  stroke: ${t.nodeBorder};
}

g.stateGroup line {
  stroke: ${t.lineColor};
  stroke-width: ${t.strokeWidth||1};
}

.transition {
  stroke: ${t.transitionColor};
  stroke-width: ${t.strokeWidth||1};
  fill: none;
}

.stateGroup .composit {
  fill: ${t.background};
  border-bottom: 1px
}

.stateGroup .alt-composit {
  fill: #e0e0e0;
  border-bottom: 1px
}

.state-note {
  stroke: ${t.noteBorderColor};
  fill: ${t.noteBkgColor};

  text {
    fill: ${t.noteTextColor};
    stroke: none;
    font-size: 10px;
  }
}

.stateLabel .box {
  stroke: none;
  stroke-width: 0;
  fill: ${t.mainBkg};
  opacity: 0.5;
}

.edgeLabel .label rect {
  fill: ${t.labelBackgroundColor};
  opacity: 0.5;
}
.edgeLabel {
  background-color: ${t.edgeLabelBackground};
  p {
    background-color: ${t.edgeLabelBackground};
  }
  rect {
    opacity: 0.5;
    background-color: ${t.edgeLabelBackground};
    fill: ${t.edgeLabelBackground};
  }
  text-align: center;
}
.edgeLabel .label text {
  fill: ${t.transitionLabelColor||t.tertiaryTextColor};
}
.label div .edgeLabel {
  color: ${t.transitionLabelColor||t.tertiaryTextColor};
}

.stateLabel text {
  fill: ${t.stateLabelColor};
  font-size: 10px;
  font-weight: bold;
}

.node circle.state-start {
  fill: ${t.specialStateColor};
  stroke: ${t.specialStateColor};
}

.node .fork-join {
  fill: ${t.specialStateColor};
  stroke: ${t.specialStateColor};
}

.node circle.state-end {
  fill: ${t.innerEndBackground};
  stroke: ${t.background};
  stroke-width: 1.5
}
.end-state-inner {
  fill: ${t.compositeBackground||t.background};
  // stroke: ${t.background};
  stroke-width: 1.5
}

.node rect {
  fill: ${t.stateBkg||t.mainBkg};
  stroke: ${t.stateBorder||t.nodeBorder};
  stroke-width: ${t.strokeWidth||1}px;
}
.node polygon {
  fill: ${t.mainBkg};
  stroke: ${t.stateBorder||t.nodeBorder};;
  stroke-width: ${t.strokeWidth||1}px;
}
[id$="-barbEnd"] {
  fill: ${t.lineColor};
}

.statediagram-cluster rect {
  fill: ${t.compositeTitleBackground};
  stroke: ${t.stateBorder||t.nodeBorder};
  stroke-width: ${t.strokeWidth||1}px;
}

.cluster-label, .nodeLabel {
  color: ${t.stateLabelColor};
  // line-height: 1;
}

.statediagram-cluster rect.outer {
  rx: 5px;
  ry: 5px;
}
.statediagram-state .divider {
  stroke: ${t.stateBorder||t.nodeBorder};
}

.statediagram-state .title-state {
  rx: 5px;
  ry: 5px;
}
.statediagram-cluster.statediagram-cluster .inner {
  fill: ${t.compositeBackground||t.background};
}
.statediagram-cluster.statediagram-cluster-alt .inner {
  fill: ${t.altBackground?t.altBackground:"#efefef"};
}

.statediagram-cluster .inner {
  rx:0;
  ry:0;
}

.statediagram-state rect.basic {
  rx: 5px;
  ry: 5px;
}
.statediagram-state rect.divider {
  stroke-dasharray: 10,10;
  fill: ${t.altBackground?t.altBackground:"#efefef"};
}

.note-edge {
  stroke-dasharray: 5;
}

.statediagram-note rect {
  fill: ${t.noteBkgColor};
  stroke: ${t.noteBorderColor};
  stroke-width: 1px;
  rx: 0;
  ry: 0;
}
.statediagram-note rect {
  fill: ${t.noteBkgColor};
  stroke: ${t.noteBorderColor};
  stroke-width: 1px;
  rx: 0;
  ry: 0;
}

.statediagram-note text {
  fill: ${t.noteTextColor};
}

.statediagram-note .nodeLabel {
  color: ${t.noteTextColor};
}
.statediagram .edgeLabel {
  color: red; // ${t.noteTextColor};
}

[id$="-dependencyStart"], [id$="-dependencyEnd"] {
  fill: ${t.lineColor};
  stroke: ${t.lineColor};
  stroke-width: ${t.strokeWidth||1};
}

.statediagramTitleText {
  text-anchor: middle;
  font-size: 18px;
  fill: ${t.textColor};
}

[data-look="neo"].statediagram-cluster rect {
  fill: ${t.mainBkg};
  stroke: ${t.useGradient?"url("+t.svgId+"-gradient)":t.stateBorder||t.nodeBorder};
  stroke-width: ${(e=t.strokeWidth)!=null?e:1};
}
[data-look="neo"].statediagram-cluster rect.outer {
  rx: ${t.radius}px;
  ry: ${t.radius}px;
  filter: ${t.dropShadow?t.dropShadow.replace("url(#drop-shadow)",`url(${t.svgId}-drop-shadow)`):"none"}
}
`},"getStyles"),Xe=Ge;export{Ke as S,He as a,ze as b,Xe as s};
