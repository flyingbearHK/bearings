import{p as xt}from"./chunk-VII2H2IX-442OLPBc.js";import{p as $t}from"./cynefin-OW5HDTMX-GVF3BKWE-D0vrl6vC.js";import{s as bt,g as Ct,o as wt,n as vt,a as Dt,b as kt,_ as s,l as X,G as At,d as Tt,p as Bt,C as Q,A as Z,D as St,I as ft}from"./render-O7CIS3YK-CNcZ7P9o.js";import{_ as N}from"./mermaid-layout-elk.core-CNKA6qqL.js";import"./index-CQqDpKBO.js";import"./transform-Ck8scYFu.js";var mt=s(()=>({domains:new Map,transitions:[]}),"createDefaultData"),G=mt(),Mt=s(()=>G.domains,"getDomains"),zt=s(()=>G.transitions,"getTransitions"),Pt=s(t=>{if(t)for(const e of t){const n=e.domain,a=(e.items??[]).map(c=>({label:c.label}));G.domains.set(n,{name:n,items:a})}},"setDomains"),Lt=s(t=>{t&&(G.transitions=t.filter(e=>e.from===e.to?(X.warn(`Cynefin: self-loop transition on domain "${e.from}" is not meaningful and will be skipped.`),!1):!0).map(e=>({from:e.from,to:e.to,label:e.label||void 0})))},"setTransitions"),_t=s(()=>Q({...St.cynefin,...Z().cynefin}),"getConfig"),It=s(()=>{Bt(),G=mt()},"clear"),O={getDomains:Mt,getTransitions:zt,setDomains:Pt,setTransitions:Lt,getConfig:_t,clear:It,setAccTitle:kt,getAccTitle:Dt,setDiagramTitle:vt,getDiagramTitle:wt,getAccDescription:Ct,setAccDescription:bt},Nt=s(t=>{xt(t,O),O.setDomains(t.domains),O.setTransitions(t.transitions)},"populate"),Rt={parse:s(async t=>{const e=await $t("cynefin",t);X.debug(e),Nt(e)},"parse")};function E(t){let e=t+1831565813|0;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}N(E,"seededRandom");s(E,"seededRandom");function J(t){let e=0;for(let n=0;n<t.length;n++){const a=t.charCodeAt(n);e=(e<<5)-e+a,e|=0}return e}N(J,"hashString");s(J,"hashString");function K(t,e){return typeof t=="number"&&Number.isFinite(t)&&t!==0?t:J(e)}N(K,"resolveSeed");s(K,"resolveSeed");function tt(t,e,n,a){const c=t/2,m=a??t*.015,v=7,R=e/v,d=[];for(let o=0;o<=v;o++){const p=E(n+o*17)*m*2-m;d.push({x:c+p,y:o*R})}let D=`M${d[0].x},${d[0].y}`;for(let o=0;o<d.length-1;o++){const p=d[o],i=d[o+1],f=(p.y+i.y)/2,b=o%2===0?1:-1,h=m*1.5*b*E(n+o*31+7),W=p.x+h,F=f,H=i.x-h;D+=` C${W},${F} ${H},${f} ${i.x},${i.y}`}return D}N(tt,"generateFoldPath");s(tt,"generateFoldPath");function et(t,e,n,a){const c=e/2,m=a??e*.015,v=7,R=t/v,d=[];for(let o=0;o<=v;o++){const p=E(n+o*23)*m*2-m;d.push({x:o*R,y:c+p})}let D=`M${d[0].x},${d[0].y}`;for(let o=0;o<d.length-1;o++){const p=d[o],i=d[o+1],f=(p.x+i.x)/2,b=o%2===0?1:-1,h=m*1.5*b*E(n+o*37+11),W=f,F=p.y+h,H=f,z=i.y-h;D+=` C${W},${F} ${H},${z} ${i.x},${i.y}`}return D}N(et,"generateHorizontalBoundary");s(et,"generateHorizontalBoundary");function nt(t,e){const n=t/2,a=e*.5,c=e,m=t*.03;return[`M${n},${a}`,`C${n+m},${a+(c-a)*.2}`,`${n-m*1.5},${a+(c-a)*.55}`,`${n+m*.5},${a+(c-a)*.75}`,`C${n-m},${a+(c-a)*.85}`,`${n+m*.3},${a+(c-a)*.95}`,`${n},${c}`].join(" ")}N(nt,"generateCliffPath");s(nt,"generateCliffPath");function at(t,e,n,a){return[`M${t-n},${e}`,`A${n},${a} 0 1,1 ${t+n},${e}`,`A${n},${a} 0 1,1 ${t-n},${e}`,"Z"].join(" ")}N(at,"generateConfusionPath");s(at,"generateConfusionPath");var dt={complex:{model:"Probe → Sense → Respond",practice:"Emergent Practices"},complicated:{model:"Sense → Analyse → Respond",practice:"Good Practices"},clear:{model:"Sense → Categorise → Respond",practice:"Best Practices"},chaotic:{model:"Act → Sense → Respond",practice:"Novel Practices"},confusion:{model:"",practice:"Disorder"}},Wt=s((t,e)=>{const n=t/2,a=e/2;return{complex:{cx:n/2,cy:a/2,x:0,y:0,w:n,h:a},complicated:{cx:n+n/2,cy:a/2,x:n,y:0,w:n,h:a},chaotic:{cx:n/2,cy:a+a/2,x:0,y:a,w:n,h:a},clear:{cx:n+n/2,cy:a+a/2,x:n,y:a,w:n,h:a},confusion:{cx:n,cy:a,x:n*.7,y:a*.7,w:n*.6,h:a*.6}}},"getDomainLayouts"),Ft=s(()=>{const t=ft(),e=Z();return Q(t,e.themeVariables).cynefin},"getCynefinDomainColors"),U=3,Ht=s((t,e,n,a)=>{const c=a.db,m=c.getDomains(),v=c.getTransitions(),R=c.getDiagramTitle(),d=c.getAccTitle(),D=c.getAccDescription(),o=c.getConfig(),p=Ft();X.debug("Rendering Cynefin diagram");const i=o.width,f=o.height,b=o.padding,h=o.showDomainDescriptions,W=o.boundaryAmplitude,F=i+b*2,H=f+b*2,z={complex:p.complexBg,complicated:p.complicatedBg,clear:p.clearBg,chaotic:p.chaoticBg,confusion:p.confusionBg},k=At(e);Tt(k,H,F,o.useMaxWidth??!0),k.attr("viewBox",`0 0 ${F} ${H}`),d&&k.append("title").text(d),D&&k.append("desc").text(D);const A=k.append("g").attr("transform",`translate(${b}, ${b})`),V=Wt(i,f),ot=K(o.seed,e),pt=A.append("g").attr("class","cynefin-backgrounds"),j=["complex","complicated","chaotic","clear"];for(const l of j){const r=V[l];pt.append("rect").attr("class","cynefinDomain").attr("x",r.x).attr("y",r.y).attr("width",r.w).attr("height",r.h).attr("fill",z[l]).attr("fill-opacity",.4).attr("stroke","none")}const q=A.append("g").attr("class","cynefin-boundaries");q.append("path").attr("class","cynefinBoundary").attr("d",tt(i,f,ot,W)).attr("fill","none"),q.append("path").attr("class","cynefinBoundary").attr("d",et(i,f,ot+100,W)).attr("fill","none"),q.append("path").attr("class","cynefinCliff").attr("d",nt(i,f)).attr("fill","none");const yt=i*.15,ut=f*.15;A.append("path").attr("class","cynefinConfusion").attr("d",at(i/2,f/2,yt,ut)).attr("fill",z.confusion).attr("fill-opacity",.5);const rt=A.append("g").attr("class","cynefin-labels");for(const l of j){const r=V[l];rt.append("text").attr("class","cynefinDomainLabel").attr("x",r.cx).attr("y",h?r.cy-30:r.cy).attr("text-anchor","middle").attr("dominant-baseline","middle").text(l.charAt(0).toUpperCase()+l.slice(1))}if(rt.append("text").attr("class","cynefinDomainLabel").attr("x",i/2).attr("y",h?f/2-10:f/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text("Confusion"),h){const l=A.append("g").attr("class","cynefin-subtitles");for(const r of j){const u=V[r],y=dt[r];l.append("text").attr("class","cynefinSubtitle").attr("x",u.cx).attr("y",u.cy-10).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.model),l.append("text").attr("class","cynefinSubtitle").attr("x",u.cx).attr("y",u.cy+5).attr("text-anchor","middle").attr("dominant-baseline","middle").text(y.practice)}l.append("text").attr("class","cynefinSubtitle").attr("x",i/2).attr("y",f/2+8).attr("text-anchor","middle").attr("dominant-baseline","middle").text(dt.confusion.practice)}const st=A.append("g").attr("class","cynefin-items"),T=26,it=10,ht=["complex","complicated","chaotic","clear","confusion"];for(const l of ht){const r=m.get(l);if(!r||r.items.length===0)continue;const u=V[l],y=l==="confusion";let P=r.items,L=0;y&&r.items.length>U&&(L=r.items.length-U,P=r.items.slice(0,U));let B;if(y){const x=h?22:14;B=u.cy+x}else B=u.cy+(h?25:15);if([...P].forEach((x,S)=>{const C=B+S*(T+4),M=st.append("g"),_=M.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",T/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(x.label);let $=x.label.length*7;const g=_.node();if(g&&typeof g.getBBox=="function"){const Y=g.getBBox();Y.width>0&&($=Y.width)}const w=$+it*2,I=u.cx-w/2;M.attr("transform",`translate(${I}, ${C})`),M.insert("rect","text").attr("class","cynefinItem").attr("x",0).attr("y",0).attr("width",w).attr("height",T).attr("rx",4).attr("ry",4).attr("fill",z[l]).attr("fill-opacity",.95),_.attr("x",w/2).attr("y",T/2)}),L>0){const x=B+P.length*(T+4),S=`+${L} more`,C=st.append("g"),M=C.append("text").attr("class","cynefinItemText").attr("x",0).attr("y",T/2).attr("text-anchor","middle").attr("dominant-baseline","central").text(S);let _=S.length*7;const $=M.node();if($&&typeof $.getBBox=="function"){const I=$.getBBox();I.width>0&&(_=I.width)}const g=_+it*2,w=u.cx-g/2;C.attr("transform",`translate(${w}, ${x})`),C.insert("rect","text").attr("class","cynefinItemOverflow").attr("x",0).attr("y",0).attr("width",g).attr("height",T).attr("rx",4).attr("ry",4).attr("fill",z[l]).attr("fill-opacity",.6),M.attr("x",g/2).attr("y",T/2)}}if(v.length>0){const l=k.select("defs").empty()?k.append("defs"):k.select("defs"),r=`cynefin-arrow-${e}`;l.append("marker").attr("id",r).attr("viewBox","0 0 10 10").attr("refX",9).attr("refY",5).attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto-start-reverse").append("path").attr("d","M 0 0 L 10 5 L 0 10 z").attr("class","cynefinArrowHead");const u=A.append("g").attr("class","cynefin-arrows");v.forEach(y=>{const P=V[y.from],L=V[y.to];if(!P||!L)return;if(y.from===y.to){X.warn(`Cynefin renderer: skipping self-loop on domain "${y.from}"`);return}const B=P.cx,x=P.cy,S=L.cx,C=L.cy,M=(B+S)/2,_=(x+C)/2,$=S-B,g=C-x,w=Math.sqrt($*$+g*g),I=w*.15,Y=-g/w,gt=$/w,ct=M+Y*I,lt=_+gt*I;u.append("path").attr("class","cynefinArrowLine").attr("d",`M${B},${x} Q${ct},${lt} ${S},${C}`).attr("fill","none").attr("marker-end",`url(#${r})`),y.label&&u.append("text").attr("class","cynefinArrowLabel").attr("x",ct).attr("y",lt-6).attr("text-anchor","middle").attr("dominant-baseline","auto").text(y.label)})}R&&A.append("text").attr("class","cynefinTitle").attr("x",i/2).attr("y",-b/2).attr("text-anchor","middle").attr("dominant-baseline","middle").text(R)},"draw"),Vt={draw:Ht},Et=s(()=>{const t=ft(),e=Z();return Q(t,e.themeVariables).cynefin},"getCynefinTheme"),Gt=s(()=>{const t=Et();return`
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
	`},"styles"),Yt=Gt,Zt={parser:Rt,db:O,renderer:Vt,styles:Yt};export{Zt as diagram};
