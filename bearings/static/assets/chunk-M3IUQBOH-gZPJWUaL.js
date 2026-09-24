import{g as se}from"./chunk-NDIOYS4C-AeIh1b4e.js";import{_ as S,l as D,c as P,y as ie,z as re,a as ae,b as ne,g as oe,s as le,n as ce,o as he,U as ue,i as J,p as de,R as fe}from"./render-O7CIS3YK-CNcZ7P9o.js";import{s as pe}from"./chunk-ISA7TJRJ-X32nkTJs.js";import{f as Se}from"./chunk-LV3HUYFY-BST56DQj.js";import{_ as m}from"./mermaid-layout-elk.core-CNKA6qqL.js";import{s as vt}from"./transform-Ck8scYFu.js";var xt=function(){var t=S(function(W,l,u,n){for(u=u||{},n=W.length;n--;u[W[n]]=l);return u},"o"),e=[1,2],s=[1,3],a=[1,4],r=[2,4],o=[1,9],h=[1,11],p=[1,16],d=[1,17],T=[1,18],E=[1,19],b=[1,33],R=[1,20],C=[1,21],L=[1,22],F=[1,23],O=[1,24],f=[1,26],I=[1,27],A=[1,28],M=[1,29],B=[1,30],v=[1,31],Y=[1,32],H=[1,35],ct=[1,36],ht=[1,37],ut=[1,38],q=[1,34],y=[1,4,5,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],dt=[1,4,5,14,15,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,39,40,41,45,48,51,52,53,54,57],Ot=[4,5,16,17,19,21,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],Tt={trace:S(m(function(){},"trace"),"trace"),yy:{},symbols_:{error:2,start:3,SPACE:4,NL:5,SD:6,document:7,line:8,statement:9,classDefStatement:10,styleStatement:11,cssClassStatement:12,idStatement:13,DESCR:14,"-->":15,HIDE_EMPTY:16,scale:17,WIDTH:18,COMPOSIT_STATE:19,STRUCT_START:20,STRUCT_STOP:21,STATE_DESCR:22,AS:23,ID:24,FORK:25,JOIN:26,CHOICE:27,CONCURRENT:28,note:29,notePosition:30,NOTE_TEXT:31,direction:32,acc_title:33,acc_title_value:34,acc_descr:35,acc_descr_value:36,acc_descr_multiline_value:37,CLICK:38,STRING:39,HREF:40,classDef:41,CLASSDEF_ID:42,CLASSDEF_STYLEOPTS:43,DEFAULT:44,style:45,STYLE_IDS:46,STYLEDEF_STYLEOPTS:47,class:48,CLASSENTITY_IDS:49,STYLECLASS:50,direction_tb:51,direction_bt:52,direction_rl:53,direction_lr:54,eol:55,";":56,EDGE_STATE:57,STYLE_SEPARATOR:58,left_of:59,right_of:60,$accept:0,$end:1},terminals_:{2:"error",4:"SPACE",5:"NL",6:"SD",14:"DESCR",15:"-->",16:"HIDE_EMPTY",17:"scale",18:"WIDTH",19:"COMPOSIT_STATE",20:"STRUCT_START",21:"STRUCT_STOP",22:"STATE_DESCR",23:"AS",24:"ID",25:"FORK",26:"JOIN",27:"CHOICE",28:"CONCURRENT",29:"note",31:"NOTE_TEXT",33:"acc_title",34:"acc_title_value",35:"acc_descr",36:"acc_descr_value",37:"acc_descr_multiline_value",38:"CLICK",39:"STRING",40:"HREF",41:"classDef",42:"CLASSDEF_ID",43:"CLASSDEF_STYLEOPTS",44:"DEFAULT",45:"style",46:"STYLE_IDS",47:"STYLEDEF_STYLEOPTS",48:"class",49:"CLASSENTITY_IDS",50:"STYLECLASS",51:"direction_tb",52:"direction_bt",53:"direction_rl",54:"direction_lr",56:";",57:"EDGE_STATE",58:"STYLE_SEPARATOR",59:"left_of",60:"right_of"},productions_:[0,[3,2],[3,2],[3,2],[7,0],[7,2],[8,2],[8,1],[8,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,3],[9,4],[9,1],[9,2],[9,1],[9,4],[9,3],[9,6],[9,1],[9,1],[9,1],[9,1],[9,4],[9,4],[9,1],[9,2],[9,2],[9,1],[9,5],[9,5],[10,3],[10,3],[11,3],[12,3],[32,1],[32,1],[32,1],[32,1],[55,1],[55,1],[13,1],[13,1],[13,3],[13,3],[30,1],[30,1]],performAction:S(m(function(l,u,n,g,_,i,G){var c=i.length-1;switch(_){case 3:return g.setRootDoc(i[c]),i[c];case 4:this.$=[];break;case 5:i[c]!="nl"&&(i[c-1].push(i[c]),this.$=i[c-1]);break;case 6:case 7:this.$=i[c];break;case 8:this.$="nl";break;case 12:this.$=i[c];break;case 13:const rt=i[c-1];rt.description=g.trimColon(i[c]),this.$=rt;break;case 14:this.$={stmt:"relation",state1:i[c-2],state2:i[c]};break;case 15:const Et=g.trimColon(i[c]);this.$={stmt:"relation",state1:i[c-3],state2:i[c-1],description:Et};break;case 19:this.$={stmt:"state",id:i[c-3],type:"default",description:"",doc:i[c-1]};break;case 20:var V=i[c],Q=i[c-2].trim();if(i[c].match(":")){var ft=i[c].split(":");V=ft[0],Q=[Q,ft[1]]}this.$={stmt:"state",id:V,type:"default",description:Q};break;case 21:this.$={stmt:"state",id:i[c-3],type:"default",description:i[c-5],doc:i[c-1]};break;case 22:this.$={stmt:"state",id:i[c],type:"fork"};break;case 23:this.$={stmt:"state",id:i[c],type:"join"};break;case 24:this.$={stmt:"state",id:i[c],type:"choice"};break;case 25:this.$={stmt:"state",id:g.getDividerId(),type:"divider"};break;case 26:this.$={stmt:"state",id:i[c-1].trim(),note:{position:i[c-2].trim(),text:i[c].trim()}};break;case 29:this.$=i[c].trim(),g.setAccTitle(this.$);break;case 30:case 31:this.$=i[c].trim(),g.setAccDescription(this.$);break;case 32:this.$={stmt:"click",id:i[c-3],url:i[c-2],tooltip:i[c-1]};break;case 33:this.$={stmt:"click",id:i[c-3],url:i[c-1],tooltip:""};break;case 34:case 35:this.$={stmt:"classDef",id:i[c-1].trim(),classes:i[c].trim()};break;case 36:this.$={stmt:"style",id:i[c-1].trim(),styleClass:i[c].trim()};break;case 37:this.$={stmt:"applyClass",id:i[c-1].trim(),styleClass:i[c].trim()};break;case 38:g.setDirection("TB"),this.$={stmt:"dir",value:"TB"};break;case 39:g.setDirection("BT"),this.$={stmt:"dir",value:"BT"};break;case 40:g.setDirection("RL"),this.$={stmt:"dir",value:"RL"};break;case 41:g.setDirection("LR"),this.$={stmt:"dir",value:"LR"};break;case 44:case 45:this.$={stmt:"state",id:i[c].trim(),type:"default",description:""};break;case 46:this.$={stmt:"state",id:i[c-2].trim(),classes:[i[c].trim()],type:"default",description:""};break;case 47:this.$={stmt:"state",id:i[c-2].trim(),classes:[i[c].trim()],type:"default",description:""};break}},"anonymous"),"anonymous"),table:[{3:1,4:e,5:s,6:a},{1:[3]},{3:5,4:e,5:s,6:a},{3:6,4:e,5:s,6:a},t([1,4,5,16,17,19,22,24,25,26,27,28,29,33,35,37,38,41,45,48,51,52,53,54,57],r,{7:7}),{1:[2,1]},{1:[2,2]},{1:[2,3],4:o,5:h,8:8,9:10,10:12,11:13,12:14,13:15,16:p,17:d,19:T,22:E,24:b,25:R,26:C,27:L,28:F,29:O,32:25,33:f,35:I,37:A,38:M,41:B,45:v,48:Y,51:H,52:ct,53:ht,54:ut,57:q},t(y,[2,5]),{9:39,10:12,11:13,12:14,13:15,16:p,17:d,19:T,22:E,24:b,25:R,26:C,27:L,28:F,29:O,32:25,33:f,35:I,37:A,38:M,41:B,45:v,48:Y,51:H,52:ct,53:ht,54:ut,57:q},t(y,[2,7]),t(y,[2,8]),t(y,[2,9]),t(y,[2,10]),t(y,[2,11]),t(y,[2,12],{14:[1,40],15:[1,41]}),t(y,[2,16]),{18:[1,42]},t(y,[2,18],{20:[1,43]}),{23:[1,44]},t(y,[2,22]),t(y,[2,23]),t(y,[2,24]),t(y,[2,25]),{30:45,31:[1,46],59:[1,47],60:[1,48]},t(y,[2,28]),{34:[1,49]},{36:[1,50]},t(y,[2,31]),{13:51,24:b,57:q},{42:[1,52],44:[1,53]},{46:[1,54]},{49:[1,55]},t(dt,[2,44],{58:[1,56]}),t(dt,[2,45],{58:[1,57]}),t(y,[2,38]),t(y,[2,39]),t(y,[2,40]),t(y,[2,41]),t(y,[2,6]),t(y,[2,13]),{13:58,24:b,57:q},t(y,[2,17]),t(Ot,r,{7:59}),{24:[1,60]},{24:[1,61]},{23:[1,62]},{24:[2,48]},{24:[2,49]},t(y,[2,29]),t(y,[2,30]),{39:[1,63],40:[1,64]},{43:[1,65]},{43:[1,66]},{47:[1,67]},{50:[1,68]},{24:[1,69]},{24:[1,70]},t(y,[2,14],{14:[1,71]}),{4:o,5:h,8:8,9:10,10:12,11:13,12:14,13:15,16:p,17:d,19:T,21:[1,72],22:E,24:b,25:R,26:C,27:L,28:F,29:O,32:25,33:f,35:I,37:A,38:M,41:B,45:v,48:Y,51:H,52:ct,53:ht,54:ut,57:q},t(y,[2,20],{20:[1,73]}),{31:[1,74]},{24:[1,75]},{39:[1,76]},{39:[1,77]},t(y,[2,34]),t(y,[2,35]),t(y,[2,36]),t(y,[2,37]),t(dt,[2,46]),t(dt,[2,47]),t(y,[2,15]),t(y,[2,19]),t(Ot,r,{7:78}),t(y,[2,26]),t(y,[2,27]),{5:[1,79]},{5:[1,80]},{4:o,5:h,8:8,9:10,10:12,11:13,12:14,13:15,16:p,17:d,19:T,21:[1,81],22:E,24:b,25:R,26:C,27:L,28:F,29:O,32:25,33:f,35:I,37:A,38:M,41:B,45:v,48:Y,51:H,52:ct,53:ht,54:ut,57:q},t(y,[2,32]),t(y,[2,33]),t(y,[2,21])],defaultActions:{5:[2,1],6:[2,2],47:[2,48],48:[2,49]},parseError:S(m(function(l,u){if(u.recoverable)this.trace(l);else{var n=new Error(l);throw n.hash=u,n}},"parseError"),"parseError"),parse:S(m(function(l){var u=this,n=[0],g=[],_=[null],i=[],G=this.table,c="",V=0,Q=0,ft=2,rt=1,Et=i.slice.call(arguments,1),k=Object.create(this.lexer),K={yy:{}};for(var _t in this.yy)Object.prototype.hasOwnProperty.call(this.yy,_t)&&(K.yy[_t]=this.yy[_t]);k.setInput(l,K.yy),K.yy.lexer=k,K.yy.parser=this,typeof k.yylloc>"u"&&(k.yylloc={});var mt=k.yylloc;i.push(mt);var ee=k.options&&k.options.ranges;typeof K.yy.parseError=="function"?this.parseError=K.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function Nt(N){n.length=n.length-2*N,_.length=_.length-N,i.length=i.length-N}m(Nt,"popStack"),S(Nt,"popStack");function bt(){var N;return N=g.pop()||k.lex()||rt,typeof N!="number"&&(N instanceof Array&&(g=N,N=g.pop()),N=u.symbols_[N]||N),N}m(bt,"lex"),S(bt,"lex");for(var w,X,$,Dt,Z={},pt,U,$t,St;;){if(X=n[n.length-1],this.defaultActions[X]?$=this.defaultActions[X]:((w===null||typeof w>"u")&&(w=bt()),$=G[X]&&G[X][w]),typeof $>"u"||!$.length||!$[0]){var kt="";St=[];for(pt in G[X])this.terminals_[pt]&&pt>ft&&St.push("'"+this.terminals_[pt]+"'");k.showPosition?kt="Parse error on line "+(V+1)+`:
`+k.showPosition()+`
Expecting `+St.join(", ")+", got '"+(this.terminals_[w]||w)+"'":kt="Parse error on line "+(V+1)+": Unexpected "+(w==rt?"end of input":"'"+(this.terminals_[w]||w)+"'"),this.parseError(kt,{text:k.match,token:this.terminals_[w]||w,line:k.yylineno,loc:mt,expected:St})}if($[0]instanceof Array&&$.length>1)throw new Error("Parse Error: multiple actions possible at state: "+X+", token: "+w);switch($[0]){case 1:n.push(w),_.push(k.yytext),i.push(k.yylloc),n.push($[1]),w=null,Q=k.yyleng,c=k.yytext,V=k.yylineno,mt=k.yylloc;break;case 2:if(U=this.productions_[$[1]][1],Z.$=_[_.length-U],Z._$={first_line:i[i.length-(U||1)].first_line,last_line:i[i.length-1].last_line,first_column:i[i.length-(U||1)].first_column,last_column:i[i.length-1].last_column},ee&&(Z._$.range=[i[i.length-(U||1)].range[0],i[i.length-1].range[1]]),Dt=this.performAction.apply(Z,[c,Q,V,K.yy,$[1],_,i].concat(Et)),typeof Dt<"u")return Dt;U&&(n=n.slice(0,-1*U*2),_=_.slice(0,-1*U),i=i.slice(0,-1*U)),n.push(this.productions_[$[1]][0]),_.push(Z.$),i.push(Z._$),$t=G[n[n.length-2]][n[n.length-1]],n.push($t);break;case 3:return!0}}return!0},"parse"),"parse")},te=function(){var W={EOF:1,parseError:S(m(function(u,n){if(this.yy.parser)this.yy.parser.parseError(u,n);else throw new Error(u)},"parseError"),"parseError"),setInput:S(function(l,u){return this.yy=u||this.yy||{},this._input=l,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:S(function(){var l=this._input[0];this.yytext+=l,this.yyleng++,this.offset++,this.match+=l,this.matched+=l;var u=l.match(/(?:\r\n?|\n).*/g);return u?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),l},"input"),unput:S(function(l){var u=l.length,n=l.split(/(?:\r\n?|\n)/g);this._input=l+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-u),this.offset-=u;var g=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),n.length-1&&(this.yylineno-=n.length-1);var _=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:n?(n.length===g.length?this.yylloc.first_column:0)+g[g.length-n.length].length-n[0].length:this.yylloc.first_column-u},this.options.ranges&&(this.yylloc.range=[_[0],_[0]+this.yyleng-u]),this.yyleng=this.yytext.length,this},"unput"),more:S(function(){return this._more=!0,this},"more"),reject:S(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},"reject"),less:S(function(l){this.unput(this.match.slice(l))},"less"),pastInput:S(function(){var l=this.matched.substr(0,this.matched.length-this.match.length);return(l.length>20?"...":"")+l.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:S(function(){var l=this.match;return l.length<20&&(l+=this._input.substr(0,20-l.length)),(l.substr(0,20)+(l.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:S(function(){var l=this.pastInput(),u=new Array(l.length+1).join("-");return l+this.upcomingInput()+`
`+u+"^"},"showPosition"),test_match:S(function(l,u){var n,g,_;if(this.options.backtrack_lexer&&(_={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(_.yylloc.range=this.yylloc.range.slice(0))),g=l[0].match(/(?:\r\n?|\n).*/g),g&&(this.yylineno+=g.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:g?g[g.length-1].length-g[g.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+l[0].length},this.yytext+=l[0],this.match+=l[0],this.matches=l,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(l[0].length),this.matched+=l[0],n=this.performAction.call(this,this.yy,this,u,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),n)return n;if(this._backtrack){for(var i in _)this[i]=_[i];return!1}return!1},"test_match"),next:S(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var l,u,n,g;this._more||(this.yytext="",this.match="");for(var _=this._currentRules(),i=0;i<_.length;i++)if(n=this._input.match(this.rules[_[i]]),n&&(!u||n[0].length>u[0].length)){if(u=n,g=i,this.options.backtrack_lexer){if(l=this.test_match(n,_[i]),l!==!1)return l;if(this._backtrack){u=!1;continue}else return!1}else if(!this.options.flex)break}return u?(l=this.test_match(u,_[g]),l!==!1?l:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:S(m(function(){var u=this.next();return u||this.lex()},"lex"),"lex"),begin:S(m(function(u){this.conditionStack.push(u)},"begin"),"begin"),popState:S(m(function(){var u=this.conditionStack.length-1;return u>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),"popState"),_currentRules:S(m(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),"_currentRules"),topState:S(m(function(u){return u=this.conditionStack.length-1-Math.abs(u||0),u>=0?this.conditionStack[u]:"INITIAL"},"topState"),"topState"),pushState:S(m(function(u){this.begin(u)},"pushState"),"pushState"),stateStackSize:S(m(function(){return this.conditionStack.length},"stateStackSize"),"stateStackSize"),options:{"case-insensitive":!0},performAction:S(m(function(u,n,g,_){function i(){const G=n.yytext.indexOf("%%");if(G===0)return!1;if(G>0){const c=n.yytext.slice(0,G),V=n.yytext.slice(G);V&&u.lexer.unput(V),n.yytext=c}return!0}switch(m(i,"processId"),S(i,"processId"),g){case 0:return 38;case 1:return 40;case 2:return 39;case 3:return 44;case 4:return 51;case 5:return 52;case 6:return 53;case 7:return 54;case 8:return 5;case 9:break;case 10:break;case 11:break;case 12:break;case 13:return this.pushState("SCALE"),17;case 14:return 18;case 15:this.popState();break;case 16:return this.begin("acc_title"),33;case 17:return this.popState(),"acc_title_value";case 18:return this.begin("acc_descr"),35;case 19:return this.popState(),"acc_descr_value";case 20:this.begin("acc_descr_multiline");break;case 21:this.popState();break;case 22:return"acc_descr_multiline_value";case 23:return this.pushState("CLASSDEF"),41;case 24:return this.popState(),this.pushState("CLASSDEFID"),"DEFAULT_CLASSDEF_ID";case 25:return this.popState(),this.pushState("CLASSDEFID"),42;case 26:return this.popState(),43;case 27:return this.pushState("CLASS"),48;case 28:return this.popState(),this.pushState("CLASS_STYLE"),49;case 29:return this.popState(),50;case 30:return this.pushState("STYLE"),45;case 31:return this.popState(),this.pushState("STYLEDEF_STYLES"),46;case 32:return this.popState(),47;case 33:return this.pushState("SCALE"),17;case 34:return 18;case 35:this.popState();break;case 36:this.pushState("STATE");break;case 37:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),25;case 38:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),26;case 39:return this.popState(),n.yytext=n.yytext.slice(0,-10).trim(),27;case 40:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),25;case 41:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),26;case 42:return this.popState(),n.yytext=n.yytext.slice(0,-10).trim(),27;case 43:return 51;case 44:return 52;case 45:return 53;case 46:return 54;case 47:this.pushState("STATE_STRING");break;case 48:return this.pushState("STATE_ID"),"AS";case 49:return i()?(this.popState(),"ID"):void 0;case 50:this.popState();break;case 51:return"STATE_DESCR";case 52:throw new Error('Error: State name must be a single word. Found: "'+n.yytext.trim()+'"');case 53:return 19;case 54:this.popState();break;case 55:return this.popState(),this.pushState("struct"),20;case 56:return this.popState(),21;case 57:break;case 58:return this.begin("NOTE"),29;case 59:return this.popState(),this.pushState("NOTE_ID"),59;case 60:return this.popState(),this.pushState("NOTE_ID"),60;case 61:this.popState(),this.pushState("FLOATING_NOTE");break;case 62:return this.popState(),this.pushState("FLOATING_NOTE_ID"),"AS";case 63:break;case 64:return"NOTE_TEXT";case 65:return i()?(this.popState(),"ID"):void 0;case 66:return i()?(this.popState(),this.pushState("NOTE_TEXT"),24):void 0;case 67:return this.popState(),n.yytext=n.yytext.substr(2).trim(),31;case 68:return this.popState(),n.yytext=n.yytext.slice(0,-8).trim(),31;case 69:return 6;case 70:return 6;case 71:return 16;case 72:return 57;case 73:return i()?24:void 0;case 74:return n.yytext=n.yytext.trim(),14;case 75:return 15;case 76:return 28;case 77:return 58;case 78:return 5;case 79:return"INVALID"}},"anonymous"),"anonymous"),rules:[/^(?:click\b)/i,/^(?:href\b)/i,/^(?:"[^"]*")/i,/^(?:default\b)/i,/^(?:.*direction\s+TB[^\n]*)/i,/^(?:.*direction\s+BT[^\n]*)/i,/^(?:.*direction\s+RL[^\n]*)/i,/^(?:.*direction\s+LR[^\n]*)/i,/^(?:[\n]+)/i,/^(?:[\s]+)/i,/^(?:((?!\n)\s)+)/i,/^(?:#[^\n]*)/i,/^(?:%%(?!\{)[^\n]*)/i,/^(?:scale\s+)/i,/^(?:\d+)/i,/^(?:\s+width\b)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:classDef\s+)/i,/^(?:DEFAULT\s+)/i,/^(?:\w+\s+)/i,/^(?:[^\n]*)/i,/^(?:class\s+)/i,/^(?:(\w+)+((,\s*\w+)*))/i,/^(?:[^\n]*)/i,/^(?:style\s+)/i,/^(?:[\w,]+\s+)/i,/^(?:[^\n]*)/i,/^(?:scale\s+)/i,/^(?:\d+)/i,/^(?:\s+width\b)/i,/^(?:state\s+)/i,/^(?:.*<<fork>>)/i,/^(?:.*<<join>>)/i,/^(?:.*<<choice>>)/i,/^(?:.*\[\[fork\]\])/i,/^(?:.*\[\[join\]\])/i,/^(?:.*\[\[choice\]\])/i,/^(?:.*direction\s+TB[^\n]*)/i,/^(?:.*direction\s+BT[^\n]*)/i,/^(?:.*direction\s+RL[^\n]*)/i,/^(?:.*direction\s+LR[^\n]*)/i,/^(?:["])/i,/^(?:\s*as\s+)/i,/^(?:[^\n\{]*)/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:\w+\s+\w+.*?\{)/i,/^(?:[^\n\s\{]+)/i,/^(?:\n)/i,/^(?:\{)/i,/^(?:\})/i,/^(?:[\n])/i,/^(?:note\s+)/i,/^(?:left of\b)/i,/^(?:right of\b)/i,/^(?:")/i,/^(?:\s*as\s*)/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:[^\n]*)/i,/^(?:\s*[^:\n\s\-]+)/i,/^(?:\s*:[^:\n;]+)/i,/^(?:[\s\S]*?\n\s*end note\b)/i,/^(?:stateDiagram\s+)/i,/^(?:stateDiagram-v2\s+)/i,/^(?:hide empty description\b)/i,/^(?:\[\*\])/i,/^(?:[^:\n\s\-\{]+)/i,/^(?:\s*:(?:[^:\n;]|:[^:\n;])+)/i,/^(?:-->)/i,/^(?:--)/i,/^(?::::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{LINE:{rules:[10,11,12],inclusive:!1},struct:{rules:[10,11,12,23,27,30,36,43,44,45,46,56,57,58,72,73,74,75,76,77],inclusive:!1},FLOATING_NOTE_ID:{rules:[65],inclusive:!1},FLOATING_NOTE:{rules:[62,63,64],inclusive:!1},NOTE_TEXT:{rules:[67,68],inclusive:!1},NOTE_ID:{rules:[66],inclusive:!1},NOTE:{rules:[59,60,61],inclusive:!1},STYLEDEF_STYLEOPTS:{rules:[],inclusive:!1},STYLEDEF_STYLES:{rules:[32],inclusive:!1},STYLE_IDS:{rules:[],inclusive:!1},STYLE:{rules:[31],inclusive:!1},CLASS_STYLE:{rules:[29],inclusive:!1},CLASS:{rules:[28],inclusive:!1},CLASSDEFID:{rules:[26],inclusive:!1},CLASSDEF:{rules:[24,25],inclusive:!1},acc_descr_multiline:{rules:[21,22],inclusive:!1},acc_descr:{rules:[19],inclusive:!1},acc_title:{rules:[17],inclusive:!1},SCALE:{rules:[14,15,34,35],inclusive:!1},ALIAS:{rules:[],inclusive:!1},STATE_ID:{rules:[49],inclusive:!1},STATE_STRING:{rules:[50,51],inclusive:!1},FORK_STATE:{rules:[],inclusive:!1},STATE:{rules:[10,11,12,37,38,39,40,41,42,47,48,52,53,54,55],inclusive:!1},ID:{rules:[10,11,12],inclusive:!1},INITIAL:{rules:[0,1,2,3,4,5,6,7,8,9,11,12,13,16,18,20,23,27,30,33,36,55,58,69,70,71,72,73,74,75,77,78,79],inclusive:!0}}};return W}();Tt.lexer=te;function it(){this.yy={}}return m(it,"Parser"),S(it,"Parser"),it.prototype=Tt,Tt.Parser=it,new it}();xt.parser=xt;var He=xt,ye="TB",Ut="TB",Ft="dir",et="state",tt="root",Lt="relation",ge="classDef",Te="style",Ee="applyClass",nt="default",Wt="divider",jt="fill:none",zt="fill: #333",Ht="c",Kt="markdown",Xt="normal",Ct="rect",At="rectWithTitle",_e="stateStart",me="stateEnd",Pt="divider",Bt="roundedWithTitle",be="note",De="noteGroup",lt="statediagram",ke="state",ve=`${lt}-${ke}`,Jt="transition",Ce="note",Ae="note-edge",xe=`${Jt} ${Ae}`,Le=`${lt}-${Ce}`,Ie="cluster",we=`${lt}-${Ie}`,Re="cluster-alt",Oe=`${lt}-${Re}`,qt="parent",Qt="note",Ne="state",It="----",$e=`${It}${Qt}`,Yt=`${It}${qt}`,Zt=S((t,e=Ut)=>{if(!t.doc)return e;let s=e;for(const a of t.doc)a.stmt==="dir"&&(s=a.value);return s},"getDir"),Fe=S(function(t,e){return e.db.getClasses()},"getClasses"),Pe=S(async function(t,e,s,a){D.info("REF0:"),D.info("Drawing state diagram (v2)",e);const{securityLevel:r,state:o,layout:h}=P();a.db.extract(a.db.getRootDocV2());const p=a.db.getData(),d=se(e,r);p.type=a.type,p.layoutAlgorithm=h,p.nodeSpacing=(o==null?void 0:o.nodeSpacing)||50,p.rankSpacing=(o==null?void 0:o.rankSpacing)||50,P().look==="neo"?p.markers=["barbNeo"]:p.markers=["barb"],p.diagramId=e,await ie(p,d);const E=8;try{(typeof a.db.getLinks=="function"?a.db.getLinks():new Map).forEach((R,C)=>{var B;const L=typeof C=="string"?C:typeof(C==null?void 0:C.id)=="string"?C.id:"",F=p.nodes.find(v=>v.id===L);if(!L){D.warn("⚠️ Invalid or missing stateId from key:",JSON.stringify(C));return}const O=(B=d.node())==null?void 0:B.querySelectorAll("g.node, g.rough-node");let f;if(O==null||O.forEach(v=>{var H;const Y=(H=v.textContent)==null?void 0:H.trim();(v.id===(F==null?void 0:F.domId)||Y===L)&&(f=v)}),!f){D.warn("⚠️ Could not find node matching text:",L);return}const I=f.parentNode;if(!I){D.warn("⚠️ Node has no parent, cannot wrap:",L);return}const A=document.createElementNS("http://www.w3.org/2000/svg","a"),M=R.url.replace(/^"+|"+$/g,"");if(A.setAttributeNS("http://www.w3.org/1999/xlink","xlink:href",M),A.setAttribute("target","_blank"),R.tooltip){const v=R.tooltip.replace(/^"+|"+$/g,"");A.setAttribute("title",v),f.setAttribute("title",v)}I.replaceChild(A,f),A.appendChild(f),D.info("🔗 Wrapped node in <a> tag for:",L,R.url)})}catch(b){D.error("❌ Error injecting clickable links:",b)}re.insertTitle(d,"statediagramTitleText",(o==null?void 0:o.titleTopMargin)??25,a.db.getDiagramTitle()),pe(d,E,lt,(o==null?void 0:o.useMaxWidth)??!0)},"draw"),Ke={getClasses:Fe,draw:Pe,getDir:Zt},gt=new Map,j=0;function ot(t="",e=0,s="",a=It){const r=s!==null&&s.length>0?`${a}${s}`:"";return`${Ne}-${t}${r}-${e}`}m(ot,"stateDomId");S(ot,"stateDomId");var Be=S((t,e,s,a,r,o,h,p)=>{D.trace("items",e),e.forEach(d=>{switch(d.stmt){case et:at(t,d,s,a,r,o,h,p);break;case nt:at(t,d,s,a,r,o,h,p);break;case Lt:{at(t,d.state1,s,a,r,o,h,p),at(t,d.state2,s,a,r,o,h,p);const T=h==="neo",E={id:"edge"+j,start:d.state1.id,end:d.state2.id,arrowhead:"normal",arrowTypeEnd:T?"arrow_barb_neo":"arrow_barb",style:jt,labelStyle:"",label:J.sanitizeText(d.description??"",P()),arrowheadStyle:zt,labelpos:Ht,labelType:Kt,thickness:Xt,classes:Jt,look:h};r.push(E),j++}break}})},"setupDoc"),Gt=S((t,e=Ut)=>{let s=e;if(t.doc)for(const a of t.doc)a.stmt==="dir"&&(s=a.value);return s},"getDir");function st(t,e,s){if(!e.id||e.id==="</join></fork>"||e.id==="</choice>")return;e.cssClasses&&(Array.isArray(e.cssCompiledStyles)||(e.cssCompiledStyles=[]),e.cssClasses.split(" ").forEach(r=>{const o=s.get(r);o&&(e.cssCompiledStyles=[...e.cssCompiledStyles??[],...o.styles])}));const a=t.find(r=>r.id===e.id);a?Object.assign(a,e):t.push(e)}m(st,"insertOrUpdateNode");S(st,"insertOrUpdateNode");function wt(t){var e;return((e=t==null?void 0:t.classes)==null?void 0:e.join(" "))??""}m(wt,"getClassesFromDbInfo");S(wt,"getClassesFromDbInfo");function Rt(t){return(t==null?void 0:t.styles)??[]}m(Rt,"getStylesFromDbInfo");S(Rt,"getStylesFromDbInfo");var at=S((t,e,s,a,r,o,h,p)=>{var C,L,F;const d=e.id,T=s.get(d),E=wt(T),b=Rt(T),R=P();if(D.info("dataFetcher parsedItem",e,T,b),d!=="root"){let O=Ct;e.start===!0?O=_e:e.start===!1&&(O=me),e.type!==nt&&(O=e.type),gt.get(d)||gt.set(d,{id:d,shape:O,description:J.sanitizeText(d,R),cssClasses:`${E} ${ve}`,cssStyles:b});const f=gt.get(d);e.description&&(Array.isArray(f.description)?(f.shape=At,f.description.push(e.description)):(C=f.description)!=null&&C.length&&f.description.length>0?(f.shape=At,f.description===d?f.description=[e.description]:f.description=[f.description,e.description]):(f.shape=Ct,f.description=e.description),f.description=J.sanitizeTextOrArray(f.description,R)),((L=f.description)==null?void 0:L.length)===1&&f.shape===At&&(f.type==="group"?f.shape=Bt:f.shape=Ct),!f.type&&e.doc&&(D.info("Setting cluster for XCX",d,Gt(e)),f.type="group",f.isGroup=!0,f.dir=Gt(e),f.shape=e.type===Wt?Pt:Bt,f.cssClasses=`${f.cssClasses} ${we} ${o?Oe:""}`);const I={labelStyle:"",shape:f.shape,label:f.description,cssClasses:f.cssClasses,cssCompiledStyles:[],cssStyles:f.cssStyles,id:d,dir:f.dir,domId:ot(d,j),type:f.type,isGroup:f.type==="group",padding:8,rx:10,ry:10,look:h,labelType:"markdown"};if(I.shape===Pt&&(I.label=""),t&&t.id!=="root"&&(D.trace("Setting node ",d," to be child of its parent ",t.id),I.parentId=t.id),I.centerLabel=!0,e.note){const A={labelStyle:"",shape:be,label:e.note.text,labelType:"markdown",cssClasses:Le,cssStyles:[],cssCompiledStyles:[],id:d+$e+"-"+j,domId:ot(d,j,Qt),type:f.type,isGroup:f.type==="group",padding:(F=R.flowchart)==null?void 0:F.padding,look:h,position:e.note.position},M=d+Yt,B={labelStyle:"",shape:De,label:e.note.text,cssClasses:f.cssClasses,cssStyles:[],id:d+Yt,domId:ot(d,j,qt),type:"group",isGroup:!0,padding:16,look:h,position:e.note.position};j++,B.id=M,A.parentId=M,st(a,B,p),st(a,A,p),st(a,I,p);let v=d,Y=A.id;e.note.position==="left of"&&(v=A.id,Y=d),r.push({id:v+"-"+Y,start:v,end:Y,arrowhead:"none",arrowTypeEnd:"",style:jt,labelStyle:"",classes:xe,arrowheadStyle:zt,labelpos:Ht,labelType:Kt,thickness:Xt,look:h})}else st(a,I,p)}e.doc&&(D.trace("Adding nodes children "),Be(e,e.doc,s,a,r,!o,h,p))},"dataFetcher"),Ye=S(()=>{gt.clear(),j=0},"reset"),x={START_NODE:"[*]",START_TYPE:"start",END_NODE:"[*]",END_TYPE:"end",COLOR_KEYWORD:"color",FILL_KEYWORD:"fill",BG_FILL:"bgFill",STYLECLASS_SEP:","},Vt=S(()=>new Map,"newClassesList"),Mt=S(()=>({relations:[],states:new Map,documents:{}}),"newDoc"),yt=S(t=>JSON.parse(JSON.stringify(t)),"clone"),z,Xe=(z=class{constructor(e){this.version=e,this.nodes=[],this.edges=[],this.rootDoc=[],this.classes=Vt(),this.documents={root:Mt()},this.currentDocument=this.documents.root,this.startEndCount=0,this.dividerCnt=0,this.links=new Map,this.funs=[],this.getAccTitle=ae,this.setAccTitle=ne,this.getAccDescription=oe,this.setAccDescription=le,this.setDiagramTitle=ce,this.getDiagramTitle=he,this.clear(),this.setRootDoc=this.setRootDoc.bind(this),this.getDividerId=this.getDividerId.bind(this),this.setDirection=this.setDirection.bind(this),this.trimColon=this.trimColon.bind(this),this.bindFunctions=this.bindFunctions.bind(this)}extract(e){this.clear(!0);for(const r of Array.isArray(e)?e:e.doc)switch(r.stmt){case et:this.addState(r.id.trim(),r.type,r.doc,r.description,r.note);break;case Lt:this.addRelation(r.state1,r.state2,r.description);break;case ge:this.addStyleClass(r.id.trim(),r.classes);break;case Te:this.handleStyleDef(r);break;case Ee:this.setCssClass(r.id.trim(),r.styleClass);break;case"click":this.addLink(r.id,r.url,r.tooltip);break}const s=this.getStates(),a=P();Ye(),at(void 0,this.getRootDocV2(),s,this.nodes,this.edges,!0,a.look,this.classes);for(const r of this.nodes)if(Array.isArray(r.label)){if(r.description=r.label.slice(1),r.isGroup&&r.description.length>0)throw new Error(`Group nodes can only have label. Remove the additional description for node [${r.id}]`);r.label=r.label[0]}}handleStyleDef(e){const s=e.id.trim().split(","),a=e.styleClass.split(",");for(const r of s){let o=this.getState(r);if(!o){const h=r.trim();this.addState(h),o=this.getState(h)}o&&(o.styles=a.map(h=>{var p;return(p=h.replace(/;/g,""))==null?void 0:p.trim()}))}}setRootDoc(e){D.info("Setting root doc",e),this.rootDoc=e,this.version===1?this.extract(e):this.extract(this.getRootDocV2())}docTranslator(e,s,a){if(s.stmt===Lt){this.docTranslator(e,s.state1,!0),this.docTranslator(e,s.state2,!1);return}if(s.stmt===et&&(s.id===x.START_NODE?(s.id=e.id+(a?"_start":"_end"),s.start=a):s.id=s.id.trim()),s.stmt!==tt&&s.stmt!==et||!s.doc)return;const r=[];let o=[];for(const h of s.doc)if(h.type===Wt){const p=yt(h);p.doc=yt(o),r.push(p),o=[]}else o.push(h);if(r.length>0&&o.length>0){const h={stmt:et,id:ue(),type:"divider",doc:yt(o)};r.push(yt(h)),s.doc=r}s.doc.forEach(h=>this.docTranslator(s,h,!0))}getRootDocV2(){return this.docTranslator({id:tt,stmt:tt},{id:tt,stmt:tt,doc:this.rootDoc},!0),{id:tt,doc:this.rootDoc}}addState(e,s=nt,a=void 0,r=void 0,o=void 0,h=void 0,p=void 0,d=void 0){const T=e==null?void 0:e.trim();if(!this.currentDocument.states.has(T))D.info("Adding state ",T,r),this.currentDocument.states.set(T,{stmt:et,id:T,descriptions:[],type:s,doc:a,note:o,classes:[],styles:[],textStyles:[]});else{const E=this.currentDocument.states.get(T);if(!E)throw new Error(`State not found: ${T}`);E.doc||(E.doc=a),E.type||(E.type=s)}if(r&&(D.info("Setting state description",T,r),(Array.isArray(r)?r:[r]).forEach(b=>this.addDescription(T,b.trim()))),o){const E=this.currentDocument.states.get(T);if(!E)throw new Error(`State not found: ${T}`);E.note=o,E.note.text=J.sanitizeText(E.note.text,P())}h&&(D.info("Setting state classes",T,h),(Array.isArray(h)?h:[h]).forEach(b=>this.setCssClass(T,b.trim()))),p&&(D.info("Setting state styles",T,p),(Array.isArray(p)?p:[p]).forEach(b=>this.setStyle(T,b.trim()))),d&&(D.info("Setting state styles",T,p),(Array.isArray(d)?d:[d]).forEach(b=>this.setTextStyle(T,b.trim())))}clear(e){this.nodes=[],this.edges=[],this.funs=[this.setupToolTips.bind(this)],this.documents={root:Mt()},this.currentDocument=this.documents.root,this.startEndCount=0,this.classes=Vt(),e||(this.links=new Map,de())}getState(e){return this.currentDocument.states.get(e)}getStates(){return this.currentDocument.states}logDocuments(){D.info("Documents = ",this.documents)}getRelations(){return this.currentDocument.relations}addLink(e,s,a){this.links.set(e,{url:s,tooltip:a}),D.warn("Adding link",e,s,a)}getLinks(){return this.links}startIdIfNeeded(e=""){return e===x.START_NODE?(this.startEndCount++,`${x.START_TYPE}${this.startEndCount}`):e}startTypeIfNeeded(e="",s=nt){return e===x.START_NODE?x.START_TYPE:s}endIdIfNeeded(e=""){return e===x.END_NODE?(this.startEndCount++,`${x.END_TYPE}${this.startEndCount}`):e}endTypeIfNeeded(e="",s=nt){return e===x.END_NODE?x.END_TYPE:s}addRelationObjs(e,s,a=""){const r=this.startIdIfNeeded(e.id.trim()),o=this.startTypeIfNeeded(e.id.trim(),e.type),h=this.startIdIfNeeded(s.id.trim()),p=this.startTypeIfNeeded(s.id.trim(),s.type);this.addState(r,o,e.doc,e.description,e.note,e.classes,e.styles,e.textStyles),this.addState(h,p,s.doc,s.description,s.note,s.classes,s.styles,s.textStyles),this.currentDocument.relations.push({id1:r,id2:h,relationTitle:J.sanitizeText(a,P())})}addRelation(e,s,a){if(typeof e=="object"&&typeof s=="object")this.addRelationObjs(e,s,a);else if(typeof e=="string"&&typeof s=="string"){const r=this.startIdIfNeeded(e.trim()),o=this.startTypeIfNeeded(e),h=this.endIdIfNeeded(s.trim()),p=this.endTypeIfNeeded(s);this.addState(r,o),this.addState(h,p),this.currentDocument.relations.push({id1:r,id2:h,relationTitle:a?J.sanitizeText(a,P()):void 0})}}addDescription(e,s){var o;const a=this.currentDocument.states.get(e),r=s.startsWith(":")?s.replace(":","").trim():s;(o=a==null?void 0:a.descriptions)==null||o.push(J.sanitizeText(r,P()))}cleanupLabel(e){return e.startsWith(":")?e.slice(2).trim():e.trim()}getDividerId(){return this.dividerCnt++,`divider-id-${this.dividerCnt}`}addStyleClass(e,s=""){this.classes.has(e)||this.classes.set(e,{id:e,styles:[],textStyles:[]});const a=this.classes.get(e);s&&a&&s.split(x.STYLECLASS_SEP).forEach(r=>{const o=r.replace(/([^;]*);/,"$1").trim();if(RegExp(x.COLOR_KEYWORD).exec(r)){const p=o.replace(x.FILL_KEYWORD,x.BG_FILL).replace(x.COLOR_KEYWORD,x.FILL_KEYWORD);a.textStyles.push(p)}a.styles.push(o)})}getClasses(){return this.classes}setupToolTips(e){const s=Se();vt(e).select("svg").selectAll("g.node, g.rough-node").on("mouseover",o=>{var T;const h=vt(o.currentTarget),p=h.attr("title");if(p===null)return;const d=(T=o.currentTarget)==null?void 0:T.getBoundingClientRect();s.transition().duration(200).style("opacity",".9"),s.style("left",window.scrollX+d.left+(d.right-d.left)/2+"px").style("top",window.scrollY+d.bottom+"px"),s.html(fe.sanitize(p)),h.classed("hover",!0)}).on("mouseout",o=>{s.transition().duration(500).style("opacity",0),vt(o.currentTarget).classed("hover",!1)})}setCssClass(e,s){e.split(",").forEach(a=>{var o;let r=this.getState(a);if(!r){const h=a.trim();this.addState(h),r=this.getState(h)}(o=r==null?void 0:r.classes)==null||o.push(s)})}setStyle(e,s){var a,r;(r=(a=this.getState(e))==null?void 0:a.styles)==null||r.push(s)}setTextStyle(e,s){var a,r;(r=(a=this.getState(e))==null?void 0:a.textStyles)==null||r.push(s)}bindFunctions(e){this.funs.forEach(s=>{s(e)})}getDirectionStatement(){return this.rootDoc.find(e=>e.stmt===Ft)}getDirection(){var e;return((e=this.getDirectionStatement())==null?void 0:e.value)??ye}setDirection(e){const s=this.getDirectionStatement();s?s.value=e:this.rootDoc.unshift({stmt:Ft,value:e})}trimColon(e){return e.startsWith(":")?e.slice(1).trim():e.trim()}getData(){const e=P();return{nodes:this.nodes,edges:this.edges,other:{},config:e,direction:Zt(this.getRootDocV2())}}getConfig(){return P().state}},m(z,"StateDB"),S(z,"StateDB"),z.relationType={AGGREGATION:0,EXTENSION:1,COMPOSITION:2,DEPENDENCY:3},z),Ge=S(t=>`
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
  stroke-width: ${t.strokeWidth??1};
}
[data-look="neo"].statediagram-cluster rect.outer {
  rx: ${t.radius}px;
  ry: ${t.radius}px;
  filter: ${t.dropShadow?t.dropShadow.replace("url(#drop-shadow)",`url(${t.svgId}-drop-shadow)`):"none"}
}
`,"getStyles"),Je=Ge;export{Xe as S,He as a,Ke as b,Je as s};
