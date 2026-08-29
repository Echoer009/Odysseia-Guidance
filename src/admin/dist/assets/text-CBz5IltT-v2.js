import{l as k,m as r,d as T,n as g,a as s,c as n,r as a,L as R,p as m,q as h,X as S,y as V,D,E as u,bv as P,ap as w}from"./index-DcSM7zMd-v2.js";import{u as E}from"./Space-D4bCZDRE-v2.js";var _=k("text",`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
`,[r("strong",`
 font-weight: var(--n-font-weight-strong);
 `),r("italic",{fontStyle:"italic"}),r("underline",{textDecoration:"underline"}),r("code",`
 line-height: 1.4;
 display: inline-block;
 font-family: var(--n-font-famliy-mono);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 box-sizing: border-box;
 padding: .05em .35em 0 .35em;
 border-radius: var(--n-code-border-radius);
 font-size: .9em;
 color: var(--n-code-text-color);
 background-color: var(--n-code-color);
 border: var(--n-code-border);
 `)]);const F={...g.props,code:Boolean,type:{type:String,default:"default"},delete:Boolean,strong:Boolean,italic:Boolean,underline:Boolean,depth:[String,Number],tag:String,as:{type:String,validator:()=>!0,default:void 0}};var M=T({name:"Text",props:F,setup(e){const{mergedClsPrefixRef:o,inlineThemeDisabled:t}=V(e),f=g("Typography","-text",_,P,e,o),l=u(()=>{const{depth:d,type:c}=e,x=c==="default"?d===void 0?"textColor":`textColor${d}Depth`:w("textColor",c),{common:{fontWeightStrong:y,fontFamilyMono:b,cubicBezierEaseInOut:p},self:{codeTextColor:v,codeBorderRadius:C,codeColor:z,codeBorder:B,[x]:$}}=f.value;return{"--n-bezier":p,"--n-text-color":$,"--n-font-weight-strong":y,"--n-font-famliy-mono":b,"--n-code-border-radius":C,"--n-code-text-color":v,"--n-code-color":z,"--n-code-border":B}}),i=t?D("text",u(()=>`${e.type[0]}${e.depth||""}`),l,e):void 0;return{mergedClsPrefix:o,compitableTag:E(e,["as","tag"]),cssVars:t?void 0:l,themeClass:i?.themeClass,onRender:i?.onRender}},render(){const{mergedClsPrefix:e}=this;this.onRender?.();const o=[`${e}-text`,this.themeClass,{[`${e}-text--code`]:this.code,[`${e}-text--delete`]:this.delete,[`${e}-text--strong`]:this.strong,[`${e}-text--italic`]:this.italic,[`${e}-text--underline`]:this.underline}],t=this.$slots.default?.();return this.code?(s(),n("code",{key:1,class:h(o),style:m(this.cssVars)},[this.delete?(s(),n("del",{key:0},[a(()=>t)])):(s(),n(R,{key:1},[a(()=>t)],64))],6)):this.delete?(s(),n("del",{key:2,class:h(o),style:m(this.cssVars)},[a(()=>t)],6)):S(this.compitableTag||"span",{class:o,style:this.cssVars},t)}});export{M as t};
