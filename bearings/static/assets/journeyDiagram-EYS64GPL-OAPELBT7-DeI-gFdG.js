import{g as mt}from"./chunk-CXNFBKHE-DSKkOARP.js";import{a as xt,b as ht,h as kt,d as _t}from"./chunk-LV3HUYFY-BST56DQj.js";import{_ as k}from"./mermaid-layout-elk.core-CNKA6qqL.js";import{g as bt,s as vt,a as wt,b as Tt,o as St,n as $t,_ as s,c as L,d as Mt,p as Et}from"./render-O7CIS3YK-CNcZ7P9o.js";import{s as U}from"./transform-Ck8scYFu.js";import{d as st}from"./arc-8OW0--_5.js";import"./index-CQqDpKBO.js";var J=function(){var t=s(function(h,i,n,l){for(n=n||{},l=h.length;l--;n[h[l]]=i);return n},"o"),e=[6,8,10,11,12,14,16,17,18],a=[1,9],p=[1,10],r=[1,11],u=[1,12],f=[1,13],o=[1,14],g={trace:s(k(function(){},"trace"),"trace"),yy:{},symbols_:{error:2,start:3,journey:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NEWLINE:10,title:11,acc_title:12,acc_title_value:13,acc_descr:14,acc_descr_value:15,acc_descr_multiline_value:16,section:17,taskName:18,taskData:19,$accept:0,$end:1},terminals_:{2:"error",4:"journey",6:"EOF",8:"SPACE",10:"NEWLINE",11:"title",12:"acc_title",13:"acc_title_value",14:"acc_descr",15:"acc_descr_value",16:"acc_descr_multiline_value",17:"section",18:"taskName",19:"taskData"},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,2]],performAction:s(k(function(i,n,l,y,d,c,v){var _=c.length-1;switch(d){case 1:return c[_-1];case 2:this.$=[];break;case 3:c[_-1].push(c[_]),this.$=c[_-1];break;case 4:case 5:this.$=c[_];break;case 6:case 7:this.$=[];break;case 8:y.setDiagramTitle(c[_].substr(6)),this.$=c[_].substr(6);break;case 9:this.$=c[_].trim(),y.setAccTitle(this.$);break;case 10:case 11:this.$=c[_].trim(),y.setAccDescription(this.$);break;case 12:y.addSection(c[_].substr(8)),this.$=c[_].substr(8);break;case 13:y.addTask(c[_-1],c[_]),this.$="task";break}},"anonymous"),"anonymous"),table:[{3:1,4:[1,2]},{1:[3]},t(e,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:a,12:p,14:r,16:u,17:f,18:o},t(e,[2,7],{1:[2,1]}),t(e,[2,3]),{9:15,11:a,12:p,14:r,16:u,17:f,18:o},t(e,[2,5]),t(e,[2,6]),t(e,[2,8]),{13:[1,16]},{15:[1,17]},t(e,[2,11]),t(e,[2,12]),{19:[1,18]},t(e,[2,4]),t(e,[2,9]),t(e,[2,10]),t(e,[2,13])],defaultActions:{},parseError:s(k(function(i,n){if(n.recoverable)this.trace(i);else{var l=new Error(i);throw l.hash=n,l}},"parseError"),"parseError"),parse:s(k(function(i){var n=this,l=[0],y=[],d=[null],c=[],v=this.table,_="",P=0,et=0,pt=2,rt=1,ft=c.slice.call(arguments,1),b=Object.create(this.lexer),A={yy:{}};for(var Y in this.yy)Object.prototype.hasOwnProperty.call(this.yy,Y)&&(A.yy[Y]=this.yy[Y]);b.setInput(i,A.yy),A.yy.lexer=b,A.yy.parser=this,typeof b.yylloc>"u"&&(b.yylloc={});var q=b.yylloc;c.push(q);var gt=b.options&&b.options.ranges;typeof A.yy.parseError=="function"?this.parseError=A.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function it(T){l.length=l.length-2*T,d.length=d.length-T,c.length=c.length-T}k(it,"popStack"),s(it,"popStack");function X(){var T;return T=y.pop()||b.lex()||rt,typeof T!="number"&&(T instanceof Array&&(y=T,T=y.pop()),T=n.symbols_[T]||T),T}k(X,"lex"),s(X,"lex");for(var w,F,S,G,R={},z,E,nt,W;;){if(F=l[l.length-1],this.defaultActions[F]?S=this.defaultActions[F]:((w===null||typeof w>"u")&&(w=X()),S=v[F]&&v[F][w]),typeof S>"u"||!S.length||!S[0]){var H="";W=[];for(z in v[F])this.terminals_[z]&&z>pt&&W.push("'"+this.terminals_[z]+"'");b.showPosition?H="Parse error on line "+(P+1)+`:
`+b.showPosition()+`
Expecting `+W.join(", ")+", got '"+(this.terminals_[w]||w)+"'":H="Parse error on line "+(P+1)+": Unexpected "+(w==rt?"end of input":"'"+(this.terminals_[w]||w)+"'"),this.parseError(H,{text:b.match,token:this.terminals_[w]||w,line:b.yylineno,loc:q,expected:W})}if(S[0]instanceof Array&&S.length>1)throw new Error("Parse Error: multiple actions possible at state: "+F+", token: "+w);switch(S[0]){case 1:l.push(w),d.push(b.yytext),c.push(b.yylloc),l.push(S[1]),w=null,et=b.yyleng,_=b.yytext,P=b.yylineno,q=b.yylloc;break;case 2:if(E=this.productions_[S[1]][1],R.$=d[d.length-E],R._$={first_line:c[c.length-(E||1)].first_line,last_line:c[c.length-1].last_line,first_column:c[c.length-(E||1)].first_column,last_column:c[c.length-1].last_column},gt&&(R._$.range=[c[c.length-(E||1)].range[0],c[c.length-1].range[1]]),G=this.performAction.apply(R,[_,et,P,A.yy,S[1],d,c].concat(ft)),typeof G<"u")return G;E&&(l=l.slice(0,-1*E*2),d=d.slice(0,-1*E),c=c.slice(0,-1*E)),l.push(this.productions_[S[1]][0]),d.push(R.$),c.push(R._$),nt=v[l[l.length-2]][l[l.length-1]],l.push(nt);break;case 3:return!0}}return!0},"parse"),"parse")},m=function(){var h={EOF:1,parseError:s(k(function(n,l){if(this.yy.parser)this.yy.parser.parseError(n,l);else throw new Error(n)},"parseError"),"parseError"),setInput:s(function(i,n){return this.yy=n||this.yy||{},this._input=i,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:s(function(){var i=this._input[0];this.yytext+=i,this.yyleng++,this.offset++,this.match+=i,this.matched+=i;var n=i.match(/(?:\r\n?|\n).*/g);return n?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),i},"input"),unput:s(function(i){var n=i.length,l=i.split(/(?:\r\n?|\n)/g);this._input=i+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-n),this.offset-=n;var y=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),l.length-1&&(this.yylineno-=l.length-1);var d=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:l?(l.length===y.length?this.yylloc.first_column:0)+y[y.length-l.length].length-l[0].length:this.yylloc.first_column-n},this.options.ranges&&(this.yylloc.range=[d[0],d[0]+this.yyleng-n]),this.yyleng=this.yytext.length,this},"unput"),more:s(function(){return this._more=!0,this},"more"),reject:s(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},"reject"),less:s(function(i){this.unput(this.match.slice(i))},"less"),pastInput:s(function(){var i=this.matched.substr(0,this.matched.length-this.match.length);return(i.length>20?"...":"")+i.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:s(function(){var i=this.match;return i.length<20&&(i+=this._input.substr(0,20-i.length)),(i.substr(0,20)+(i.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:s(function(){var i=this.pastInput(),n=new Array(i.length+1).join("-");return i+this.upcomingInput()+`
`+n+"^"},"showPosition"),test_match:s(function(i,n){var l,y,d;if(this.options.backtrack_lexer&&(d={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(d.yylloc.range=this.yylloc.range.slice(0))),y=i[0].match(/(?:\r\n?|\n).*/g),y&&(this.yylineno+=y.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:y?y[y.length-1].length-y[y.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+i[0].length},this.yytext+=i[0],this.match+=i[0],this.matches=i,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(i[0].length),this.matched+=i[0],l=this.performAction.call(this,this.yy,this,n,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),l)return l;if(this._backtrack){for(var c in d)this[c]=d[c];return!1}return!1},"test_match"),next:s(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var i,n,l,y;this._more||(this.yytext="",this.match="");for(var d=this._currentRules(),c=0;c<d.length;c++)if(l=this._input.match(this.rules[d[c]]),l&&(!n||l[0].length>n[0].length)){if(n=l,y=c,this.options.backtrack_lexer){if(i=this.test_match(l,d[c]),i!==!1)return i;if(this._backtrack){n=!1;continue}else return!1}else if(!this.options.flex)break}return n?(i=this.test_match(n,d[y]),i!==!1?i:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:s(k(function(){var n=this.next();return n||this.lex()},"lex"),"lex"),begin:s(k(function(n){this.conditionStack.push(n)},"begin"),"begin"),popState:s(k(function(){var n=this.conditionStack.length-1;return n>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),"popState"),_currentRules:s(k(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),"_currentRules"),topState:s(k(function(n){return n=this.conditionStack.length-1-Math.abs(n||0),n>=0?this.conditionStack[n]:"INITIAL"},"topState"),"topState"),pushState:s(k(function(n){this.begin(n)},"pushState"),"pushState"),stateStackSize:s(k(function(){return this.conditionStack.length},"stateStackSize"),"stateStackSize"),options:{"case-insensitive":!0},performAction:s(k(function(n,l,y,d){switch(y){case 0:break;case 1:break;case 2:return 10;case 3:break;case 4:break;case 5:return 4;case 6:return 11;case 7:return this.begin("acc_title"),12;case 8:return this.popState(),"acc_title_value";case 9:return this.begin("acc_descr"),14;case 10:return this.popState(),"acc_descr_value";case 11:this.begin("acc_descr_multiline");break;case 12:this.popState();break;case 13:return"acc_descr_multiline_value";case 14:return 17;case 15:return 18;case 16:return 19;case 17:return":";case 18:return 6;case 19:return"INVALID"}},"anonymous"),"anonymous"),rules:[/^(?:%(?!\{)[^\n]*)/i,/^(?:[^\}]%%[^\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:#[^\n]*)/i,/^(?:journey\b)/i,/^(?:title\s[^#\n;]+)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:section\s[^#:\n;]+)/i,/^(?:[^#:\n;]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[12,13],inclusive:!1},acc_descr:{rules:[10],inclusive:!1},acc_title:{rules:[8],inclusive:!1},INITIAL:{rules:[0,1,2,3,4,5,6,7,9,11,14,15,16,17,18,19],inclusive:!0}}};return h}();g.lexer=m;function x(){this.yy={}}return k(x,"Parser"),s(x,"Parser"),x.prototype=g,g.Parser=x,new x}();J.parser=J;var Ct=J,V="",Q=[],B=[],j=[],Pt=s(function(){Q.length=0,B.length=0,V="",j.length=0,Et()},"clear"),It=s(function(t){V=t,Q.push(t)},"addSection"),At=s(function(){return Q},"getSections"),Ft=s(function(){let t=at();const e=100;let a=0;for(;!t&&a<e;)t=at(),a++;return B.push(...j),B},"getTasks"),Rt=s(function(){const t=[];return B.forEach(a=>{a.people&&t.push(...a.people)}),[...new Set(t)].sort()},"updateActors"),Vt=s(function(t,e){const a=e.substr(1).split(":");let p=0,r=[];a.length===1?(p=Number(a[0]),r=[]):(p=Number(a[0]),r=a[1].split(","));const u=r.map(o=>o.trim()),f={section:V,type:V,people:u,task:t,score:p};j.push(f)},"addTask"),Lt=s(function(t){const e={section:V,type:V,description:t,task:t,classes:[]};B.push(e)},"addTaskOrg"),at=s(function(){const t=s(function(a){return j[a].processed},"compileTask");let e=!0;for(const[a,p]of j.entries())t(a),e=e&&p.processed;return e},"compileTasks"),Bt=s(function(){return Rt()},"getActors"),lt={getConfig:s(()=>L().journey,"getConfig"),clear:Pt,setDiagramTitle:$t,getDiagramTitle:St,setAccTitle:Tt,getAccTitle:wt,setAccDescription:vt,getAccDescription:bt,addSection:It,getSections:At,getTasks:Ft,addTask:Vt,addTaskOrg:Lt,getActors:Bt},jt=s(t=>`.label {
    font-family: ${t.fontFamily};
    color: ${t.textColor};
  }
  .mouth {
    stroke: #666;
  }

  line {
    stroke: ${t.textColor}
  }

  .legend {
    fill: ${t.textColor};
    font-family: ${t.fontFamily};
  }

  .label text {
    fill: #333;
  }
  .label {
    color: ${t.textColor}
  }

  .face {
    ${t.faceColor?`fill: ${t.faceColor}`:"fill: #FFF8DC"};
    stroke: #999;
  }

  .node rect,
  .node circle,
  .node ellipse,
  .node polygon,
  .node path {
    fill: ${t.mainBkg};
    stroke: ${t.nodeBorder};
    stroke-width: 1px;
  }

  .node .label {
    text-align: center;
  }
  .node.clickable {
    cursor: pointer;
  }

  .arrowheadPath {
    fill: ${t.arrowheadColor};
  }

  .edgePath .path {
    stroke: ${t.lineColor};
    stroke-width: 1.5px;
  }

  .flowchart-link {
    stroke: ${t.lineColor};
    fill: none;
  }

  .edgeLabel {
    background-color: ${t.edgeLabelBackground};
    rect {
      opacity: 0.5;
    }
    text-align: center;
  }

  .cluster rect {
  }

  .cluster text {
    fill: ${t.titleColor};
  }

  div.mermaidTooltip {
    position: absolute;
    text-align: center;
    max-width: 200px;
    padding: 2px;
    font-family: ${t.fontFamily};
    font-size: 12px;
    background: ${t.tertiaryColor};
    border: 1px solid ${t.border2};
    border-radius: 2px;
    pointer-events: none;
    z-index: 100;
  }

  .task-type-0, .section-type-0  {
    ${t.fillType0?`fill: ${t.fillType0}`:""};
  }
  .task-type-1, .section-type-1  {
    ${t.fillType0?`fill: ${t.fillType1}`:""};
  }
  .task-type-2, .section-type-2  {
    ${t.fillType0?`fill: ${t.fillType2}`:""};
  }
  .task-type-3, .section-type-3  {
    ${t.fillType0?`fill: ${t.fillType3}`:""};
  }
  .task-type-4, .section-type-4  {
    ${t.fillType0?`fill: ${t.fillType4}`:""};
  }
  .task-type-5, .section-type-5  {
    ${t.fillType0?`fill: ${t.fillType5}`:""};
  }
  .task-type-6, .section-type-6  {
    ${t.fillType0?`fill: ${t.fillType6}`:""};
  }
  .task-type-7, .section-type-7  {
    ${t.fillType0?`fill: ${t.fillType7}`:""};
  }

  .actor-0 {
    ${t.actor0?`fill: ${t.actor0}`:""};
  }
  .actor-1 {
    ${t.actor1?`fill: ${t.actor1}`:""};
  }
  .actor-2 {
    ${t.actor2?`fill: ${t.actor2}`:""};
  }
  .actor-3 {
    ${t.actor3?`fill: ${t.actor3}`:""};
  }
  .actor-4 {
    ${t.actor4?`fill: ${t.actor4}`:""};
  }
  .actor-5 {
    ${t.actor5?`fill: ${t.actor5}`:""};
  }
  ${mt()}
`,"getStyles"),Nt=jt,D=s(function(t,e){return _t(t,e)},"drawRect"),zt=s(function(t,e){const p=t.append("circle").attr("cx",e.cx).attr("cy",e.cy).attr("class","face").attr("r",15).attr("stroke-width",2).attr("overflow","visible"),r=t.append("g");r.append("circle").attr("cx",e.cx-15/3).attr("cy",e.cy-15/3).attr("r",1.5).attr("stroke-width",2).attr("fill","#666").attr("stroke","#666"),r.append("circle").attr("cx",e.cx+15/3).attr("cy",e.cy-15/3).attr("r",1.5).attr("stroke-width",2).attr("fill","#666").attr("stroke","#666");function u(g){const m=st().startAngle(Math.PI/2).endAngle(3*(Math.PI/2)).innerRadius(7.5).outerRadius(6.8181818181818175);g.append("path").attr("class","mouth").attr("d",m).attr("transform","translate("+e.cx+","+(e.cy+2)+")")}k(u,"smile"),s(u,"smile");function f(g){const m=st().startAngle(3*Math.PI/2).endAngle(5*(Math.PI/2)).innerRadius(7.5).outerRadius(6.8181818181818175);g.append("path").attr("class","mouth").attr("d",m).attr("transform","translate("+e.cx+","+(e.cy+7)+")")}k(f,"sad"),s(f,"sad");function o(g){g.append("line").attr("class","mouth").attr("stroke",2).attr("x1",e.cx-5).attr("y1",e.cy+7).attr("x2",e.cx+5).attr("y2",e.cy+7).attr("class","mouth").attr("stroke-width","1px").attr("stroke","#666")}return k(o,"ambivalent"),s(o,"ambivalent"),e.score>3?u(r):e.score<3?f(r):o(r),p},"drawFace"),ut=s(function(t,e){const a=t.append("circle");return a.attr("cx",e.cx),a.attr("cy",e.cy),a.attr("class","actor-"+e.pos),a.attr("fill",e.fill),a.attr("stroke",e.stroke),a.attr("r",e.r),a.class!==void 0&&a.attr("class",a.class),e.title!==void 0&&a.append("title").text(e.title),a},"drawCircle"),yt=s(function(t,e){return kt(t,e)},"drawText"),Wt=s(function(t,e){function a(r,u,f,o,g){return r+","+u+" "+(r+f)+","+u+" "+(r+f)+","+(u+o-g)+" "+(r+f-g*1.2)+","+(u+o)+" "+r+","+(u+o)}k(a,"genPoints"),s(a,"genPoints");const p=t.append("polygon");p.attr("points",a(e.x,e.y,50,20,7)),p.attr("class","labelBox"),e.y=e.y+e.labelMargin,e.x=e.x+.5*e.labelMargin,yt(t,e)},"drawLabel"),Ot=s(function(t,e,a){const p=t.append("g"),r=ht();r.x=e.x,r.y=e.y,r.fill=e.fill,r.width=a.width*e.taskCount+a.diagramMarginX*(e.taskCount-1),r.height=a.height,r.class="journey-section section-type-"+e.num,r.rx=3,r.ry=3,D(p,r),dt(a)(e.text,p,r.x,r.y,r.width,r.height,{class:"journey-section section-type-"+e.num},a,e.colour)},"drawSection"),K=-1,Yt=s(function(t,e,a,p){const r=e.x+a.width/2,u=t.append("g");K++;const f=300+5*30;u.append("line").attr("id",p+"-task"+K).attr("x1",r).attr("y1",e.y).attr("x2",r).attr("y2",f).attr("class","task-line").attr("stroke-width","1px").attr("stroke-dasharray","4 2").attr("stroke","#666"),zt(u,{cx:r,cy:300+(5-e.score)*30,score:e.score});const o=ht();o.x=e.x,o.y=e.y,o.fill=e.fill,o.width=a.width,o.height=a.height,o.class="task task-type-"+e.num,o.rx=3,o.ry=3,D(u,o);let g=e.x+14;e.people.forEach(m=>{const x=e.actors[m].color,h={cx:g,cy:e.y,r:7,fill:x,stroke:"#000",title:m,pos:e.actors[m].position};ut(u,h),g+=10}),dt(a)(e.task,u,o.x,o.y,o.width,o.height,{class:"task"},a,e.colour)},"drawTask"),qt=s(function(t,e){xt(t,e)},"drawBackgroundRect"),dt=function(){function t(r,u,f,o,g,m,x,h){const i=u.append("text").attr("x",f+g/2).attr("y",o+m/2+5).style("font-color",h).style("text-anchor","middle").text(r);p(i,x)}k(t,"byText"),s(t,"byText");function e(r,u,f,o,g,m,x,h,i){const{taskFontSize:n,taskFontFamily:l}=h,y=r.split(/<br\s*\/?>/gi);for(let d=0;d<y.length;d++){const c=d*n-n*(y.length-1)/2,v=u.append("text").attr("x",f+g/2).attr("y",o).attr("fill",i).style("text-anchor","middle").style("font-size",n).style("font-family",l);v.append("tspan").attr("x",f+g/2).attr("dy",c).text(y[d]),v.attr("y",o+m/2).attr("dominant-baseline","central").attr("alignment-baseline","central"),p(v,x)}}k(e,"byTspan"),s(e,"byTspan");function a(r,u,f,o,g,m,x,h){const i=u.append("switch"),l=i.append("foreignObject").attr("x",f).attr("y",o).attr("width",g).attr("height",m).attr("position","fixed").append("xhtml:div").style("display","table").style("height","100%").style("width","100%");l.append("div").attr("class","label").style("display","table-cell").style("text-align","center").style("vertical-align","middle").text(r),e(r,i,f,o,g,m,x,h),p(l,x)}k(a,"byFo"),s(a,"byFo");function p(r,u){for(const f in u)f in u&&r.attr(f,u[f])}return k(p,"_setTextAttrs"),s(p,"_setTextAttrs"),function(r){return r.textPlacement==="fo"?a:r.textPlacement==="old"?t:e}}(),Xt=s(function(t,e){K=-1,t.append("defs").append("marker").attr("id",e+"-arrowhead").attr("refX",5).attr("refY",2).attr("markerWidth",6).attr("markerHeight",4).attr("orient","auto").append("path").attr("d","M 0,0 V 4 L6,2 Z")},"initGraphics"),N={drawRect:D,drawCircle:ut,drawSection:Ot,drawText:yt,drawLabel:Wt,drawTask:Yt,drawBackgroundRect:qt,initGraphics:Xt},Gt=s(function(t){Object.keys(t).forEach(function(a){M[a]=t[a]})},"setConf"),C={},O=0;function tt(t){const e=L().journey,a=e.maxLabelWidth;O=0;let p=60;Object.keys(C).forEach(r=>{const u=C[r].color,f={cx:20,cy:p,r:7,fill:u,stroke:"#000",pos:C[r].position};N.drawCircle(t,f);let o=t.append("text").attr("visibility","hidden").text(r);const g=o.node().getBoundingClientRect().width;o.remove();let m=[];if(g<=a)m=[r];else{const x=r.split(" ");let h="";o=t.append("text").attr("visibility","hidden"),x.forEach(i=>{const n=h?`${h} ${i}`:i;if(o.text(n),o.node().getBoundingClientRect().width>a){if(h&&m.push(h),h=i,o.text(i),o.node().getBoundingClientRect().width>a){let y="";for(const d of i)y+=d,o.text(y+"-"),o.node().getBoundingClientRect().width>a&&(m.push(y.slice(0,-1)+"-"),y=d);h=y}}else h=n}),h&&m.push(h),o.remove()}m.forEach((x,h)=>{const i={x:40,y:p+7+h*20,fill:"#666",text:x,textMargin:e.boxTextMargin??5},l=N.drawText(t,i).node().getBoundingClientRect().width;l>O&&l>e.leftMargin-l&&(O=l)}),p+=Math.max(20,m.length*20)})}k(tt,"drawActorLegend");s(tt,"drawActorLegend");var M=L().journey,I=0,Ht=s(function(t,e,a,p){const r=L(),u=r.journey.titleColor,f=r.journey.titleFontSize,o=r.journey.titleFontFamily,g=r.securityLevel;let m;g==="sandbox"&&(m=U("#i"+e));const x=g==="sandbox"?U(m.nodes()[0].contentDocument.body):U("body");$.init();const h=x.select("#"+e);N.initGraphics(h,e);const i=p.db.getTasks(),n=p.db.getDiagramTitle(),l=p.db.getActors();for(const P in C)delete C[P];let y=0;l.forEach(P=>{C[P]={color:M.actorColours[y%M.actorColours.length],position:y},y++}),tt(h),I=M.leftMargin+O,$.insert(0,0,I,Object.keys(C).length*50),Ut(h,i,0,e);const d=$.getBounds();n&&h.append("text").text(n).attr("x",I).attr("font-size",f).attr("font-weight","bold").attr("y",25).attr("fill",u).attr("font-family",o);const c=d.stopy-d.starty+2*M.diagramMarginY,v=I+d.stopx+2*M.diagramMarginX;Mt(h,c,v,M.useMaxWidth),h.append("line").attr("x1",I).attr("y1",M.height*4).attr("x2",v-I-4).attr("y2",M.height*4).attr("stroke-width",4).attr("stroke","black").attr("marker-end","url(#"+e+"-arrowhead)");const _=n?70:0;h.attr("viewBox",`${d.startx} -25 ${v} ${c+_}`),h.attr("preserveAspectRatio","xMinYMin meet"),h.attr("height",c+_+25)},"draw"),$={data:{startx:void 0,stopx:void 0,starty:void 0,stopy:void 0},verticalPos:0,sequenceItems:[],init:s(function(){this.sequenceItems=[],this.data={startx:void 0,stopx:void 0,starty:void 0,stopy:void 0},this.verticalPos=0},"init"),updateVal:s(function(t,e,a,p){t[e]===void 0?t[e]=a:t[e]=p(a,t[e])},"updateVal"),updateBounds:s(function(t,e,a,p){const r=L().journey,u=this;let f=0;function o(g){return s(k(function(x){f++;const h=u.sequenceItems.length-f+1;u.updateVal(x,"starty",e-h*r.boxMargin,Math.min),u.updateVal(x,"stopy",p+h*r.boxMargin,Math.max),u.updateVal($.data,"startx",t-h*r.boxMargin,Math.min),u.updateVal($.data,"stopx",a+h*r.boxMargin,Math.max),g!=="activation"&&(u.updateVal(x,"startx",t-h*r.boxMargin,Math.min),u.updateVal(x,"stopx",a+h*r.boxMargin,Math.max),u.updateVal($.data,"starty",e-h*r.boxMargin,Math.min),u.updateVal($.data,"stopy",p+h*r.boxMargin,Math.max))},"updateItemBounds"),"updateItemBounds")}k(o,"updateFn"),s(o,"updateFn"),this.sequenceItems.forEach(o())},"updateBounds"),insert:s(function(t,e,a,p){const r=Math.min(t,a),u=Math.max(t,a),f=Math.min(e,p),o=Math.max(e,p);this.updateVal($.data,"startx",r,Math.min),this.updateVal($.data,"starty",f,Math.min),this.updateVal($.data,"stopx",u,Math.max),this.updateVal($.data,"stopy",o,Math.max),this.updateBounds(r,f,u,o)},"insert"),bumpVerticalPos:s(function(t){this.verticalPos=this.verticalPos+t,this.data.stopy=this.verticalPos},"bumpVerticalPos"),getVerticalPos:s(function(){return this.verticalPos},"getVerticalPos"),getBounds:s(function(){return this.data},"getBounds")},Z=M.sectionFills,ot=M.sectionColours,Ut=s(function(t,e,a,p){const r=L().journey;let u="";const f=r.height*2+r.diagramMarginY,o=a+f;let g=0,m="#CCC",x="black",h=0;for(const[i,n]of e.entries()){if(u!==n.section){m=Z[g%Z.length],h=g%Z.length,x=ot[g%ot.length];let y=0;const d=n.section;for(let v=i;v<e.length&&e[v].section==d;v++)y=y+1;const c={x:i*r.taskMargin+i*r.width+I,y:50,text:n.section,fill:m,num:h,colour:x,taskCount:y};N.drawSection(t,c,r),u=n.section,g++}const l=n.people.reduce((y,d)=>(C[d]&&(y[d]=C[d]),y),{});n.x=i*r.taskMargin+i*r.width+I,n.y=o,n.width=r.diagramMarginX,n.height=r.diagramMarginY,n.colour=x,n.fill=m,n.num=h,n.actors=l,N.drawTask(t,n,r,p),$.insert(n.x,n.y,n.x+n.width+r.taskMargin,300+5*30)}},"drawTasks"),ct={setConf:Gt,draw:Ht},re={parser:Ct,db:lt,renderer:ct,styles:Nt,init:s(t=>{ct.setConf(t.journey),lt.clear()},"init")};export{re as diagram};
