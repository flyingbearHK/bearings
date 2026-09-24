import{g as de,s as fe,o as he,n as me,a as ke,b as ye,_ as l,c as mt,d as ge,l as lt,i as pe,p as ve,F as ee,r as Te,z as xe}from"./render-O7CIS3YK-DVdUWRs5.js";import{_ as Y,a as ut,b as Ct}from"./mermaid-layout-elk.core-p257D0Dx.js";import{s as bt}from"./transform-Ck8scYFu.js";import{t as be,m as we,a as _e,i as De,b as Se,c as Bt,d as qt,e as Ce,f as Me,g as Ee,h as Ie,j as Ye,k as $e,l as Le,n as Gt,o as Xt,p as Ut,s as Zt,q as Qt,r as Fe}from"./time-Cfq2UDNX.js";import{l as Ae}from"./linear-BwQBVMVp.js";import"./index-ct4Tt_dp.js";import"./init-Gi6I4Gst.js";import"./defaultLocale-5voVPcsN.js";var Oe=Ct({"../../node_modules/.pnpm/dayjs@1.11.21/node_modules/dayjs/plugin/isoWeek.js"(t,s){(function(i,e){typeof t=="object"&&typeof s<"u"?s.exports=e():typeof define=="function"&&define.amd?define(e):(i=typeof globalThis<"u"?globalThis:i||self).dayjs_plugin_isoWeek=e()})(t,function(){var i="day";return function(e,a,g){var p=Y(function(A){return A.add(4-A.isoWeekday(),i)},"a"),b=a.prototype;b.isoWeekYear=function(){return p(this).year()},b.isoWeek=function(A){if(!this.$utils().u(A))return this.add(7*(A-this.isoWeek()),i);var w,V,O,z,U=p(this),N=(w=this.isoWeekYear(),V=this.$u,O=(V?g.utc:g)().year(w).startOf("year"),z=4-O.isoWeekday(),O.isoWeekday()>4&&(z+=7),O.add(z,i));return U.diff(N,"week")+1},b.isoWeekday=function(A){return this.$utils().u(A)?this.day()||7:this.day(this.day()%7?A:A-7)};var F=b.startOf;b.startOf=function(A,w){var V=this.$utils(),O=!!V.u(w)||w;return V.p(A)==="isoweek"?O?this.date(this.date()-(this.isoWeekday()-1)).startOf("day"):this.date(this.date()-1-(this.isoWeekday()-1)+7).endOf("day"):F.bind(this)(A,w)}}})}}),We=Ct({"../../node_modules/.pnpm/dayjs@1.11.21/node_modules/dayjs/plugin/customParseFormat.js"(t,s){(function(i,e){typeof t=="object"&&typeof s<"u"?s.exports=e():typeof define=="function"&&define.amd?define(e):(i=typeof globalThis<"u"?globalThis:i||self).dayjs_plugin_customParseFormat=e()})(t,function(){var i={LTS:"h:mm:ss A",LT:"h:mm A",L:"MM/DD/YYYY",LL:"MMMM D, YYYY",LLL:"MMMM D, YYYY h:mm A",LLLL:"dddd, MMMM D, YYYY h:mm A"},e=/(\[[^[]*\])|([-_:/.,()\s]+)|(A|a|Q|YYYY|YY?|ww?|MM?M?M?|Do|DD?|hh?|HH?|mm?|ss?|S{1,3}|z|ZZ?)/g,a=/\d/,g=/\d\d/,p=/\d\d?/,b=/\d*[^-_:/,()\s\d]+/,F={},A=Y(function(k){return(k=+k)+(k>68?1900:2e3)},"a"),w=Y(function(k){return function(D){this[k]=+D}},"f"),V=[/[+-]\d\d:?(\d\d)?|Z/,function(k){(this.zone||(this.zone={})).offset=function(D){if(!D||D==="Z")return 0;var W=D.match(/([+-]|\d\d)/g),L=60*W[1]+(+W[2]||0);return L===0?0:W[0]==="+"?-L:L}(k)}],O=Y(function(k){var D=F[k];return D&&(D.indexOf?D:D.s.concat(D.f))},"u"),z=Y(function(k,D){var W,L=F.meridiem;if(L){for(var q=1;q<=24;q+=1)if(k.indexOf(L(q,0,D))>-1){W=q>12;break}}else W=k===(D?"pm":"PM");return W},"d"),U={A:[b,function(k){this.afternoon=z(k,!1)}],a:[b,function(k){this.afternoon=z(k,!0)}],Q:[a,function(k){this.month=3*(k-1)+1}],S:[a,function(k){this.milliseconds=100*+k}],SS:[g,function(k){this.milliseconds=10*+k}],SSS:[/\d{3}/,function(k){this.milliseconds=+k}],s:[p,w("seconds")],ss:[p,w("seconds")],m:[p,w("minutes")],mm:[p,w("minutes")],H:[p,w("hours")],h:[p,w("hours")],HH:[p,w("hours")],hh:[p,w("hours")],D:[p,w("day")],DD:[g,w("day")],Do:[b,function(k){var D=F.ordinal,W=k.match(/\d+/);if(this.day=W[0],D)for(var L=1;L<=31;L+=1)D(L).replace(/\[|\]/g,"")===k&&(this.day=L)}],w:[p,w("week")],ww:[g,w("week")],M:[p,w("month")],MM:[g,w("month")],MMM:[b,function(k){var D=O("months"),W=(O("monthsShort")||D.map(function(L){return L.slice(0,3)})).indexOf(k)+1;if(W<1)throw new Error;this.month=W%12||W}],MMMM:[b,function(k){var D=O("months").indexOf(k)+1;if(D<1)throw new Error;this.month=D%12||D}],Y:[/[+-]?\d+/,w("year")],YY:[g,function(k){this.year=A(k)}],YYYY:[/\d{4}/,w("year")],Z:V,ZZ:V};function N(k){var D,W;D=k,W=F&&F.formats;for(var L=(k=D.replace(/(\[[^\]]+])|(LTS?|l{1,4}|L{1,4})/g,function(m,T,v){var y=v&&v.toUpperCase();return T||W[v]||i[v]||W[y].replace(/(\[[^\]]+])|(MMMM|MM|DD|dddd)/g,function(r,d,f){return d||f.slice(1)})})).match(e),q=L.length,B=0;B<q;B+=1){var $=L[B],x=U[$],h=x&&x[0],I=x&&x[1];L[B]=I?{regex:h,parser:I}:$.replace(/^\[|\]$/g,"")}return function(m){for(var T={},v=0,y=0;v<q;v+=1){var r=L[v];if(typeof r=="string")y+=r.length;else{var d=r.regex,f=r.parser,u=m.slice(y),_=d.exec(u)[0];f.call(T,_),m=m.replace(_,"")}}return function(n){var S=n.afternoon;if(S!==void 0){var o=n.hours;S?o<12&&(n.hours+=12):o===12&&(n.hours=0),delete n.afternoon}}(T),T}}return Y(N,"l"),function(k,D,W){W.p.customParseFormat=!0,k&&k.parseTwoDigitYear&&(A=k.parseTwoDigitYear);var L=D.prototype,q=L.parse;L.parse=function(B){var $=B.date,x=B.utc,h=B.args;this.$u=x;var I=h[1];if(typeof I=="string"){var m=h[2]===!0,T=h[3]===!0,v=m||T,y=h[2];T&&(y=h[2]),F=this.$locale(),!m&&y&&(F=W.Ls[y]),this.$d=function(u,_,n,S){try{if(["x","X"].indexOf(_)>-1)return new Date((_==="X"?1e3:1)*u);var o=N(_)(u),H=o.year,c=o.month,C=o.day,M=o.hours,R=o.minutes,E=o.seconds,j=o.milliseconds,P=o.zone,nt=o.week,at=new Date,ft=C||(H||c?1:at.getDate()),ot=H||at.getFullYear(),G=0;H&&!c||(G=c>0?c-1:at.getMonth());var J,Z=M||0,ct=R||0,tt=E||0,rt=j||0;return P?new Date(Date.UTC(ot,G,ft,Z,ct,tt,rt+60*P.offset*1e3)):n?new Date(Date.UTC(ot,G,ft,Z,ct,tt,rt)):(J=new Date(ot,G,ft,Z,ct,tt,rt),nt&&(J=S(J).week(nt).toDate()),J)}catch{return new Date("")}}($,I,x,W),this.init(),y&&y!==!0&&(this.$L=this.locale(y).$L),v&&$!=this.format(I)&&(this.$d=new Date("")),F={}}else if(I instanceof Array)for(var r=I.length,d=1;d<=r;d+=1){h[1]=I[d-1];var f=W.apply(this,h);if(f.isValid()){this.$d=f.$d,this.$L=f.$L,this.init();break}d===r&&(this.$d=new Date(""))}else q.call(this,B)}}})}}),Pe=Ct({"../../node_modules/.pnpm/dayjs@1.11.21/node_modules/dayjs/plugin/advancedFormat.js"(t,s){(function(i,e){typeof t=="object"&&typeof s<"u"?s.exports=e():typeof define=="function"&&define.amd?define(e):(i=typeof globalThis<"u"?globalThis:i||self).dayjs_plugin_advancedFormat=e()})(t,function(){return function(i,e){var a=e.prototype,g=a.format;a.format=function(p){var b=this,F=this.$locale();if(!this.isValid())return g.bind(this)(p);var A=this.$utils(),w=(p||"YYYY-MM-DDTHH:mm:ssZ").replace(/\[([^\]]+)]|Q|wo|ww|w|WW|W|zzz|z|gggg|GGGG|Do|X|x|k{1,2}|S/g,function(V){switch(V){case"Q":return Math.ceil((b.$M+1)/3);case"Do":return F.ordinal(b.$D);case"gggg":return b.weekYear();case"GGGG":return b.isoWeekYear();case"wo":return F.ordinal(b.week(),"W");case"w":case"ww":return A.s(b.week(),V==="w"?1:2,"0");case"W":case"WW":return A.s(b.isoWeek(),V==="W"?1:2,"0");case"k":case"kk":return A.s(String(b.$H===0?24:b.$H),V==="k"?1:2,"0");case"X":return Math.floor(b.$d.getTime()/1e3);case"x":return b.$d.getTime();case"z":return"["+b.offsetName()+"]";case"zzz":return"["+b.offsetName("long")+"]";default:return V}});return g.bind(this)(w)}}})}}),Ve=Ct({"../../node_modules/.pnpm/dayjs@1.11.21/node_modules/dayjs/plugin/duration.js"(t,s){(function(i,e){typeof t=="object"&&typeof s<"u"?s.exports=e():typeof define=="function"&&define.amd?define(e):(i=typeof globalThis<"u"?globalThis:i||self).dayjs_plugin_duration=e()})(t,function(){var i,e,a=1e3,g=6e4,p=36e5,b=864e5,F=31536e6,A=2628e6,w=/^(-|\+)?P(?:([-+]?[0-9,.]*)Y)?(?:([-+]?[0-9,.]*)M)?(?:([-+]?[0-9,.]*)W)?(?:([-+]?[0-9,.]*)D)?(?:T(?:([-+]?[0-9,.]*)H)?(?:([-+]?[0-9,.]*)M)?(?:([-+]?[0-9,.]*)S)?)?$/,V=/\[([^\]]+)]|YYYY|YY|Y|M{1,2}|D{1,2}|H{1,2}|m{1,2}|s{1,2}|SSS/g,O={years:F,months:A,days:b,hours:p,minutes:g,seconds:a,milliseconds:1,weeks:6048e5},z=Y(function($){return $ instanceof q},"c"),U=Y(function($,x,h){return new q($,h,x.$l)},"f"),N=Y(function($){return e.p($)+"s"},"m"),k=Y(function($){return $<0},"l"),D=Y(function($){return k($)?Math.ceil($):Math.floor($)},"$"),W=Y(function($){return Math.abs($)},"y"),L=Y(function($,x){return $?k($)?{negative:!0,format:""+W($)+x}:{negative:!1,format:""+$+x}:{negative:!1,format:""}},"v"),q=function(){function $(h,I,m){var T=this;if(this.$d={},this.$l=m,h===void 0&&(this.$ms=0,this.parseFromMilliseconds()),I)return U(h*O[N(I)],this);if(typeof h=="number")return this.$ms=h,this.parseFromMilliseconds(),this;if(typeof h=="object")return Object.keys(h).forEach(function(r){T.$d[N(r)]=h[r]}),this.calMilliseconds(),this;if(typeof h=="string"){var v=h.match(w);if(v){var y=v.slice(2).map(function(r){return r!=null?Number(r):0});return this.$d.years=y[0],this.$d.months=y[1],this.$d.weeks=y[2],this.$d.days=y[3],this.$d.hours=y[4],this.$d.minutes=y[5],this.$d.seconds=y[6],this.calMilliseconds(),this}}return this}Y($,"l");var x=$.prototype;return x.calMilliseconds=function(){var h=this;this.$ms=Object.keys(this.$d).reduce(function(I,m){return I+(h.$d[m]||0)*O[m]},0)},x.parseFromMilliseconds=function(){var h=this.$ms;this.$d.years=D(h/F),h%=F,this.$d.months=D(h/A),h%=A,this.$d.days=D(h/b),h%=b,this.$d.hours=D(h/p),h%=p,this.$d.minutes=D(h/g),h%=g,this.$d.seconds=D(h/a),h%=a,this.$d.milliseconds=h},x.toISOString=function(){var h=L(this.$d.years,"Y"),I=L(this.$d.months,"M"),m=+this.$d.days||0;this.$d.weeks&&(m+=7*this.$d.weeks);var T=L(m,"D"),v=L(this.$d.hours,"H"),y=L(this.$d.minutes,"M"),r=this.$d.seconds||0;this.$d.milliseconds&&(r+=this.$d.milliseconds/1e3,r=Math.round(1e3*r)/1e3);var d=L(r,"S"),f=h.negative||I.negative||T.negative||v.negative||y.negative||d.negative,u=v.format||y.format||d.format?"T":"",_=(f?"-":"")+"P"+h.format+I.format+T.format+u+v.format+y.format+d.format;return _==="P"||_==="-P"?"P0D":_},x.toJSON=function(){return this.toISOString()},x.format=function(h){var I=h||"YYYY-MM-DDTHH:mm:ss",m={Y:this.$d.years,YY:e.s(this.$d.years,2,"0"),YYYY:e.s(this.$d.years,4,"0"),M:this.$d.months,MM:e.s(this.$d.months,2,"0"),D:this.$d.days,DD:e.s(this.$d.days,2,"0"),H:this.$d.hours,HH:e.s(this.$d.hours,2,"0"),m:this.$d.minutes,mm:e.s(this.$d.minutes,2,"0"),s:this.$d.seconds,ss:e.s(this.$d.seconds,2,"0"),SSS:e.s(this.$d.milliseconds,3,"0")};return I.replace(V,function(T,v){return v||String(m[T])})},x.as=function(h){return this.$ms/O[N(h)]},x.get=function(h){var I=this.$ms,m=N(h);return m==="milliseconds"?I%=1e3:I=m==="weeks"?D(I/O[m]):this.$d[m],I||0},x.add=function(h,I,m){var T;return T=I?h*O[N(I)]:z(h)?h.$ms:U(h,this).$ms,U(this.$ms+T*(m?-1:1),this)},x.subtract=function(h,I){return this.add(h,I,!0)},x.locale=function(h){var I=this.clone();return I.$l=h,I},x.clone=function(){return U(this.$ms,this)},x.humanize=function(h){return i().add(this.$ms,"ms").locale(this.$l).fromNow(!h)},x.valueOf=function(){return this.asMilliseconds()},x.milliseconds=function(){return this.get("milliseconds")},x.asMilliseconds=function(){return this.as("milliseconds")},x.seconds=function(){return this.get("seconds")},x.asSeconds=function(){return this.as("seconds")},x.minutes=function(){return this.get("minutes")},x.asMinutes=function(){return this.as("minutes")},x.hours=function(){return this.get("hours")},x.asHours=function(){return this.as("hours")},x.days=function(){return this.get("days")},x.asDays=function(){return this.as("days")},x.weeks=function(){return this.get("weeks")},x.asWeeks=function(){return this.as("weeks")},x.months=function(){return this.get("months")},x.asMonths=function(){return this.as("months")},x.years=function(){return this.get("years")},x.asYears=function(){return this.as("years")},$}(),B=Y(function($,x,h){return $.add(x.years()*h,"y").add(x.months()*h,"M").add(x.days()*h,"d").add(x.hours()*h,"h").add(x.minutes()*h,"m").add(x.seconds()*h,"s").add(x.milliseconds()*h,"ms")},"p");return function($,x,h){i=h,e=h().$utils(),h.duration=function(T,v){var y=h.locale();return U(T,{$l:y},v)},h.isDuration=z;var I=x.prototype.add,m=x.prototype.subtract;x.prototype.add=function(T,v){return z(T)?B(this,T,1):I.bind(this)(T,v)},x.prototype.subtract=function(T,v){return z(T)?B(this,T,-1):m.bind(this)(T,v)}}})}}),Re=ut(Te()),K=ut(ee()),ze=ut(Oe()),Ne=ut(We()),je=ut(Pe()),vt=ut(ee()),He=ut(Ve()),Yt=function(){var t=l(function(y,r,d,f){for(d=d||{},f=y.length;f--;d[y[f]]=r);return d},"o"),s=[6,8,10,12,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29,30,31,33,35,36,38,40],i=[1,26],e=[1,27],a=[1,28],g=[1,29],p=[1,30],b=[1,31],F=[1,32],A=[1,33],w=[1,34],V=[1,9],O=[1,10],z=[1,11],U=[1,12],N=[1,13],k=[1,14],D=[1,15],W=[1,16],L=[1,19],q=[1,20],B=[1,21],$=[1,22],x=[1,23],h=[1,25],I=[1,35],m={trace:l(Y(function(){},"trace"),"trace"),yy:{},symbols_:{error:2,start:3,gantt:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NL:10,weekday:11,weekday_monday:12,weekday_tuesday:13,weekday_wednesday:14,weekday_thursday:15,weekday_friday:16,weekday_saturday:17,weekday_sunday:18,weekend:19,weekend_friday:20,weekend_saturday:21,dateFormat:22,inclusiveEndDates:23,topAxis:24,axisFormat:25,tickInterval:26,excludes:27,includes:28,todayMarker:29,title:30,acc_title:31,acc_title_value:32,acc_descr:33,acc_descr_value:34,acc_descr_multiline_value:35,section:36,clickStatement:37,taskTxt:38,taskData:39,click:40,callbackname:41,callbackargs:42,href:43,clickStatementDebug:44,$accept:0,$end:1},terminals_:{2:"error",4:"gantt",6:"EOF",8:"SPACE",10:"NL",12:"weekday_monday",13:"weekday_tuesday",14:"weekday_wednesday",15:"weekday_thursday",16:"weekday_friday",17:"weekday_saturday",18:"weekday_sunday",20:"weekend_friday",21:"weekend_saturday",22:"dateFormat",23:"inclusiveEndDates",24:"topAxis",25:"axisFormat",26:"tickInterval",27:"excludes",28:"includes",29:"todayMarker",30:"title",31:"acc_title",32:"acc_title_value",33:"acc_descr",34:"acc_descr_value",35:"acc_descr_multiline_value",36:"section",38:"taskTxt",39:"taskData",40:"click",41:"callbackname",42:"callbackargs",43:"href"},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[19,1],[19,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,1],[9,2],[37,2],[37,3],[37,3],[37,4],[37,3],[37,4],[37,2],[44,2],[44,3],[44,3],[44,4],[44,3],[44,4],[44,2]],performAction:l(Y(function(r,d,f,u,_,n,S){var o=n.length-1;switch(_){case 1:return n[o-1];case 2:this.$=[];break;case 3:n[o-1].push(n[o]),this.$=n[o-1];break;case 4:case 5:this.$=n[o];break;case 6:case 7:this.$=[];break;case 8:u.setWeekday("monday");break;case 9:u.setWeekday("tuesday");break;case 10:u.setWeekday("wednesday");break;case 11:u.setWeekday("thursday");break;case 12:u.setWeekday("friday");break;case 13:u.setWeekday("saturday");break;case 14:u.setWeekday("sunday");break;case 15:u.setWeekend("friday");break;case 16:u.setWeekend("saturday");break;case 17:u.setDateFormat(n[o].substr(11)),this.$=n[o].substr(11);break;case 18:u.enableInclusiveEndDates(),this.$=n[o].substr(18);break;case 19:u.TopAxis(),this.$=n[o].substr(8);break;case 20:u.setAxisFormat(n[o].substr(11)),this.$=n[o].substr(11);break;case 21:u.setTickInterval(n[o].substr(13)),this.$=n[o].substr(13);break;case 22:u.setExcludes(n[o].substr(9)),this.$=n[o].substr(9);break;case 23:u.setIncludes(n[o].substr(9)),this.$=n[o].substr(9);break;case 24:u.setTodayMarker(n[o].substr(12)),this.$=n[o].substr(12);break;case 27:u.setDiagramTitle(n[o].substr(6)),this.$=n[o].substr(6);break;case 28:this.$=n[o].trim(),u.setAccTitle(this.$);break;case 29:case 30:this.$=n[o].trim(),u.setAccDescription(this.$);break;case 31:u.addSection(n[o].substr(8)),this.$=n[o].substr(8);break;case 33:u.addTask(n[o-1],n[o]),this.$="task";break;case 34:this.$=n[o-1],u.setClickEvent(n[o-1],n[o],null);break;case 35:this.$=n[o-2],u.setClickEvent(n[o-2],n[o-1],n[o]);break;case 36:this.$=n[o-2],u.setClickEvent(n[o-2],n[o-1],null),u.setLink(n[o-2],n[o]);break;case 37:this.$=n[o-3],u.setClickEvent(n[o-3],n[o-2],n[o-1]),u.setLink(n[o-3],n[o]);break;case 38:this.$=n[o-2],u.setClickEvent(n[o-2],n[o],null),u.setLink(n[o-2],n[o-1]);break;case 39:this.$=n[o-3],u.setClickEvent(n[o-3],n[o-1],n[o]),u.setLink(n[o-3],n[o-2]);break;case 40:this.$=n[o-1],u.setLink(n[o-1],n[o]);break;case 41:case 47:this.$=n[o-1]+" "+n[o];break;case 42:case 43:case 45:this.$=n[o-2]+" "+n[o-1]+" "+n[o];break;case 44:case 46:this.$=n[o-3]+" "+n[o-2]+" "+n[o-1]+" "+n[o];break}},"anonymous"),"anonymous"),table:[{3:1,4:[1,2]},{1:[3]},t(s,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:17,12:i,13:e,14:a,15:g,16:p,17:b,18:F,19:18,20:A,21:w,22:V,23:O,24:z,25:U,26:N,27:k,28:D,29:W,30:L,31:q,33:B,35:$,36:x,37:24,38:h,40:I},t(s,[2,7],{1:[2,1]}),t(s,[2,3]),{9:36,11:17,12:i,13:e,14:a,15:g,16:p,17:b,18:F,19:18,20:A,21:w,22:V,23:O,24:z,25:U,26:N,27:k,28:D,29:W,30:L,31:q,33:B,35:$,36:x,37:24,38:h,40:I},t(s,[2,5]),t(s,[2,6]),t(s,[2,17]),t(s,[2,18]),t(s,[2,19]),t(s,[2,20]),t(s,[2,21]),t(s,[2,22]),t(s,[2,23]),t(s,[2,24]),t(s,[2,25]),t(s,[2,26]),t(s,[2,27]),{32:[1,37]},{34:[1,38]},t(s,[2,30]),t(s,[2,31]),t(s,[2,32]),{39:[1,39]},t(s,[2,8]),t(s,[2,9]),t(s,[2,10]),t(s,[2,11]),t(s,[2,12]),t(s,[2,13]),t(s,[2,14]),t(s,[2,15]),t(s,[2,16]),{41:[1,40],43:[1,41]},t(s,[2,4]),t(s,[2,28]),t(s,[2,29]),t(s,[2,33]),t(s,[2,34],{42:[1,42],43:[1,43]}),t(s,[2,40],{41:[1,44]}),t(s,[2,35],{43:[1,45]}),t(s,[2,36]),t(s,[2,38],{42:[1,46]}),t(s,[2,37]),t(s,[2,39])],defaultActions:{},parseError:l(Y(function(r,d){if(d.recoverable)this.trace(r);else{var f=new Error(r);throw f.hash=d,f}},"parseError"),"parseError"),parse:l(Y(function(r){var d=this,f=[0],u=[],_=[null],n=[],S=this.table,o="",H=0,c=0,C=2,M=1,R=n.slice.call(arguments,1),E=Object.create(this.lexer),j={yy:{}};for(var P in this.yy)Object.prototype.hasOwnProperty.call(this.yy,P)&&(j.yy[P]=this.yy[P]);E.setInput(r,j.yy),j.yy.lexer=E,j.yy.parser=this,typeof E.yylloc>"u"&&(E.yylloc={});var nt=E.yylloc;n.push(nt);var at=E.options&&E.options.ranges;typeof j.yy.parseError=="function"?this.parseError=j.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function ft(Q){f.length=f.length-2*Q,_.length=_.length-Q,n.length=n.length-Q}Y(ft,"popStack"),l(ft,"popStack");function ot(){var Q;return Q=u.pop()||E.lex()||M,typeof Q!="number"&&(Q instanceof Array&&(u=Q,Q=u.pop()),Q=d.symbols_[Q]||Q),Q}Y(ot,"lex"),l(ot,"lex");for(var G,J,Z,ct,tt={},rt,et,Ht,xt;;){if(J=f[f.length-1],this.defaultActions[J]?Z=this.defaultActions[J]:((G===null||typeof G>"u")&&(G=ot()),Z=S[J]&&S[J][G]),typeof Z>"u"||!Z.length||!Z[0]){var Et="";xt=[];for(rt in S[J])this.terminals_[rt]&&rt>C&&xt.push("'"+this.terminals_[rt]+"'");E.showPosition?Et="Parse error on line "+(H+1)+`:
`+E.showPosition()+`
Expecting `+xt.join(", ")+", got '"+(this.terminals_[G]||G)+"'":Et="Parse error on line "+(H+1)+": Unexpected "+(G==M?"end of input":"'"+(this.terminals_[G]||G)+"'"),this.parseError(Et,{text:E.match,token:this.terminals_[G]||G,line:E.yylineno,loc:nt,expected:xt})}if(Z[0]instanceof Array&&Z.length>1)throw new Error("Parse Error: multiple actions possible at state: "+J+", token: "+G);switch(Z[0]){case 1:f.push(G),_.push(E.yytext),n.push(E.yylloc),f.push(Z[1]),G=null,c=E.yyleng,o=E.yytext,H=E.yylineno,nt=E.yylloc;break;case 2:if(et=this.productions_[Z[1]][1],tt.$=_[_.length-et],tt._$={first_line:n[n.length-(et||1)].first_line,last_line:n[n.length-1].last_line,first_column:n[n.length-(et||1)].first_column,last_column:n[n.length-1].last_column},at&&(tt._$.range=[n[n.length-(et||1)].range[0],n[n.length-1].range[1]]),ct=this.performAction.apply(tt,[o,c,H,j.yy,Z[1],_,n].concat(R)),typeof ct<"u")return ct;et&&(f=f.slice(0,-1*et*2),_=_.slice(0,-1*et),n=n.slice(0,-1*et)),f.push(this.productions_[Z[1]][0]),_.push(tt.$),n.push(tt._$),Ht=S[f[f.length-2]][f[f.length-1]],f.push(Ht);break;case 3:return!0}}return!0},"parse"),"parse")},T=function(){var y={EOF:1,parseError:l(Y(function(d,f){if(this.yy.parser)this.yy.parser.parseError(d,f);else throw new Error(d)},"parseError"),"parseError"),setInput:l(function(r,d){return this.yy=d||this.yy||{},this._input=r,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},"setInput"),input:l(function(){var r=this._input[0];this.yytext+=r,this.yyleng++,this.offset++,this.match+=r,this.matched+=r;var d=r.match(/(?:\r\n?|\n).*/g);return d?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),r},"input"),unput:l(function(r){var d=r.length,f=r.split(/(?:\r\n?|\n)/g);this._input=r+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-d),this.offset-=d;var u=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),f.length-1&&(this.yylineno-=f.length-1);var _=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:f?(f.length===u.length?this.yylloc.first_column:0)+u[u.length-f.length].length-f[0].length:this.yylloc.first_column-d},this.options.ranges&&(this.yylloc.range=[_[0],_[0]+this.yyleng-d]),this.yyleng=this.yytext.length,this},"unput"),more:l(function(){return this._more=!0,this},"more"),reject:l(function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},"reject"),less:l(function(r){this.unput(this.match.slice(r))},"less"),pastInput:l(function(){var r=this.matched.substr(0,this.matched.length-this.match.length);return(r.length>20?"...":"")+r.substr(-20).replace(/\n/g,"")},"pastInput"),upcomingInput:l(function(){var r=this.match;return r.length<20&&(r+=this._input.substr(0,20-r.length)),(r.substr(0,20)+(r.length>20?"...":"")).replace(/\n/g,"")},"upcomingInput"),showPosition:l(function(){var r=this.pastInput(),d=new Array(r.length+1).join("-");return r+this.upcomingInput()+`
`+d+"^"},"showPosition"),test_match:l(function(r,d){var f,u,_;if(this.options.backtrack_lexer&&(_={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(_.yylloc.range=this.yylloc.range.slice(0))),u=r[0].match(/(?:\r\n?|\n).*/g),u&&(this.yylineno+=u.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:u?u[u.length-1].length-u[u.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+r[0].length},this.yytext+=r[0],this.match+=r[0],this.matches=r,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(r[0].length),this.matched+=r[0],f=this.performAction.call(this,this.yy,this,d,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),f)return f;if(this._backtrack){for(var n in _)this[n]=_[n];return!1}return!1},"test_match"),next:l(function(){if(this.done)return this.EOF;this._input||(this.done=!0);var r,d,f,u;this._more||(this.yytext="",this.match="");for(var _=this._currentRules(),n=0;n<_.length;n++)if(f=this._input.match(this.rules[_[n]]),f&&(!d||f[0].length>d[0].length)){if(d=f,u=n,this.options.backtrack_lexer){if(r=this.test_match(f,_[n]),r!==!1)return r;if(this._backtrack){d=!1;continue}else return!1}else if(!this.options.flex)break}return d?(r=this.test_match(d,_[u]),r!==!1?r:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},"next"),lex:l(Y(function(){var d=this.next();return d||this.lex()},"lex"),"lex"),begin:l(Y(function(d){this.conditionStack.push(d)},"begin"),"begin"),popState:l(Y(function(){var d=this.conditionStack.length-1;return d>0?this.conditionStack.pop():this.conditionStack[0]},"popState"),"popState"),_currentRules:l(Y(function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},"_currentRules"),"_currentRules"),topState:l(Y(function(d){return d=this.conditionStack.length-1-Math.abs(d||0),d>=0?this.conditionStack[d]:"INITIAL"},"topState"),"topState"),pushState:l(Y(function(d){this.begin(d)},"pushState"),"pushState"),stateStackSize:l(Y(function(){return this.conditionStack.length},"stateStackSize"),"stateStackSize"),options:{"case-insensitive":!0},performAction:l(Y(function(d,f,u,_){switch(u){case 0:return this.begin("open_directive"),"open_directive";case 1:return this.begin("acc_title"),31;case 2:return this.popState(),"acc_title_value";case 3:return this.begin("acc_descr"),33;case 4:return this.popState(),"acc_descr_value";case 5:this.begin("acc_descr_multiline");break;case 6:this.popState();break;case 7:return"acc_descr_multiline_value";case 8:break;case 9:break;case 10:break;case 11:return 10;case 12:break;case 13:break;case 14:this.begin("href");break;case 15:this.popState();break;case 16:return 43;case 17:this.begin("callbackname");break;case 18:this.popState();break;case 19:this.popState(),this.begin("callbackargs");break;case 20:return 41;case 21:this.popState();break;case 22:return 42;case 23:this.begin("click");break;case 24:this.popState();break;case 25:return 40;case 26:return 4;case 27:return 22;case 28:return 23;case 29:return 24;case 30:return 25;case 31:return 26;case 32:return 28;case 33:return 27;case 34:return 29;case 35:return 12;case 36:return 13;case 37:return 14;case 38:return 15;case 39:return 16;case 40:return 17;case 41:return 18;case 42:return 20;case 43:return 21;case 44:return"date";case 45:return 30;case 46:return"accDescription";case 47:return 36;case 48:return 38;case 49:return 39;case 50:return":";case 51:return 6;case 52:return"INVALID"}},"anonymous"),"anonymous"),rules:[/^(?:%%\{)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:%%(?!\{)*[^\n]*)/i,/^(?:[^\}]%%*[^\n]*)/i,/^(?:%%*[^\n]*[\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:%[^\n]*)/i,/^(?:href[\s]+["])/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:call[\s]+)/i,/^(?:\([\s]*\))/i,/^(?:\()/i,/^(?:[^(]*)/i,/^(?:\))/i,/^(?:[^)]*)/i,/^(?:click[\s]+)/i,/^(?:[\s\n])/i,/^(?:[^\s\n]*)/i,/^(?:gantt\b)/i,/^(?:dateFormat\s[^#\n;]+)/i,/^(?:inclusiveEndDates\b)/i,/^(?:topAxis\b)/i,/^(?:axisFormat\s[^#\n;]+)/i,/^(?:tickInterval\s[^#\n;]+)/i,/^(?:includes\s[^#\n;]+)/i,/^(?:excludes\s[^#\n;]+)/i,/^(?:todayMarker\s[^\n;]+)/i,/^(?:weekday\s+monday\b)/i,/^(?:weekday\s+tuesday\b)/i,/^(?:weekday\s+wednesday\b)/i,/^(?:weekday\s+thursday\b)/i,/^(?:weekday\s+friday\b)/i,/^(?:weekday\s+saturday\b)/i,/^(?:weekday\s+sunday\b)/i,/^(?:weekend\s+friday\b)/i,/^(?:weekend\s+saturday\b)/i,/^(?:\d\d\d\d-\d\d-\d\d\b)/i,/^(?:title\s[^\n]+)/i,/^(?:accDescription\s[^#\n;]+)/i,/^(?:section\s[^\n]+)/i,/^(?:[^:\n]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[6,7],inclusive:!1},acc_descr:{rules:[4],inclusive:!1},acc_title:{rules:[2],inclusive:!1},callbackargs:{rules:[21,22],inclusive:!1},callbackname:{rules:[18,19,20],inclusive:!1},href:{rules:[15,16],inclusive:!1},click:{rules:[24,25],inclusive:!1},INITIAL:{rules:[0,1,3,5,8,9,10,11,12,13,14,17,23,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52],inclusive:!0}}};return y}();m.lexer=T;function v(){this.yy={}}return Y(v,"Parser"),l(v,"Parser"),v.prototype=m,m.Parser=v,new v}();Yt.parser=Yt;var Be=Yt;K.default.extend(ze.default);K.default.extend(Ne.default);K.default.extend(je.default);var Jt={friday:5,saturday:6},st="",At="",Ot=void 0,Wt="",yt=[],gt=[],Pt=new Map,Vt=[],Dt=[],pt="",Rt="",se=["active","done","crit","milestone","vert"],zt=[],ht="",Tt=!1,Nt=!1,jt="sunday",St="saturday",$t=0,qe=l(function(){Vt=[],Dt=[],pt="",zt=[],wt=0,Ft=void 0,_t=void 0,X=[],st="",At="",Rt="",Ot=void 0,Wt="",yt=[],gt=[],Tt=!1,Nt=!1,$t=0,Pt=new Map,ht="",ve(),jt="sunday",St="saturday"},"clear"),Ge=l(function(t){ht=t},"setDiagramId"),Xe=l(function(t){At=t},"setAxisFormat"),Ue=l(function(){return At},"getAxisFormat"),Ze=l(function(t){Ot=t},"setTickInterval"),Qe=l(function(){return Ot},"getTickInterval"),Je=l(function(t){Wt=t},"setTodayMarker"),Ke=l(function(){return Wt},"getTodayMarker"),ts=l(function(t){st=t},"setDateFormat"),es=l(function(){Tt=!0},"enableInclusiveEndDates"),ss=l(function(){return Tt},"endDatesAreInclusive"),is=l(function(){Nt=!0},"enableTopAxis"),ns=l(function(){return Nt},"topAxisEnabled"),rs=l(function(t){Rt=t},"setDisplayMode"),as=l(function(){return Rt},"getDisplayMode"),os=l(function(){return st},"getDateFormat"),ie=l((t,s)=>{const i=s.toLowerCase().split(/[\s,]+/).filter(e=>e!=="");return[...new Set([...t,...i])]},"mergeTokens"),cs=l(function(t){yt=ie(yt,t)},"setIncludes"),ls=l(function(){return yt},"getIncludes"),us=l(function(t){gt=ie(gt,t)},"setExcludes"),ds=l(function(){return gt},"getExcludes"),fs=l(function(){return Pt},"getLinks"),hs=l(function(t){pt=t,Vt.push(t)},"addSection"),ms=l(function(){return Vt},"getSections"),ks=l(function(){let t=Kt();const s=10;let i=0;for(;!t&&i<s;)t=Kt(),i++;return Dt=X,Dt},"getTasks"),ne=l(function(t,s,i,e){const a=t.format(s.trim()),g=t.format("YYYY-MM-DD");return e.includes(a)||e.includes(g)?!1:i.includes("weekends")&&(t.isoWeekday()===Jt[St]||t.isoWeekday()===Jt[St]+1)||i.includes(t.format("dddd").toLowerCase())?!0:i.includes(a)||i.includes(g)},"isInvalidDate"),ys=l(function(t){jt=t},"setWeekday"),gs=l(function(){return jt},"getWeekday"),ps=l(function(t){St=t},"setWeekend"),re=l(function(t,s,i,e){if(!i.length||t.manualEndTime)return;let a;t.startTime instanceof Date?a=(0,K.default)(t.startTime):a=(0,K.default)(t.startTime,s,!0),a=a.add(1,"d");let g;t.endTime instanceof Date?g=(0,K.default)(t.endTime):g=(0,K.default)(t.endTime,s,!0);const[p,b]=vs(a,g,s,i,e);t.endTime=p.toDate(),t.renderEndTime=b},"checkTaskDates"),vs=l(function(t,s,i,e,a){let g=!1,p=null;const b=s.add(1e4,"d");for(;t<=s;){if(g||(p=s.toDate()),g=ne(t,i,e,a),g&&(s=s.add(1,"d"),s>b))throw new Error("Failed to find a valid date that was not excluded by `excludes` after 10,000 iterations.");t=t.add(1,"d")}return[s,p]},"fixTaskDates"),Lt=l(function(t,s,i){if(i=i.trim(),l(b=>{const F=b.trim();return F==="x"||F==="X"},"isTimestampFormat")(s)&&/^\d+$/.test(i))return new Date(Number(i));const g=/^after\s+(?<ids>[\d\w- ]+)/.exec(i);if(g!==null){let b=null;for(const A of g.groups.ids.split(" ")){let w=dt(A);w!==void 0&&(!b||w.endTime>b.endTime)&&(b=w)}if(b)return b.endTime;const F=new Date;return F.setHours(0,0,0,0),F}let p=(0,K.default)(i,s.trim(),!0);if(p.isValid())return p.toDate();{lt.debug("Invalid date:"+i),lt.debug("With date format:"+s.trim());const b=new Date(i);if(b===void 0||isNaN(b.getTime())||b.getFullYear()<-1e4||b.getFullYear()>1e4)throw new Error("Invalid date:"+i);return b}},"getStartDate"),ae=l(function(t){const s=/^(\d+(?:\.\d+)?)([Mdhmswy]|ms)$/.exec(t.trim());return s!==null?[Number.parseFloat(s[1]),s[2]]:[NaN,"ms"]},"parseDuration"),oe=l(function(t,s,i,e=!1){i=i.trim();const g=/^until\s+(?<ids>[\d\w- ]+)/.exec(i);if(g!==null){let w=null;for(const O of g.groups.ids.split(" ")){let z=dt(O);z!==void 0&&(!w||z.startTime<w.startTime)&&(w=z)}if(w)return w.startTime;const V=new Date;return V.setHours(0,0,0,0),V}let p=(0,K.default)(i,s.trim(),!0);if(p.isValid())return e&&(p=p.add(1,"d")),p.toDate();let b=(0,K.default)(t);const[F,A]=ae(i);if(!Number.isNaN(F)){const w=b.add(F,A);w.isValid()&&(b=w)}return b.toDate()},"getEndDate"),wt=0,kt=l(function(t){return t===void 0?(wt=wt+1,"task"+wt):t},"parseId"),Ts=l(function(t,s){let i;s.substr(0,1)===":"?i=s.substr(1,s.length):i=s;const e=i.split(","),a={};Mt(e,a,se);for(let p=0;p<e.length;p++)e[p]=e[p].trim();let g="";switch(e.length){case 1:a.id=kt(),a.startTime=t.endTime,g=e[0];break;case 2:a.id=kt(),a.startTime=Lt(void 0,st,e[0]),g=e[1];break;case 3:a.id=kt(e[0]),a.startTime=Lt(void 0,st,e[1]),g=e[2];break}return g&&(a.endTime=oe(a.startTime,st,g,Tt),a.manualEndTime=(0,K.default)(g,"YYYY-MM-DD",!0).isValid(),re(a,st,gt,yt)),a},"compileData"),xs=l(function(t,s){let i;s.substr(0,1)===":"?i=s.substr(1,s.length):i=s;const e=i.split(","),a={};Mt(e,a,se);for(let g=0;g<e.length;g++)e[g]=e[g].trim();switch(e.length){case 1:a.id=kt(),a.startTime={type:"prevTaskEnd",id:t},a.endTime={data:e[0]};break;case 2:a.id=kt(),a.startTime={type:"getStartDate",startData:e[0]},a.endTime={data:e[1]};break;case 3:a.id=kt(e[0]),a.startTime={type:"getStartDate",startData:e[1]},a.endTime={data:e[2]};break}return a},"parseData"),Ft,_t,X=[],ce={},bs=l(function(t,s){const i={section:pt,type:pt,processed:!1,manualEndTime:!1,renderEndTime:null,raw:{data:s},task:t,classes:[]},e=xs(_t,s);i.raw.startTime=e.startTime,i.raw.endTime=e.endTime,i.id=e.id,i.prevTaskId=_t,i.active=e.active,i.done=e.done,i.crit=e.crit,i.milestone=e.milestone,i.vert=e.vert,i.vert?i.order=-1:(i.order=$t,$t++);const a=X.push(i);_t=i.id,ce[i.id]=a-1},"addTask"),dt=l(function(t){const s=ce[t];return X[s]},"findTaskById"),ws=l(function(t,s){const i={section:pt,type:pt,description:t,task:t,classes:[]},e=Ts(Ft,s);i.startTime=e.startTime,i.endTime=e.endTime,i.id=e.id,i.active=e.active,i.done=e.done,i.crit=e.crit,i.milestone=e.milestone,i.vert=e.vert,Ft=i,Dt.push(i)},"addTaskOrg"),Kt=l(function(){const t=l(function(i){const e=X[i];let a="";switch(X[i].raw.startTime.type){case"prevTaskEnd":{const g=dt(e.prevTaskId);e.startTime=g.endTime;break}case"getStartDate":a=Lt(void 0,st,X[i].raw.startTime.startData),a&&(X[i].startTime=a);break}return X[i].startTime&&(X[i].endTime=oe(X[i].startTime,st,X[i].raw.endTime.data,Tt),X[i].endTime&&(X[i].processed=!0,X[i].manualEndTime=(0,K.default)(X[i].raw.endTime.data,"YYYY-MM-DD",!0).isValid(),re(X[i],st,gt,yt))),X[i].processed},"compileTask");let s=!0;for(const[i,e]of X.entries())t(i),s=s&&e.processed;return s},"compileTasks"),_s=l(function(t,s){let i=s;mt().securityLevel!=="loose"&&(i=(0,Re.sanitizeUrl)(s)),t.split(",").forEach(function(e){dt(e)!==void 0&&(ue(e,()=>{window.open(i,"_self")}),Pt.set(e,i))}),le(t,"clickable")},"setLink"),le=l(function(t,s){t.split(",").forEach(function(i){let e=dt(i);e!==void 0&&e.classes.push(s)})},"setClass"),Ds=l(function(t,s,i){if(mt().securityLevel!=="loose"||s===void 0)return;let e=[];if(typeof i=="string"){e=i.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);for(let g=0;g<e.length;g++){let p=e[g].trim();p.startsWith('"')&&p.endsWith('"')&&(p=p.substr(1,p.length-2)),e[g]=p}}e.length===0&&e.push(t),dt(t)!==void 0&&ue(t,()=>{xe.runFunc(s,...e)})},"setClickFun"),ue=l(function(t,s){zt.push(function(){const i=ht?`${ht}-${t}`:t,e=document.querySelector(`[id="${i}"]`);e!==null&&e.addEventListener("click",function(){s()})},function(){const i=ht?`${ht}-${t}`:t,e=document.querySelector(`[id="${i}-text"]`);e!==null&&e.addEventListener("click",function(){s()})})},"pushFun"),Ss=l(function(t,s,i){t.split(",").forEach(function(e){Ds(e,s,i)}),le(t,"clickable")},"setClickEvent"),Cs=l(function(t){zt.forEach(function(s){s(t)})},"bindFunctions"),Ms={getConfig:l(()=>mt().gantt,"getConfig"),clear:qe,setDateFormat:ts,getDateFormat:os,enableInclusiveEndDates:es,endDatesAreInclusive:ss,enableTopAxis:is,topAxisEnabled:ns,setAxisFormat:Xe,getAxisFormat:Ue,setTickInterval:Ze,getTickInterval:Qe,setTodayMarker:Je,getTodayMarker:Ke,setAccTitle:ye,getAccTitle:ke,setDiagramTitle:me,getDiagramTitle:he,setDiagramId:Ge,setDisplayMode:rs,getDisplayMode:as,setAccDescription:fe,getAccDescription:de,addSection:hs,getSections:ms,getTasks:ks,addTask:bs,findTaskById:dt,addTaskOrg:ws,setIncludes:cs,getIncludes:ls,setExcludes:us,getExcludes:ds,setClickEvent:Ss,setLink:_s,getLinks:fs,bindFunctions:Cs,parseDuration:ae,isInvalidDate:ne,setWeekday:ys,getWeekday:gs,setWeekend:ps};function Mt(t,s,i){let e=!0;for(;e;)e=!1,i.forEach(function(a){const g="^\\s*"+a+"\\s*$",p=new RegExp(g);t[0].match(p)&&(s[a]=!0,t.shift(1),e=!0)})}Y(Mt,"getTaskTags");l(Mt,"getTaskTags");vt.default.extend(He.default);var Es=l(function(){lt.debug("Something is calling, setConf, remove the call")},"setConf"),te={monday:Le,tuesday:$e,wednesday:Ye,thursday:Ie,friday:Ee,saturday:Me,sunday:Ce},Is=l((t,s)=>{let i=[...t].map(()=>-1/0),e=[...t].sort((g,p)=>g.startTime-p.startTime||g.order-p.order),a=0;for(const g of e)for(let p=0;p<i.length;p++)if(g.startTime>=i[p]){i[p]=g.endTime,g.order=p+s,p>a&&(a=p);break}return a},"getMaxIntersections"),it,It=1e4,Ys=l(function(t,s,i,e){const a=mt().gantt;e.db.setDiagramId(s);const g=mt().securityLevel;let p;g==="sandbox"&&(p=bt("#i"+s));const b=g==="sandbox"?bt(p.nodes()[0].contentDocument.body):bt("body"),F=g==="sandbox"?p.nodes()[0].contentDocument:document,A=F.getElementById(s);it=A.parentElement.offsetWidth,it===void 0&&(it=1200),a.useWidth!==void 0&&(it=a.useWidth);const w=e.db.getTasks(),V=w.filter(m=>!m.vert);let O=[];for(const m of V)O.push(m.type);O=I(O);const z={};let U=2*a.topPadding;if(e.db.getDisplayMode()==="compact"||a.displayMode==="compact"){const m={};for(const v of V)m[v.section]===void 0?m[v.section]=[v]:m[v.section].push(v);let T=0;for(const v of Object.keys(m)){const y=Is(m[v],T)+1;T+=y,U+=y*(a.barHeight+a.barGap),z[v]=y}}else{U+=V.length*(a.barHeight+a.barGap);for(const m of O)z[m]=V.filter(T=>T.type===m).length}A.setAttribute("viewBox","0 0 "+it+" "+U);const N=b.select(`[id="${s}"]`),k=be().domain([we(w,function(m){return m.startTime}),_e(w,function(m){return m.endTime})]).rangeRound([0,it-a.leftPadding-a.rightPadding]);function D(m,T){const v=m.startTime,y=T.startTime;let r=0;return v>y?r=1:v<y&&(r=-1),r}Y(D,"taskCompare"),l(D,"taskCompare"),w.sort(D),W(w,it,U),ge(N,U,it,a.useMaxWidth),N.append("text").text(e.db.getDiagramTitle()).attr("x",it/2).attr("y",a.titleTopMargin).attr("class","titleText");function W(m,T,v){const y=a.barHeight,r=y+a.barGap,d=a.topPadding,f=a.leftPadding,u=Ae().domain([0,O.length]).range(["#00B9FA","#F95002"]).interpolate(De);q(r,d,f,T,v,m,e.db.getExcludes(),e.db.getIncludes()),$(f,d,T,v),L(m,r,d,f,y,u,T),x(r,d),h(f,d,T,v)}Y(W,"makeGantt"),l(W,"makeGantt");function L(m,T,v,y,r,d,f){m.sort((c,C)=>c.vert===C.vert?0:c.vert?1:-1);const u=m.filter(c=>!c.vert),n=[...new Set(u.map(c=>c.order))].map(c=>u.find(C=>C.order===c));N.append("g").selectAll("rect").data(n).enter().append("rect").attr("x",0).attr("y",function(c,C){return C=c.order,C*T+v-2}).attr("width",function(){return f-a.rightPadding/2}).attr("height",T).attr("class",function(c){for(const[C,M]of O.entries())if(c.type===M)return"section section"+C%a.numberSectionStyles;return"section section0"}).enter();const S=N.append("g").selectAll("rect").data(m).enter(),o=e.db.getLinks();if(S.append("rect").attr("id",function(c){return s+"-"+c.id}).attr("rx",3).attr("ry",3).attr("x",function(c){return c.milestone?k(c.startTime)+y+.5*(k(c.endTime)-k(c.startTime))-.5*r:k(c.startTime)+y}).attr("y",function(c,C){return C=c.order,c.vert?a.gridLineStartPadding:C*T+v}).attr("width",function(c){return c.milestone?r:c.vert?.08*r:k(c.renderEndTime||c.endTime)-k(c.startTime)}).attr("height",function(c){return c.vert?u.length*(a.barHeight+a.barGap)+a.barHeight*2:r}).attr("transform-origin",function(c,C){return C=c.order,(k(c.startTime)+y+.5*(k(c.endTime)-k(c.startTime))).toString()+"px "+(C*T+v+.5*r).toString()+"px"}).attr("class",function(c){const C="task";let M="";c.classes.length>0&&(M=c.classes.join(" "));let R=0;for(const[j,P]of O.entries())c.type===P&&(R=j%a.numberSectionStyles);let E="";return c.active?c.crit?E+=" activeCrit":E=" active":c.done?c.crit?E=" doneCrit":E=" done":c.crit&&(E+=" crit"),E.length===0&&(E=" task"),c.milestone&&(E=" milestone "+E),c.vert&&(E=" vert "+E),E+=R,E+=" "+M,C+E}),S.append("text").attr("id",function(c){return s+"-"+c.id+"-text"}).text(function(c){return c.task}).attr("font-size",a.fontSize).attr("x",function(c){let C=k(c.startTime),M=k(c.renderEndTime||c.endTime);if(c.milestone&&(C+=.5*(k(c.endTime)-k(c.startTime))-.5*r,M=C+r),c.vert)return k(c.startTime)+y;const R=this.getBBox().width;return R>M-C?M+R+1.5*a.leftPadding>f?C+y-5:M+y+5:(M-C)/2+C+y}).attr("y",function(c,C){return c.vert?a.gridLineStartPadding+u.length*(a.barHeight+a.barGap)+60:(C=c.order,C*T+a.barHeight/2+(a.fontSize/2-2)+v)}).attr("text-height",r).attr("class",function(c){const C=k(c.startTime);let M=k(c.endTime);c.milestone&&(M=C+r);const R=this.getBBox().width;let E="";c.classes.length>0&&(E=c.classes.join(" "));let j=0;for(const[nt,at]of O.entries())c.type===at&&(j=nt%a.numberSectionStyles);let P="";return c.active&&(c.crit?P="activeCritText"+j:P="activeText"+j),c.done?c.crit?P=P+" doneCritText"+j:P=P+" doneText"+j:c.crit&&(P=P+" critText"+j),c.milestone&&(P+=" milestoneText"),c.vert&&(P+=" vertText"),R>M-C?M+R+1.5*a.leftPadding>f?E+" taskTextOutsideLeft taskTextOutside"+j+" "+P:E+" taskTextOutsideRight taskTextOutside"+j+" "+P+" width-"+R:E+" taskText taskText"+j+" "+P+" width-"+R}),mt().securityLevel==="sandbox"){let c;c=bt("#i"+s);const C=c.nodes()[0].contentDocument;S.filter(function(M){return o.has(M.id)}).each(function(M){var R=C.querySelector("#"+CSS.escape(s+"-"+M.id)),E=C.querySelector("#"+CSS.escape(s+"-"+M.id+"-text"));const j=R.parentNode;var P=C.createElement("a");P.setAttribute("xlink:href",o.get(M.id)),P.setAttribute("target","_top"),j.appendChild(P),P.appendChild(R),P.appendChild(E)})}}Y(L,"drawRects"),l(L,"drawRects");function q(m,T,v,y,r,d,f,u){if(f.length===0&&u.length===0)return;let _,n;for(const{startTime:M,endTime:R}of d)(_===void 0||M<_)&&(_=M),(n===void 0||R>n)&&(n=R);if(!_||!n)return;if((0,vt.default)(n).diff((0,vt.default)(_),"year")>5){lt.warn("The difference between the min and max time is more than 5 years. This will cause performance issues. Skipping drawing exclude days.");return}const S=e.db.getDateFormat(),o=[];let H=null,c=(0,vt.default)(_);for(;c.valueOf()<=n;)e.db.isInvalidDate(c,S,f,u)?H?H.end=c:H={start:c,end:c}:H&&(o.push(H),H=null),c=c.add(1,"d");N.append("g").selectAll("rect").data(o).enter().append("rect").attr("id",M=>s+"-exclude-"+M.start.format("YYYY-MM-DD")).attr("x",M=>k(M.start.startOf("day"))+v).attr("y",a.gridLineStartPadding).attr("width",M=>k(M.end.endOf("day"))-k(M.start.startOf("day"))).attr("height",r-T-a.gridLineStartPadding).attr("transform-origin",function(M,R){return(k(M.start)+v+.5*(k(M.end)-k(M.start))).toString()+"px "+(R*m+.5*r).toString()+"px"}).attr("class","exclude-range")}Y(q,"drawExcludeDays"),l(q,"drawExcludeDays");function B(m,T,v,y){if(v<=0||m>T)return 1/0;const r=T-m,d=vt.default.duration({[y??"day"]:v}).asMilliseconds();return d<=0?1/0:Math.ceil(r/d)}Y(B,"getEstimatedTickCount"),l(B,"getEstimatedTickCount");function $(m,T,v,y){const r=e.db.getDateFormat(),d=e.db.getAxisFormat();let f;d?f=d:r==="D"?f="%d":f=a.axisFormat??"%Y-%m-%d";let u=Se(k).tickSize(-y+T+a.gridLineStartPadding).tickFormat(Bt(f));const n=/^([1-9]\d*)(millisecond|second|minute|hour|day|week|month)$/.exec(e.db.getTickInterval()||a.tickInterval);if(n!==null){const S=parseInt(n[1],10);if(isNaN(S)||S<=0)lt.warn(`Invalid tick interval value: "${n[1]}". Skipping custom tick interval.`);else{const o=n[2],H=e.db.getWeekday()||a.weekday,c=k.domain(),C=c[0],M=c[1],R=B(C,M,S,o);if(R>It)lt.warn(`The tick interval "${S}${o}" would generate ${R} ticks, which exceeds the maximum allowed (${It}). This may indicate an invalid date or time range. Skipping custom tick interval.`);else switch(o){case"millisecond":u.ticks(Qt.every(S));break;case"second":u.ticks(Zt.every(S));break;case"minute":u.ticks(Ut.every(S));break;case"hour":u.ticks(Xt.every(S));break;case"day":u.ticks(Gt.every(S));break;case"week":u.ticks(te[H].every(S));break;case"month":u.ticks(qt.every(S));break}}}if(N.append("g").attr("class","grid").attr("transform","translate("+m+", "+(y-50)+")").call(u).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10).attr("dy","1em"),e.db.topAxisEnabled()||a.topAxis){let S=Fe(k).tickSize(-y+T+a.gridLineStartPadding).tickFormat(Bt(f));if(n!==null){const o=parseInt(n[1],10);if(isNaN(o)||o<=0)lt.warn(`Invalid tick interval value: "${n[1]}". Skipping custom tick interval.`);else{const H=n[2],c=e.db.getWeekday()||a.weekday,C=k.domain(),M=C[0],R=C[1];if(B(M,R,o,H)<=It)switch(H){case"millisecond":S.ticks(Qt.every(o));break;case"second":S.ticks(Zt.every(o));break;case"minute":S.ticks(Ut.every(o));break;case"hour":S.ticks(Xt.every(o));break;case"day":S.ticks(Gt.every(o));break;case"week":S.ticks(te[c].every(o));break;case"month":S.ticks(qt.every(o));break}}}N.append("g").attr("class","grid").attr("transform","translate("+m+", "+T+")").call(S).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10)}}Y($,"makeGrid"),l($,"makeGrid");function x(m,T){let v=0;const y=Object.keys(z).map(r=>[r,z[r]]);N.append("g").selectAll("text").data(y).enter().append(function(r){const d=r[0].split(pe.lineBreakRegex),f=-(d.length-1)/2,u=F.createElementNS("http://www.w3.org/2000/svg","text");u.setAttribute("dy",f+"em");for(const[_,n]of d.entries()){const S=F.createElementNS("http://www.w3.org/2000/svg","tspan");S.setAttribute("alignment-baseline","central"),S.setAttribute("x","10"),_>0&&S.setAttribute("dy","1em"),S.textContent=n,u.appendChild(S)}return u}).attr("x",10).attr("y",function(r,d){if(d>0)for(let f=0;f<d;f++)return v+=y[d-1][1],r[1]*m/2+v*m+T;else return r[1]*m/2+T}).attr("font-size",a.sectionFontSize).attr("class",function(r){for(const[d,f]of O.entries())if(r[0]===f)return"sectionTitle sectionTitle"+d%a.numberSectionStyles;return"sectionTitle"})}Y(x,"vertLabels"),l(x,"vertLabels");function h(m,T,v,y){const r=e.db.getTodayMarker();if(r==="off")return;const d=N.append("g").attr("class","today"),f=new Date,u=d.append("line");u.attr("x1",k(f)+m).attr("x2",k(f)+m).attr("y1",a.titleTopMargin).attr("y2",y-a.titleTopMargin).attr("class","today"),r!==""&&u.attr("style",r.replace(/,/g,";"))}Y(h,"drawToday"),l(h,"drawToday");function I(m){const T={},v=[];for(let y=0,r=m.length;y<r;++y)Object.prototype.hasOwnProperty.call(T,m[y])||(T[m[y]]=!0,v.push(m[y]));return v}Y(I,"checkUnique"),l(I,"checkUnique")},"draw"),$s={setConf:Es,draw:Ys},Ls=l(t=>`
  .mermaid-main-font {
        font-family: ${t.fontFamily};
  }

  .exclude-range {
    fill: ${t.excludeBkgColor};
  }

  .section {
    stroke: none;
    opacity: 0.2;
  }

  .section0 {
    fill: ${t.sectionBkgColor};
  }

  .section2 {
    fill: ${t.sectionBkgColor2};
  }

  .section1,
  .section3 {
    fill: ${t.altSectionBkgColor};
    opacity: 0.2;
  }

  .sectionTitle0 {
    fill: ${t.titleColor};
  }

  .sectionTitle1 {
    fill: ${t.titleColor};
  }

  .sectionTitle2 {
    fill: ${t.titleColor};
  }

  .sectionTitle3 {
    fill: ${t.titleColor};
  }

  .sectionTitle {
    text-anchor: start;
    font-family: ${t.fontFamily};
  }


  /* Grid and axis */

  .grid .tick {
    stroke: ${t.gridColor};
    opacity: 0.8;
    shape-rendering: crispEdges;
  }

  .grid .tick text {
    font-family: ${t.fontFamily};
    fill: ${t.textColor};
  }

  .grid path {
    stroke-width: 0;
  }


  /* Today line */

  .today {
    fill: none;
    stroke: ${t.todayLineColor};
    stroke-width: 2px;
  }


  /* Task styling */

  /* Default task */

  .task {
    stroke-width: 2;
  }

  .taskText {
    text-anchor: middle;
    font-family: ${t.fontFamily};
  }

  .taskTextOutsideRight {
    fill: ${t.taskTextDarkColor};
    text-anchor: start;
    font-family: ${t.fontFamily};
  }

  .taskTextOutsideLeft {
    fill: ${t.taskTextDarkColor};
    text-anchor: end;
  }


  /* Special case clickable */

  .task.clickable {
    cursor: pointer;
  }

  .taskText.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideLeft.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideRight.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }


  /* Specific task settings for the sections*/

  .taskText0,
  .taskText1,
  .taskText2,
  .taskText3 {
    fill: ${t.taskTextColor};
  }

  .task0,
  .task1,
  .task2,
  .task3 {
    fill: ${t.taskBkgColor};
    stroke: ${t.taskBorderColor};
  }

  .taskTextOutside0,
  .taskTextOutside2
  {
    fill: ${t.taskTextOutsideColor};
  }

  .taskTextOutside1,
  .taskTextOutside3 {
    fill: ${t.taskTextOutsideColor};
  }


  /* Active task */

  .active0,
  .active1,
  .active2,
  .active3 {
    fill: ${t.activeTaskBkgColor};
    stroke: ${t.activeTaskBorderColor};
  }

  .activeText0,
  .activeText1,
  .activeText2,
  .activeText3 {
    fill: ${t.taskTextDarkColor} !important;
  }


  /* Completed task */

  .done0,
  .done1,
  .done2,
  .done3 {
    stroke: ${t.doneTaskBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
  }

  .doneText0,
  .doneText1,
  .doneText2,
  .doneText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  /* Done task text displayed outside the bar sits against the diagram background,
     not against the done-task bar, so it must use the outside/contrast color. */
  .doneText0.taskTextOutsideLeft,
  .doneText0.taskTextOutsideRight,
  .doneText1.taskTextOutsideLeft,
  .doneText1.taskTextOutsideRight,
  .doneText2.taskTextOutsideLeft,
  .doneText2.taskTextOutsideRight,
  .doneText3.taskTextOutsideLeft,
  .doneText3.taskTextOutsideRight {
    fill: ${t.taskTextOutsideColor} !important;
  }


  /* Tasks on the critical line */

  .crit0,
  .crit1,
  .crit2,
  .crit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.critBkgColor};
    stroke-width: 2;
  }

  .activeCrit0,
  .activeCrit1,
  .activeCrit2,
  .activeCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.activeTaskBkgColor};
    stroke-width: 2;
  }

  .doneCrit0,
  .doneCrit1,
  .doneCrit2,
  .doneCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
    cursor: pointer;
    shape-rendering: crispEdges;
  }

  .milestone {
    transform: rotate(45deg) scale(0.8,0.8);
  }

  .milestoneText {
    font-style: italic;
  }
  .doneCritText0,
  .doneCritText1,
  .doneCritText2,
  .doneCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  /* Done-crit task text outside the bar — same reasoning as doneText above. */
  .doneCritText0.taskTextOutsideLeft,
  .doneCritText0.taskTextOutsideRight,
  .doneCritText1.taskTextOutsideLeft,
  .doneCritText1.taskTextOutsideRight,
  .doneCritText2.taskTextOutsideLeft,
  .doneCritText2.taskTextOutsideRight,
  .doneCritText3.taskTextOutsideLeft,
  .doneCritText3.taskTextOutsideRight {
    fill: ${t.taskTextOutsideColor} !important;
  }

  .vert {
    stroke: ${t.vertLineColor};
  }

  .vertText {
    font-size: 15px;
    text-anchor: middle;
    fill: ${t.vertLineColor} !important;
  }

  .activeCritText0,
  .activeCritText1,
  .activeCritText2,
  .activeCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  .titleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${t.titleColor||t.textColor};
    font-family: ${t.fontFamily};
  }
`,"getStyles"),Fs=Ls,js={parser:Be,db:Ms,renderer:$s,styles:Fs};export{js as diagram};
