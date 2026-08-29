import{h as lo,s as io,i as ao,j as Ae,k as ie,l as s,m as z,d as L,n as Z,a as d,c as w,p as U,q as k,r as R,t as T,v as Fe,x as J,S as Le,y as ue,z as Me,D as ve,E as g,F,G as re,H as c,I as x,J as j,K as Oe,L as D,M as X,N as de,O,P as ne,Q as co,R as ze,T as te,U as be,V as we,W as so,X as le,Y as he,Z as uo,_ as Ne,$ as vo,a0 as mo,u as ho,a1 as fo,o as po,f as go,a2 as bo,w as W,b as Y,e as K,a3 as fe,g as He,a4 as xo,B as Co,a5 as yo,a6 as zo,a7 as wo}from"./index-DcSM7zMd-v2.js";import{T as So}from"./Tag-D_myid6E-v2.js";import{u as Io,S as Ro}from"./Space-D4bCZDRE-v2.js";import{f as pe}from"./format-length-B9rBjcGe-v2.js";import{C as _o}from"./ChevronRight-fsUiuOuh-v2.js";import{u as xe}from"./use-merged-state-DhCu5lfq-v2.js";import{T as ko}from"./Tooltip-D7ucjWdi-v2.js";import{D as Po}from"./Dropdown-BEKWdUb--v2.js";import{V as To,c as ge}from"./create-BEyCP4Lb-v2.js";import{_ as Ao}from"./_plugin-vue_export-helper-DlAUqK2U-v2.js";import"./Popover-DCn8ko3l-v2.js";import"./next-frame-once-C5Ksf8W7-v2.js";import"./happens-in-CM8LO42l-v2.js";function No(e){const{baseColor:r,textColor2:n,bodyColor:a,cardColor:i,dividerColor:t,actionColor:u,scrollbarColor:v,scrollbarColorHover:m,invertedColor:f}=e;return{textColor:n,textColorInverted:"#FFF",color:a,colorEmbedded:u,headerColor:i,headerColorInverted:f,footerColor:u,footerColorInverted:f,headerBorderColor:t,headerBorderColorInverted:f,footerBorderColor:t,footerBorderColorInverted:f,siderBorderColor:t,siderBorderColorInverted:f,siderColor:i,siderColorInverted:f,siderToggleButtonBorder:`1px solid ${t}`,siderToggleButtonColor:r,siderToggleButtonIconColor:n,siderToggleButtonIconColorInverted:n,siderToggleBarColor:Ae(a,v),siderToggleBarColorHover:Ae(a,m),__invertScrollbar:"true"}}const Se=lo({name:"Layout",common:ao,peers:{Scrollbar:io},self:No}),Ke=ie("n-layout-sider"),Ie={type:String,default:"static"};var Ho=s("layout",`
 color: var(--n-text-color);
 background-color: var(--n-color);
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 flex: auto;
 overflow: hidden;
 transition:
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
`,[s("layout-scroll-container",`
 overflow-x: hidden;
 box-sizing: border-box;
 height: 100%;
 `),z("absolute-positioned",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)]);const Bo={embedded:Boolean,position:Ie,nativeScrollbar:{type:Boolean,default:!0},scrollbarProps:Object,onScroll:Function,contentClass:String,contentStyle:{type:[String,Object],default:""},hasSider:Boolean,siderPlacement:{type:String,default:"left"}},Ve=ie("n-layout");function De(e){return L({name:e?"LayoutContent":"Layout",props:{...Z.props,...Bo},setup(r){const n=F(null),a=F(null),{mergedClsPrefixRef:i,inlineThemeDisabled:t}=ue(r),u=Z("Layout","-layout",Ho,Se,r,i);function v(_,A){if(r.nativeScrollbar){const{value:H}=n;H&&(A===void 0?H.scrollTo(_):H.scrollTo(_,A))}else{const{value:H}=a;H&&H.scrollTo(_,A)}}re(Ve,r);let m=0,f=0;const b=_=>{const A=_.target;m=A.scrollLeft,f=A.scrollTop,r.onScroll?.(_)};Me(()=>{if(r.nativeScrollbar){const _=n.value;_&&(_.scrollTop=f,_.scrollLeft=m)}});const S={display:"flex",flexWrap:"nowrap",width:"100%",flexDirection:"row"},C={scrollTo:v},N=g(()=>{const{common:{cubicBezierEaseInOut:_},self:A}=u.value;return{"--n-bezier":_,"--n-color":r.embedded?A.colorEmbedded:A.color,"--n-text-color":A.textColor}}),M=t?ve("layout",g(()=>r.embedded?"e":""),N,r):void 0;return{mergedClsPrefix:i,scrollableElRef:n,scrollbarInstRef:a,hasSiderStyle:S,mergedTheme:u,handleNativeElScroll:b,cssVars:t?void 0:N,themeClass:M?.themeClass,onRender:M?.onRender,...C}},render(){const{mergedClsPrefix:r,hasSider:n}=this;this.onRender?.();const a=n?this.hasSiderStyle:void 0,i=[this.themeClass,e&&`${r}-layout-content`,`${r}-layout`,`${r}-layout--${this.position}-positioned`];return d(),w("div",{class:k(i),style:U(this.cssVars)},[this.nativeScrollbar?(d(),w("div",{key:0,ref:"scrollableElRef",class:k([`${r}-layout-scroll-container`,this.contentClass]),style:U([this.contentStyle,a]),onScroll:this.handleNativeElScroll},[R(()=>this.$slots.default?.())],46,["onScroll"])):(d(),T(Le,J({key:1},this.scrollbarProps,{onScroll:this.onScroll,ref:"scrollbarInstRef",theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar,contentClass:this.contentClass,contentStyle:[this.contentStyle,a]}),Fe(this.$slots),1040,["onScroll","theme","themeOverrides","contentClass","contentStyle"]))],6)}})}var Be=De(!1),Eo=De(!0),$o=s("layout-header",`
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 box-sizing: border-box;
 width: 100%;
 background-color: var(--n-color);
 color: var(--n-text-color);
`,[z("absolute-positioned",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 `),z("bordered",`
 border-bottom: solid 1px var(--n-border-color);
 `)]);const Fo={position:Ie,inverted:Boolean,bordered:Boolean};var Lo=L({name:"LayoutHeader",props:{...Z.props,...Fo},setup(e){const{mergedClsPrefixRef:r,inlineThemeDisabled:n}=ue(e),a=Z("Layout","-layout-header",$o,Se,e,r),i=g(()=>{const{common:{cubicBezierEaseInOut:u},self:v}=a.value,m={"--n-bezier":u};return e.inverted?(m["--n-color"]=v.headerColorInverted,m["--n-text-color"]=v.textColorInverted,m["--n-border-color"]=v.headerBorderColorInverted):(m["--n-color"]=v.headerColor,m["--n-text-color"]=v.textColor,m["--n-border-color"]=v.headerBorderColor),m}),t=n?ve("layout-header",g(()=>e.inverted?"a":"b"),i,e):void 0;return{mergedClsPrefix:r,cssVars:n?void 0:i,themeClass:t?.themeClass,onRender:t?.onRender}},render(){const{mergedClsPrefix:e}=this;return this.onRender?.(),d(),w("div",{class:k([`${e}-layout-header`,this.themeClass,this.position&&`${e}-layout-header--${this.position}-positioned`,this.bordered&&`${e}-layout-header--bordered`]),style:U(this.cssVars)},[R(()=>this.$slots.default?.())],6)}}),Mo=s("layout-sider",`
 flex-shrink: 0;
 box-sizing: border-box;
 position: relative;
 z-index: 1;
 color: var(--n-text-color);
 transition:
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 min-width .3s var(--n-bezier),
 max-width .3s var(--n-bezier),
 transform .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 background-color: var(--n-color);
 display: flex;
 justify-content: flex-end;
`,[z("bordered",[c("border",`
 content: "";
 position: absolute;
 top: 0;
 bottom: 0;
 width: 1px;
 background-color: var(--n-border-color);
 transition: background-color .3s var(--n-bezier);
 `)]),c("left-placement",[z("bordered",[c("border",`
 right: 0;
 `)])]),z("right-placement",`
 justify-content: flex-start;
 `,[z("bordered",[c("border",`
 left: 0;
 `)]),z("collapsed",[s("layout-toggle-button",[s("base-icon",`
 transform: rotate(180deg);
 `)]),s("layout-toggle-bar",[x("&:hover",[c("top",{transform:"rotate(-12deg) scale(1.15) translateY(-2px)"}),c("bottom",{transform:"rotate(12deg) scale(1.15) translateY(2px)"})])])]),s("layout-toggle-button",`
 left: 0;
 transform: translateX(-50%) translateY(-50%);
 `,[s("base-icon",`
 transform: rotate(0);
 `)]),s("layout-toggle-bar",`
 left: -28px;
 transform: rotate(180deg);
 `,[x("&:hover",[c("top",{transform:"rotate(12deg) scale(1.15) translateY(-2px)"}),c("bottom",{transform:"rotate(-12deg) scale(1.15) translateY(2px)"})])])]),z("collapsed",[s("layout-toggle-bar",[x("&:hover",[c("top",{transform:"rotate(-12deg) scale(1.15) translateY(-2px)"}),c("bottom",{transform:"rotate(12deg) scale(1.15) translateY(2px)"})])]),s("layout-toggle-button",[s("base-icon",`
 transform: rotate(0);
 `)])]),s("layout-toggle-button",`
 transition:
 color .3s var(--n-bezier),
 right .3s var(--n-bezier),
 left .3s var(--n-bezier),
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 cursor: pointer;
 width: 24px;
 height: 24px;
 position: absolute;
 top: 50%;
 right: 0;
 border-radius: 50%;
 display: flex;
 align-items: center;
 justify-content: center;
 font-size: 18px;
 color: var(--n-toggle-button-icon-color);
 border: var(--n-toggle-button-border);
 background-color: var(--n-toggle-button-color);
 box-shadow: 0 2px 4px 0px rgba(0, 0, 0, .06);
 transform: translateX(50%) translateY(-50%);
 z-index: 1;
 `,[s("base-icon",`
 transition: transform .3s var(--n-bezier);
 transform: rotate(180deg);
 `)]),s("layout-toggle-bar",`
 cursor: pointer;
 height: 72px;
 width: 32px;
 position: absolute;
 top: calc(50% - 36px);
 right: -28px;
 `,[c("top, bottom",`
 position: absolute;
 width: 4px;
 border-radius: 2px;
 height: 38px;
 left: 14px;
 transition: 
 background-color .3s var(--n-bezier),
 transform .3s var(--n-bezier);
 `),c("bottom",`
 position: absolute;
 top: 34px;
 `),x("&:hover",[c("top",{transform:"rotate(12deg) scale(1.15) translateY(-2px)"}),c("bottom",{transform:"rotate(-12deg) scale(1.15) translateY(2px)"})]),c("top, bottom",{backgroundColor:"var(--n-toggle-bar-color)"}),x("&:hover",[c("top, bottom",{backgroundColor:"var(--n-toggle-bar-color-hover)"})])]),c("border",`
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 width: 1px;
 transition: background-color .3s var(--n-bezier);
 `),s("layout-sider-scroll-container",`
 flex-grow: 1;
 flex-shrink: 0;
 box-sizing: border-box;
 height: 100%;
 opacity: 0;
 transition: opacity .3s var(--n-bezier);
 max-width: 100%;
 `),z("show-content",[s("layout-sider-scroll-container",{opacity:1})]),z("absolute-positioned",`
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 `)]);const Oo=["onClick"];var Ko=L({props:{clsPrefix:{type:String,required:!0},onClick:Function},render(){const{clsPrefix:e}=this;return d(),w("div",{onClick:this.onClick,class:k(`${e}-layout-toggle-bar`)},[j("div",{class:k(`${e}-layout-toggle-bar__top`)},null,2),j("div",{class:k(`${e}-layout-toggle-bar__bottom`)},null,2)],10,Oo)}});const Vo=["onClick"];var Do=L({name:"LayoutToggleButton",props:{clsPrefix:{type:String,required:!0},onClick:Function},render(){const{clsPrefix:e}=this;return d(),w("div",{class:k(`${e}-layout-toggle-button`),onClick:this.onClick},[(d(),T(Oe,{clsPrefix:e},{default:()=>(d(),T(_o))},1032,["clsPrefix"]))],10,Vo)}});const Uo=["onTransitionend"],jo={position:Ie,bordered:Boolean,collapsedWidth:{type:Number,default:48},width:{type:[Number,String],default:272},contentClass:String,contentStyle:{type:[String,Object],default:""},collapseMode:{type:String,default:"transform"},collapsed:{type:Boolean,default:void 0},defaultCollapsed:Boolean,showCollapsedContent:{type:Boolean,default:!0},showTrigger:{type:[Boolean,String],default:!1},nativeScrollbar:{type:Boolean,default:!0},inverted:Boolean,scrollbarProps:Object,triggerClass:String,triggerStyle:[String,Object],collapsedTriggerClass:String,collapsedTriggerStyle:[String,Object],"onUpdate:collapsed":[Function,Array],onUpdateCollapsed:[Function,Array],onAfterEnter:Function,onAfterLeave:Function,onExpand:[Function,Array],onCollapse:[Function,Array],onScroll:Function};var Go=L({name:"LayoutSider",props:{...Z.props,...jo},setup(e){const r=X(Ve),n=F(null),a=F(null),i=F(e.defaultCollapsed),t=xe(de(e,"collapsed"),i),u=g(()=>pe(t.value?e.collapsedWidth:e.width)),v=g(()=>e.collapseMode!=="transform"?{}:{minWidth:pe(e.width)}),m=g(()=>r?r.siderPlacement:"left");function f(P,I){if(e.nativeScrollbar){const{value:B}=n;B&&(I===void 0?B.scrollTo(P):B.scrollTo(P,I))}else{const{value:B}=a;B&&B.scrollTo(P,I)}}function b(){const{"onUpdate:collapsed":P,onUpdateCollapsed:I,onExpand:B,onCollapse:q}=e,{value:V}=t;I&&O(I,!V),P&&O(P,!V),i.value=!V,V?B&&O(B):q&&O(q)}let S=0,C=0;const N=P=>{const I=P.target;S=I.scrollLeft,C=I.scrollTop,e.onScroll?.(P)};Me(()=>{if(e.nativeScrollbar){const P=n.value;P&&(P.scrollTop=C,P.scrollLeft=S)}}),re(Ke,{collapsedRef:t,collapseModeRef:de(e,"collapseMode")});const{mergedClsPrefixRef:M,inlineThemeDisabled:_}=ue(e),A=Z("Layout","-layout-sider",Mo,Se,e,M);function H(P){P.propertyName==="max-width"&&(t.value?e.onAfterLeave?.():e.onAfterEnter?.())}const ee={scrollTo:f},G=g(()=>{const{common:{cubicBezierEaseInOut:P},self:I}=A.value,{siderToggleButtonColor:B,siderToggleButtonBorder:q,siderToggleBarColor:V,siderToggleBarColorHover:me}=I,E={"--n-bezier":P,"--n-toggle-button-color":B,"--n-toggle-button-border":q,"--n-toggle-bar-color":V,"--n-toggle-bar-color-hover":me};return e.inverted?(E["--n-color"]=I.siderColorInverted,E["--n-text-color"]=I.textColorInverted,E["--n-border-color"]=I.siderBorderColorInverted,E["--n-toggle-button-icon-color"]=I.siderToggleButtonIconColorInverted,E.__invertScrollbar=I.__invertScrollbar):(E["--n-color"]=I.siderColor,E["--n-text-color"]=I.textColor,E["--n-border-color"]=I.siderBorderColor,E["--n-toggle-button-icon-color"]=I.siderToggleButtonIconColor),E}),oe=_?ve("layout-sider",g(()=>e.inverted?"a":"b"),G,e):void 0;return{scrollableElRef:n,scrollbarInstRef:a,mergedClsPrefix:M,mergedTheme:A,styleMaxWidth:u,mergedCollapsed:t,scrollContainerStyle:v,siderPlacement:m,handleNativeElScroll:N,handleTransitionend:H,handleTriggerClick:b,inlineThemeDisabled:_,cssVars:G,themeClass:oe?.themeClass,onRender:oe?.onRender,...ee}},render(){const{mergedClsPrefix:e,mergedCollapsed:r,showTrigger:n}=this;return this.onRender?.(),d(),w("aside",{class:k([`${e}-layout-sider`,this.themeClass,`${e}-layout-sider--${this.position}-positioned`,`${e}-layout-sider--${this.siderPlacement}-placement`,this.bordered&&`${e}-layout-sider--bordered`,r&&`${e}-layout-sider--collapsed`,(!r||this.showCollapsedContent)&&`${e}-layout-sider--show-content`]),onTransitionend:this.handleTransitionend,style:U([this.inlineThemeDisabled?void 0:this.cssVars,{maxWidth:this.styleMaxWidth,width:pe(this.width)}])},[this.nativeScrollbar?(d(),w("div",{key:1,class:k([`${e}-layout-sider-scroll-container`,this.contentClass]),onScroll:this.handleNativeElScroll,style:U([this.scrollContainerStyle,{overflow:"auto"},this.contentStyle]),ref:"scrollableElRef"},[R(()=>this.$slots.default?.())],46,["onScroll"])):(d(),T(Le,J({key:0},this.scrollbarProps,{onScroll:this.onScroll,ref:"scrollbarInstRef",style:this.scrollContainerStyle,contentStyle:this.contentStyle,contentClass:this.contentClass,theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar,builtinThemeOverrides:this.inverted&&this.cssVars.__invertScrollbar==="true"?{colorHover:"rgba(255, 255, 255, .4)",color:"rgba(255, 255, 255, .3)"}:void 0}),Fe(this.$slots),1040,["onScroll","style","contentStyle","contentClass","theme","themeOverrides","builtinThemeOverrides"])),n?(d(),w(D,{key:2},[n==="bar"?(d(),T(Ko,{key:0,clsPrefix:e,class:k(r?this.collapsedTriggerClass:this.triggerClass),style:U(r?this.collapsedTriggerStyle:this.triggerStyle),onClick:this.handleTriggerClick},null,8,["clsPrefix","class","style","onClick"])):(d(),T(Do,{key:1,clsPrefix:e,class:k(r?this.collapsedTriggerClass:this.triggerClass),style:U(r?this.collapsedTriggerStyle:this.triggerStyle),onClick:this.handleTriggerClick},null,8,["clsPrefix","class","style","onClick"]))],64)):R(()=>null),this.bordered?(d(),w("div",{key:4,class:k(`${e}-layout-sider__border`)},null,2)):R(()=>null)],46,Uo)}});const ae=ie("n-menu"),Ue=ie("n-submenu"),Re=ie("n-menu-item-group"),Ee=[x("&::before","background-color: var(--n-item-color-hover);"),c("arrow",`
 color: var(--n-arrow-color-hover);
 `),c("icon",`
 color: var(--n-item-icon-color-hover);
 `),s("menu-item-content-header",`
 color: var(--n-item-text-color-hover);
 `,[x("a",`
 color: var(--n-item-text-color-hover);
 `),c("extra",`
 color: var(--n-item-text-color-hover);
 `)])],$e=[c("icon",`
 color: var(--n-item-icon-color-hover-horizontal);
 `),s("menu-item-content-header",`
 color: var(--n-item-text-color-hover-horizontal);
 `,[x("a",`
 color: var(--n-item-text-color-hover-horizontal);
 `),c("extra",`
 color: var(--n-item-text-color-hover-horizontal);
 `)])];var qo=x([s("menu",`
 background-color: var(--n-color);
 color: var(--n-item-text-color);
 overflow: hidden;
 transition: background-color .3s var(--n-bezier);
 box-sizing: border-box;
 font-size: var(--n-font-size);
 padding-bottom: 6px;
 `,[z("horizontal",`
 max-width: 100%;
 width: 100%;
 display: flex;
 overflow: hidden;
 padding-bottom: 0;
 `,[s("submenu","margin: 0;"),s("menu-item","margin: 0;"),s("menu-item-content",`
 padding: 0 20px;
 border-bottom: 2px solid #0000;
 `,[x("&::before","display: none;"),z("selected","border-bottom: 2px solid var(--n-border-color-horizontal)")]),s("menu-item-content",[z("selected",[c("icon","color: var(--n-item-icon-color-active-horizontal);"),s("menu-item-content-header",`
 color: var(--n-item-text-color-active-horizontal);
 `,[x("a","color: var(--n-item-text-color-active-horizontal);"),c("extra","color: var(--n-item-text-color-active-horizontal);")])]),z("child-active",`
 border-bottom: 2px solid var(--n-border-color-horizontal);
 `,[s("menu-item-content-header",`
 color: var(--n-item-text-color-child-active-horizontal);
 `,[x("a",`
 color: var(--n-item-text-color-child-active-horizontal);
 `),c("extra",`
 color: var(--n-item-text-color-child-active-horizontal);
 `)]),c("icon",`
 color: var(--n-item-icon-color-child-active-horizontal);
 `)]),ne("disabled",[ne("selected, child-active",[x("&:focus-within",$e)]),z("selected",[Q(null,[c("icon","color: var(--n-item-icon-color-active-hover-horizontal);"),s("menu-item-content-header",`
 color: var(--n-item-text-color-active-hover-horizontal);
 `,[x("a","color: var(--n-item-text-color-active-hover-horizontal);"),c("extra","color: var(--n-item-text-color-active-hover-horizontal);")])])]),z("child-active",[Q(null,[c("icon","color: var(--n-item-icon-color-child-active-hover-horizontal);"),s("menu-item-content-header",`
 color: var(--n-item-text-color-child-active-hover-horizontal);
 `,[x("a","color: var(--n-item-text-color-child-active-hover-horizontal);"),c("extra","color: var(--n-item-text-color-child-active-hover-horizontal);")])])]),Q("border-bottom: 2px solid var(--n-border-color-horizontal);",$e)]),s("menu-item-content-header",[x("a","color: var(--n-item-text-color-horizontal);")])])]),ne("responsive",[s("menu-item-content-header",`
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),z("collapsed",[s("menu-item-content",[z("selected",[x("&::before",`
 background-color: var(--n-item-color-active-collapsed) !important;
 `)]),s("menu-item-content-header","opacity: 0;"),c("arrow","opacity: 0;"),c("icon","color: var(--n-item-icon-color-collapsed);")])]),s("menu-item",`
 height: var(--n-item-height);
 margin-top: 6px;
 position: relative;
 `),s("menu-item-content",`
 box-sizing: border-box;
 line-height: 1.75;
 height: 100%;
 display: grid;
 grid-template-areas: "icon content arrow";
 grid-template-columns: auto 1fr auto;
 align-items: center;
 cursor: pointer;
 position: relative;
 padding-right: 18px;
 transition:
 background-color .3s var(--n-bezier),
 padding-left .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[x("> *","z-index: 1;"),x("&::before",`
 z-index: auto;
 content: "";
 background-color: #0000;
 position: absolute;
 left: 8px;
 right: 8px;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),z("disabled",`
 opacity: .45;
 cursor: not-allowed;
 `),z("collapsed",[c("arrow","transform: rotate(0);")]),z("selected",[x("&::before","background-color: var(--n-item-color-active);"),c("arrow","color: var(--n-arrow-color-active);"),c("icon","color: var(--n-item-icon-color-active);"),s("menu-item-content-header",`
 color: var(--n-item-text-color-active);
 `,[x("a","color: var(--n-item-text-color-active);"),c("extra","color: var(--n-item-text-color-active);")])]),z("child-active",[s("menu-item-content-header",`
 color: var(--n-item-text-color-child-active);
 `,[x("a",`
 color: var(--n-item-text-color-child-active);
 `),c("extra",`
 color: var(--n-item-text-color-child-active);
 `)]),c("arrow",`
 color: var(--n-arrow-color-child-active);
 `),c("icon",`
 color: var(--n-item-icon-color-child-active);
 `)]),ne("disabled",[ne("selected, child-active",[x("&:focus-within",Ee)]),z("selected",[Q(null,[c("arrow","color: var(--n-arrow-color-active-hover);"),c("icon","color: var(--n-item-icon-color-active-hover);"),s("menu-item-content-header",`
 color: var(--n-item-text-color-active-hover);
 `,[x("a","color: var(--n-item-text-color-active-hover);"),c("extra","color: var(--n-item-text-color-active-hover);")])])]),z("child-active",[Q(null,[c("arrow","color: var(--n-arrow-color-child-active-hover);"),c("icon","color: var(--n-item-icon-color-child-active-hover);"),s("menu-item-content-header",`
 color: var(--n-item-text-color-child-active-hover);
 `,[x("a","color: var(--n-item-text-color-child-active-hover);"),c("extra","color: var(--n-item-text-color-child-active-hover);")])])]),z("selected",[Q(null,[x("&::before","background-color: var(--n-item-color-active-hover);")])]),Q(null,Ee)]),c("icon",`
 grid-area: icon;
 color: var(--n-item-icon-color);
 transition:
 color .3s var(--n-bezier),
 font-size .3s var(--n-bezier),
 margin-right .3s var(--n-bezier);
 box-sizing: content-box;
 display: inline-flex;
 align-items: center;
 justify-content: center;
 `),c("arrow",`
 grid-area: arrow;
 font-size: 16px;
 color: var(--n-arrow-color);
 transform: rotate(180deg);
 opacity: 1;
 transition:
 color .3s var(--n-bezier),
 transform 0.2s var(--n-bezier),
 opacity 0.2s var(--n-bezier);
 `),s("menu-item-content-header",`
 grid-area: content;
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 opacity: 1;
 white-space: nowrap;
 color: var(--n-item-text-color);
 `,[x("a",`
 outline: none;
 text-decoration: none;
 transition: color .3s var(--n-bezier);
 color: var(--n-item-text-color);
 `,[x("&::before",`
 content: "";
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)]),c("extra",`
 font-size: .93em;
 color: var(--n-group-text-color);
 transition: color .3s var(--n-bezier);
 `)])]),s("submenu",`
 cursor: pointer;
 position: relative;
 margin-top: 6px;
 `,[s("menu-item-content",`
 height: var(--n-item-height);
 `),s("submenu-children",`
 overflow: hidden;
 padding: 0;
 `,[co({duration:".2s"})])]),s("menu-item-group",[s("menu-item-group-title",`
 margin-top: 6px;
 color: var(--n-group-text-color);
 cursor: default;
 font-size: .93em;
 height: 36px;
 display: flex;
 align-items: center;
 transition:
 padding-left .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `)])]),s("menu-tooltip",[x("a",`
 color: inherit;
 text-decoration: none;
 `)]),s("menu-divider",`
 transition: background-color .3s var(--n-bezier);
 background-color: var(--n-divider-color);
 height: 1px;
 margin: 6px 18px;
 `)]);function Q(e,r){return[z("hover",e,r),x("&:hover",e,r)]}var Wo=L({name:"MenuDivider",setup(){const{mergedClsPrefixRef:e,isHorizontalRef:r}=X(ae);return()=>r.value?null:(d(),w("div",{key:1,class:k(`${e.value}-menu-divider`)},null,2))}}),Yo=L({name:"ChevronDownFilled",render(){return(()=>{const e=ze("f3af82a2aab086a5");return e[0]||(e[0]=j("svg",{viewBox:"0 0 16 16",fill:"none",xmlns:"http://www.w3.org/2000/svg"},[j("path",{d:"M3.20041 5.73966C3.48226 5.43613 3.95681 5.41856 4.26034 5.70041L8 9.22652L11.7397 5.70041C12.0432 5.41856 12.5177 5.43613 12.7996 5.73966C13.0815 6.0432 13.0639 6.51775 12.7603 6.7996L8.51034 10.7996C8.22258 11.0668 7.77743 11.0668 7.48967 10.7996L3.23966 6.7996C2.93613 6.51775 2.91856 6.0432 3.20041 5.73966Z",fill:"currentColor"})],-1))})()}});const Xo=["onClick"];var je=L({name:"MenuOptionContent",props:{collapsed:Boolean,disabled:Boolean,title:[String,Function],icon:Function,extra:[String,Function],showArrow:Boolean,childActive:Boolean,hover:Boolean,paddingLeft:Number,selected:Boolean,maxIconSize:{type:Number,required:!0},activeIconSize:{type:Number,required:!0},iconMarginRight:{type:Number,required:!0},clsPrefix:{type:String,required:!0},onClick:Function,tmNode:{type:Object,required:!0},isEllipsisPlaceholder:Boolean},setup(e){const{props:r}=X(ae);return{menuProps:r,style:g(()=>{const{paddingLeft:n}=e;return{paddingLeft:n&&`${n}px`}}),iconStyle:g(()=>{const{maxIconSize:n,activeIconSize:a,iconMarginRight:i}=e;return{width:`${n}px`,height:`${n}px`,fontSize:`${a}px`,marginRight:`${i}px`}})}},render(){const{clsPrefix:e,tmNode:r,menuProps:{renderIcon:n,renderLabel:a,renderExtra:i,expandIcon:t}}=this,u=n?n(r.rawNode):te(this.icon);return(()=>{const v=ze("7bb10afc6caf8fa4");return d(),w("div",{onClick:m=>{this.onClick?.(m)},role:"none",class:k([`${e}-menu-item-content`,{[`${e}-menu-item-content--selected`]:this.selected,[`${e}-menu-item-content--collapsed`]:this.collapsed,[`${e}-menu-item-content--child-active`]:this.childActive,[`${e}-menu-item-content--disabled`]:this.disabled,[`${e}-menu-item-content--hover`]:this.hover}]),style:U(this.style)},[R(()=>u&&(d(),w("div",{class:k(`${e}-menu-item-content__icon`),style:U(this.iconStyle),role:"none"},[R(()=>[u])],6))),j("div",{class:k(`${e}-menu-item-content-header`),role:"none"},[this.isEllipsisPlaceholder?(d(),w(D,{key:0},[R(()=>this.title)],64)):(d(),w(D,{key:1},[a?(d(),w(D,{key:0},[R(()=>a(r.rawNode))],64)):(d(),w(D,{key:1},[R(()=>te(this.title))],64))],64)),this.extra||i?(d(),w("span",{key:2,class:k(`${e}-menu-item-content-header__extra`)},[v[0]||(v[0]=R(" ",-1)),i?(d(),w(D,{key:0},[R(()=>i(r.rawNode))],64)):(d(),w(D,{key:1},[R(()=>te(this.extra))],64))],2)):R(()=>null)],2),this.showArrow?(d(),T(Oe,{key:0,ariaHidden:!0,class:k(`${e}-menu-item-content__arrow`),clsPrefix:e},{default:()=>t?t(r.rawNode):(d(),T(Yo,{key:1}))},1032,["class","clsPrefix"])):R(()=>null)],14,Xo)})()}});const se=8;function _e(e){const r=X(ae),{props:n,mergedCollapsedRef:a}=r,i=X(Ue,null),t=X(Re,null),u=g(()=>n.mode==="horizontal"),v=g(()=>u.value?n.dropdownPlacement:"tmNodes"in e?"right-start":"right"),m=g(()=>Math.max(n.collapsedIconSize??n.iconSize,n.iconSize));return{dropdownPlacement:v,activeIconSize:g(()=>!u.value&&e.root&&a.value?n.collapsedIconSize??n.iconSize:n.iconSize),maxIconSize:m,paddingLeft:g(()=>{if(u.value)return;const{collapsedWidth:f,indent:b,rootIndent:S}=n,{root:C,isGroup:N}=e,M=S===void 0?b:S;return C?a.value?f/2-m.value/2:M:t&&typeof t.paddingLeftRef.value=="number"?a.value?f/2-m.value/2:b/2+t.paddingLeftRef.value:i&&typeof i.paddingLeftRef.value=="number"?(N?b/2:b)+i.paddingLeftRef.value:0}),iconMarginRight:g(()=>{const{collapsedWidth:f,indent:b,rootIndent:S}=n,{value:C}=m,{root:N}=e;return u.value||!N||!a.value?se:(S===void 0?b:S)+C+se-(f+C)/2}),NMenu:r,NSubmenu:i,NMenuOptionGroup:t}}const ke={internalKey:{type:[String,Number],required:!0},root:Boolean,isGroup:Boolean,level:{type:Number,required:!0},title:[String,Function],extra:[String,Function]},Ge={...ke,tmNode:{type:Object,required:!0},disabled:Boolean,icon:Function,onClick:Function},Zo=we(Ge),Jo=L({name:"MenuOption",props:Ge,setup(e){const r=_e(e),{NSubmenu:n,NMenu:a,NMenuOptionGroup:i}=r,{props:t,mergedClsPrefixRef:u,mergedCollapsedRef:v}=a,m=n?n.mergedDisabledRef:i?i.mergedDisabledRef:{value:!1},f=g(()=>m.value||e.disabled);function b(C){const{onClick:N}=e;N&&N(C)}function S(C){f.value||(a.doSelect(e.internalKey,e.tmNode.rawNode),b(C))}return{mergedClsPrefix:u,dropdownPlacement:r.dropdownPlacement,paddingLeft:r.paddingLeft,iconMarginRight:r.iconMarginRight,maxIconSize:r.maxIconSize,activeIconSize:r.activeIconSize,mergedTheme:a.mergedThemeRef,menuProps:t,dropdownEnabled:be(()=>e.root&&v.value&&t.mode!=="horizontal"&&!f.value),selected:be(()=>a.mergedValueRef.value===e.internalKey),mergedDisabled:f,handleClick:S}},render(){const{mergedClsPrefix:e,mergedTheme:r,tmNode:n,menuProps:{renderLabel:a,nodeProps:i}}=this,t=i?.(n.rawNode);return d(),w("div",J(t,{role:"menuitem",class:[`${e}-menu-item`,t?.class]}),[(d(),T(ko,{theme:r.peers.Tooltip,themeOverrides:r.peerOverrides.Tooltip,trigger:"hover",placement:this.dropdownPlacement,disabled:!this.dropdownEnabled||this.title===void 0,internalExtraClass:["menu-tooltip"]},{default:()=>a?a(n.rawNode):te(this.title),trigger:()=>(d(),T(je,{tmNode:n,clsPrefix:e,paddingLeft:this.paddingLeft,iconMarginRight:this.iconMarginRight,maxIconSize:this.maxIconSize,activeIconSize:this.activeIconSize,selected:this.selected,title:this.title,extra:this.extra,disabled:this.mergedDisabled,icon:this.icon,onClick:this.handleClick},null,8,["tmNode","clsPrefix","paddingLeft","iconMarginRight","maxIconSize","activeIconSize","selected","title","extra","disabled","icon","onClick"]))},1032,["theme","themeOverrides","placement","disabled"]))],16)}}),qe={...ke,tmNode:{type:Object,required:!0},tmNodes:{type:Array,required:!0}},Qo=we(qe),et=L({name:"MenuOptionGroup",props:qe,setup(e){const r=_e(e),{NSubmenu:n}=r,a=g(()=>n?.mergedDisabledRef.value?!0:e.tmNode.disabled);re(Re,{paddingLeftRef:r.paddingLeft,mergedDisabledRef:a});const{mergedClsPrefixRef:i,props:t}=X(ae);return function(){const{value:u}=i,v=r.paddingLeft.value,{nodeProps:m}=t,f=m?.(e.tmNode.rawNode);return(()=>{const b=ze("45eca6a63be5028b");return d(),w("div",{class:k(`${u}-menu-item-group`),role:"group"},[j("div",J(f,{class:[`${u}-menu-item-group-title`,f?.class],style:[f?.style||"",v!==void 0?`padding-left: ${v}px;`:""]}),[R(()=>te(e.title)),e.extra?(d(),w(D,{key:0},[b[0]||(b[0]=R(" ",-1)),R(()=>te(e.extra))],64)):R(()=>null)],16),j("div",null,[R(()=>e.tmNodes.map(S=>Pe(S,t)))])],2)})()}}}),ot=["aria-expanded","id"],tt=["aria-expanded","id"],We={...ke,rawNodes:{type:Array,default:()=>[]},tmNodes:{type:Array,default:()=>[]},tmNode:{type:Object,required:!0},disabled:Boolean,icon:Function,onClick:Function,domId:String,virtualChildActive:{type:Boolean,default:void 0},isEllipsisPlaceholder:Boolean},rt=we(We),Ce=L({name:"Submenu",props:We,setup(e){const r=_e(e),{NMenu:n,NSubmenu:a}=r,{props:i,mergedCollapsedRef:t,mergedThemeRef:u}=n,v=g(()=>{const{disabled:C}=e;return a?.mergedDisabledRef.value||i.disabled?!0:C}),m=F(!1);re(Ue,{paddingLeftRef:r.paddingLeft,mergedDisabledRef:v}),re(Re,null);function f(){const{onClick:C}=e;C&&C()}function b(){v.value||(t.value||n.toggleExpand(e.internalKey),f())}function S(C){m.value=C}return{menuProps:i,mergedTheme:u,doSelect:n.doSelect,inverted:n.invertedRef,isHorizontal:n.isHorizontalRef,mergedClsPrefix:n.mergedClsPrefixRef,maxIconSize:r.maxIconSize,activeIconSize:r.activeIconSize,iconMarginRight:r.iconMarginRight,dropdownPlacement:r.dropdownPlacement,dropdownShow:m,paddingLeft:r.paddingLeft,mergedDisabled:v,mergedValue:n.mergedValueRef,childActive:be(()=>e.virtualChildActive??n.activePathRef.value.includes(e.internalKey)),collapsed:g(()=>i.mode==="horizontal"?!1:t.value?!0:!n.mergedExpandedKeysRef.value.includes(e.internalKey)),dropdownEnabled:g(()=>!v.value&&(i.mode==="horizontal"||t.value)),handlePopoverShowChange:S,handleClick:b}},render(){const{mergedClsPrefix:e,menuProps:{renderIcon:r,renderLabel:n}}=this,a=()=>{const{isHorizontal:t,paddingLeft:u,collapsed:v,mergedDisabled:m,maxIconSize:f,activeIconSize:b,title:S,childActive:C,icon:N,handleClick:M,menuProps:{nodeProps:_},dropdownShow:A,iconMarginRight:H,tmNode:ee,mergedClsPrefix:G,isEllipsisPlaceholder:oe,extra:P}=this,I=_?.(ee.rawNode);return d(),w("div",J(I,{class:[`${G}-menu-item`,I?.class],role:"menuitem"}),[(d(),T(je,{tmNode:ee,paddingLeft:u,collapsed:v,disabled:m,iconMarginRight:H,maxIconSize:f,activeIconSize:b,title:S,extra:P,showArrow:!t,childActive:C,clsPrefix:G,icon:N,hover:A,onClick:M,isEllipsisPlaceholder:oe},null,8,["tmNode","paddingLeft","collapsed","disabled","iconMarginRight","maxIconSize","activeIconSize","title","extra","showArrow","childActive","clsPrefix","icon","hover","onClick","isEllipsisPlaceholder"]))],16)},i=()=>(d(),T(so,null,{default:()=>{const{tmNodes:t,collapsed:u}=this;return u?null:(d(),w("div",{key:1,class:k(`${e}-submenu-children`),role:"menu"},[R(()=>t.map(v=>Pe(v,this.menuProps)))],2))}},1024));return this.root?(d(),T(Po,J({key:2,size:"large",trigger:"hover"},this.menuProps?.dropdownProps,{themeOverrides:this.mergedTheme.peerOverrides.Dropdown,theme:this.mergedTheme.peers.Dropdown,builtinThemeOverrides:{fontSizeLarge:"14px",optionIconSizeLarge:"18px"},value:this.mergedValue,disabled:!this.dropdownEnabled,placement:this.dropdownPlacement,keyField:this.menuProps.keyField,labelField:this.menuProps.labelField,childrenField:this.menuProps.childrenField,onUpdateShow:this.handlePopoverShowChange,options:this.rawNodes,onSelect:this.doSelect,inverted:this.inverted,renderIcon:r,renderLabel:n}),{default:()=>(d(),w("div",{class:k(`${e}-submenu`),role:"menu","aria-expanded":!this.collapsed,id:this.domId},[R(()=>a()),this.isHorizontal?R(()=>null):(d(),w(D,{key:1},[R(()=>i())],64))],10,ot))},1040,["themeOverrides","theme","value","disabled","placement","keyField","labelField","childrenField","onUpdateShow","options","onSelect","inverted","renderIcon","renderLabel"])):(d(),w("div",{key:3,class:k(`${e}-submenu`),role:"menu","aria-expanded":!this.collapsed,id:this.domId},[R(()=>a()),R(()=>i())],10,tt))}});function ye(e){return e.type==="divider"||e.type==="render"}function nt(e){return e.type==="divider"}function Pe(e,r){const{rawNode:n}=e,{show:a}=n;if(a===!1)return null;if(ye(n))return nt(n)?(d(),T(Wo,J({key:e.key},n.props),null,16)):null;const{labelField:i}=r,{key:t,level:u,isGroup:v}=e,m={...n,title:n.title||n[i],extra:n.titleExtra||n.extra,key:t,internalKey:t,level:u,root:u===0,isGroup:v};return e.children?e.isGroup?le(et,he(m,Qo,{tmNode:e,tmNodes:e.children,key:t})):le(Ce,he(m,rt,{key:t,rawNodes:n[r.childrenField],tmNodes:e.children,tmNode:e})):le(Jo,he(m,Zo,{key:t,tmNode:e}))}const lt={...Z.props,options:{type:Array,default:()=>[]},collapsed:{type:Boolean,default:void 0},collapsedWidth:{type:Number,default:48},iconSize:{type:Number,default:20},collapsedIconSize:{type:Number,default:24},rootIndent:Number,indent:{type:Number,default:32},labelField:{type:String,default:"label"},keyField:{type:String,default:"key"},childrenField:{type:String,default:"children"},disabledField:{type:String,default:"disabled"},defaultExpandAll:Boolean,defaultExpandedKeys:Array,expandedKeys:Array,value:[String,Number],defaultValue:{type:[String,Number],default:null},mode:{type:String,default:"vertical"},watchProps:{type:Array,default:void 0},disabled:Boolean,show:{type:Boolean,default:!0},inverted:Boolean,"onUpdate:expandedKeys":[Function,Array],onUpdateExpandedKeys:[Function,Array],onUpdateValue:[Function,Array],"onUpdate:value":[Function,Array],expandIcon:Function,renderIcon:Function,renderLabel:Function,renderExtra:Function,dropdownProps:Object,accordion:Boolean,nodeProps:Function,dropdownPlacement:{type:String,default:"bottom"},responsive:Boolean,items:Array,onOpenNamesChange:[Function,Array],onSelect:[Function,Array],onExpandedNamesChange:[Function,Array],expandedNames:Array,defaultExpandedNames:Array};var it=L({name:"Menu",inheritAttrs:!1,props:lt,setup(e){const{mergedClsPrefixRef:r,inlineThemeDisabled:n}=ue(e),a=Z("Menu","-menu",qo,mo,e,r),i=X(Ke,null),t=g(()=>{const{collapsed:h}=e;if(h!==void 0)return h;if(i){const{collapseModeRef:y,collapsedRef:o}=i;if(y.value==="width")return o.value??!1}return!1}),u=g(()=>{const{keyField:h,childrenField:y,disabledField:o}=e;return ge(e.items||e.options,{getIgnored(p){return ye(p)},getChildren(p){return p[y]},getDisabled(p){return p[o]},getKey(p){return p[h]??p.name}})}),v=g(()=>new Set(u.value.treeNodes.map(h=>h.key))),{watchProps:m}=e,f=F(null);m?.includes("defaultValue")?Ne(()=>{f.value=e.defaultValue}):f.value=e.defaultValue;const b=de(e,"value"),S=xe(b,f),C=F([]),N=()=>{C.value=e.defaultExpandAll?u.value.getNonLeafKeys():e.defaultExpandedNames||e.defaultExpandedKeys||u.value.getPath(S.value,{includeSelf:!1}).keyPath};m?.includes("defaultExpandedKeys")?Ne(N):N();const M=Io(e,["expandedNames","expandedKeys"]),_=xe(M,C),A=g(()=>u.value.treeNodes),H=g(()=>u.value.getPath(S.value).keyPath);re(ae,{props:e,mergedCollapsedRef:t,mergedThemeRef:a,mergedValueRef:S,mergedExpandedKeysRef:_,activePathRef:H,mergedClsPrefixRef:r,isHorizontalRef:g(()=>e.mode==="horizontal"),invertedRef:de(e,"inverted"),doSelect:ee,toggleExpand:oe});function ee(h,y){const{"onUpdate:value":o,onUpdateValue:p,onSelect:$}=e;p&&O(p,h,y),o&&O(o,h,y),$&&O($,h,y),f.value=h}function G(h){const{"onUpdate:expandedKeys":y,onUpdateExpandedKeys:o,onExpandedNamesChange:p,onOpenNamesChange:$}=e;y&&O(y,h),o&&O(o,h),p&&O(p,h),$&&O($,h),C.value=h}function oe(h){const y=Array.from(_.value),o=y.findIndex(p=>p===h);if(~o)y.splice(o,1);else{if(e.accordion&&v.value.has(h)){const p=y.findIndex($=>v.value.has($));p>-1&&y.splice(p,1)}y.push(h)}G(y)}const P=h=>{const y=u.value.getPath(h??S.value,{includeSelf:!1}).keyPath;if(!y.length)return;const o=Array.from(_.value),p=new Set([...o,...y]);e.accordion&&v.value.forEach($=>{p.has($)&&!y.includes($)&&p.delete($)}),G(Array.from(p))},I=g(()=>{const{inverted:h}=e,{common:{cubicBezierEaseInOut:y},self:o}=a.value,{borderRadius:p,borderColorHorizontal:$,fontSize:to,itemHeight:ro,dividerColor:no}=o,l={"--n-divider-color":no,"--n-bezier":y,"--n-font-size":to,"--n-border-color-horizontal":$,"--n-border-radius":p,"--n-item-height":ro};return h?(l["--n-group-text-color"]=o.groupTextColorInverted,l["--n-color"]=o.colorInverted,l["--n-item-text-color"]=o.itemTextColorInverted,l["--n-item-text-color-hover"]=o.itemTextColorHoverInverted,l["--n-item-text-color-active"]=o.itemTextColorActiveInverted,l["--n-item-text-color-child-active"]=o.itemTextColorChildActiveInverted,l["--n-item-text-color-child-active-hover"]=o.itemTextColorChildActiveInverted,l["--n-item-text-color-active-hover"]=o.itemTextColorActiveHoverInverted,l["--n-item-icon-color"]=o.itemIconColorInverted,l["--n-item-icon-color-hover"]=o.itemIconColorHoverInverted,l["--n-item-icon-color-active"]=o.itemIconColorActiveInverted,l["--n-item-icon-color-active-hover"]=o.itemIconColorActiveHoverInverted,l["--n-item-icon-color-child-active"]=o.itemIconColorChildActiveInverted,l["--n-item-icon-color-child-active-hover"]=o.itemIconColorChildActiveHoverInverted,l["--n-item-icon-color-collapsed"]=o.itemIconColorCollapsedInverted,l["--n-item-text-color-horizontal"]=o.itemTextColorHorizontalInverted,l["--n-item-text-color-hover-horizontal"]=o.itemTextColorHoverHorizontalInverted,l["--n-item-text-color-active-horizontal"]=o.itemTextColorActiveHorizontalInverted,l["--n-item-text-color-child-active-horizontal"]=o.itemTextColorChildActiveHorizontalInverted,l["--n-item-text-color-child-active-hover-horizontal"]=o.itemTextColorChildActiveHoverHorizontalInverted,l["--n-item-text-color-active-hover-horizontal"]=o.itemTextColorActiveHoverHorizontalInverted,l["--n-item-icon-color-horizontal"]=o.itemIconColorHorizontalInverted,l["--n-item-icon-color-hover-horizontal"]=o.itemIconColorHoverHorizontalInverted,l["--n-item-icon-color-active-horizontal"]=o.itemIconColorActiveHorizontalInverted,l["--n-item-icon-color-active-hover-horizontal"]=o.itemIconColorActiveHoverHorizontalInverted,l["--n-item-icon-color-child-active-horizontal"]=o.itemIconColorChildActiveHorizontalInverted,l["--n-item-icon-color-child-active-hover-horizontal"]=o.itemIconColorChildActiveHoverHorizontalInverted,l["--n-arrow-color"]=o.arrowColorInverted,l["--n-arrow-color-hover"]=o.arrowColorHoverInverted,l["--n-arrow-color-active"]=o.arrowColorActiveInverted,l["--n-arrow-color-active-hover"]=o.arrowColorActiveHoverInverted,l["--n-arrow-color-child-active"]=o.arrowColorChildActiveInverted,l["--n-arrow-color-child-active-hover"]=o.arrowColorChildActiveHoverInverted,l["--n-item-color-hover"]=o.itemColorHoverInverted,l["--n-item-color-active"]=o.itemColorActiveInverted,l["--n-item-color-active-hover"]=o.itemColorActiveHoverInverted,l["--n-item-color-active-collapsed"]=o.itemColorActiveCollapsedInverted):(l["--n-group-text-color"]=o.groupTextColor,l["--n-color"]=o.color,l["--n-item-text-color"]=o.itemTextColor,l["--n-item-text-color-hover"]=o.itemTextColorHover,l["--n-item-text-color-active"]=o.itemTextColorActive,l["--n-item-text-color-child-active"]=o.itemTextColorChildActive,l["--n-item-text-color-child-active-hover"]=o.itemTextColorChildActiveHover,l["--n-item-text-color-active-hover"]=o.itemTextColorActiveHover,l["--n-item-icon-color"]=o.itemIconColor,l["--n-item-icon-color-hover"]=o.itemIconColorHover,l["--n-item-icon-color-active"]=o.itemIconColorActive,l["--n-item-icon-color-active-hover"]=o.itemIconColorActiveHover,l["--n-item-icon-color-child-active"]=o.itemIconColorChildActive,l["--n-item-icon-color-child-active-hover"]=o.itemIconColorChildActiveHover,l["--n-item-icon-color-collapsed"]=o.itemIconColorCollapsed,l["--n-item-text-color-horizontal"]=o.itemTextColorHorizontal,l["--n-item-text-color-hover-horizontal"]=o.itemTextColorHoverHorizontal,l["--n-item-text-color-active-horizontal"]=o.itemTextColorActiveHorizontal,l["--n-item-text-color-child-active-horizontal"]=o.itemTextColorChildActiveHorizontal,l["--n-item-text-color-child-active-hover-horizontal"]=o.itemTextColorChildActiveHoverHorizontal,l["--n-item-text-color-active-hover-horizontal"]=o.itemTextColorActiveHoverHorizontal,l["--n-item-icon-color-horizontal"]=o.itemIconColorHorizontal,l["--n-item-icon-color-hover-horizontal"]=o.itemIconColorHoverHorizontal,l["--n-item-icon-color-active-horizontal"]=o.itemIconColorActiveHorizontal,l["--n-item-icon-color-active-hover-horizontal"]=o.itemIconColorActiveHoverHorizontal,l["--n-item-icon-color-child-active-horizontal"]=o.itemIconColorChildActiveHorizontal,l["--n-item-icon-color-child-active-hover-horizontal"]=o.itemIconColorChildActiveHoverHorizontal,l["--n-arrow-color"]=o.arrowColor,l["--n-arrow-color-hover"]=o.arrowColorHover,l["--n-arrow-color-active"]=o.arrowColorActive,l["--n-arrow-color-active-hover"]=o.arrowColorActiveHover,l["--n-arrow-color-child-active"]=o.arrowColorChildActive,l["--n-arrow-color-child-active-hover"]=o.arrowColorChildActiveHover,l["--n-item-color-hover"]=o.itemColorHover,l["--n-item-color-active"]=o.itemColorActive,l["--n-item-color-active-hover"]=o.itemColorActiveHover,l["--n-item-color-active-collapsed"]=o.itemColorActiveCollapsed),l}),B=n?ve("menu",g(()=>e.inverted?"a":"b"),I,e):void 0,q=vo(),V=F(null),me=F(null);let E=!0;const Te=()=>{E?E=!1:V.value?.sync({showAllItemsBeforeCalculate:!0})};function Ye(){return document.getElementById(q)}const ce=F(-1);function Xe(h){ce.value=e.options.length-h}function Ze(h){h||(ce.value=-1)}const Je=g(()=>{const h=ce.value;return{children:h===-1?[]:e.options.slice(h)}}),Qe=g(()=>{const{childrenField:h,disabledField:y,keyField:o}=e;return ge([Je.value],{getIgnored(p){return ye(p)},getChildren(p){return p[h]},getDisabled(p){return p[y]},getKey(p){return p[o]??p.name}})}),eo=g(()=>ge([{}]).treeNodes[0]);function oo(){if(ce.value===-1)return d(),T(Ce,{root:!0,level:0,key:"__ellpisisGroupPlaceholder__",internalKey:"__ellpisisGroupPlaceholder__",title:"···",tmNode:eo.value,domId:q,isEllipsisPlaceholder:!0},null,8,["tmNode","domId"]);const h=Qe.value.treeNodes[0],y=H.value,o=!!h.children?.some(p=>y.includes(p.key));return d(),T(Ce,{level:0,root:!0,key:"__ellpisisGroup__",internalKey:"__ellpisisGroup__",title:"···",virtualChildActive:o,tmNode:h,domId:q,rawNodes:h.rawNode.children||[],tmNodes:h.children||[],isEllipsisPlaceholder:!0},null,8,["virtualChildActive","tmNode","domId","rawNodes","tmNodes"])}return{mergedClsPrefix:r,controlledExpandedKeys:M,uncontrolledExpanededKeys:C,mergedExpandedKeys:_,uncontrolledValue:f,mergedValue:S,activePath:H,tmNodes:A,mergedTheme:a,mergedCollapsed:t,cssVars:n?void 0:I,themeClass:B?.themeClass,overflowRef:V,counterRef:me,updateCounter:()=>{},onResize:Te,onUpdateOverflow:Ze,onUpdateCount:Xe,renderCounter:oo,getCounter:Ye,onRender:B?.onRender,showOption:P,deriveResponsiveState:Te}},render(){const{mergedClsPrefix:e,mode:r,themeClass:n,onRender:a}=this;a?.();const i=()=>this.tmNodes.map(v=>Pe(v,this.$props)),t=r==="horizontal"&&this.responsive,u=()=>le("div",J(this.$attrs,{role:r==="horizontal"?"menubar":"menu",class:[`${e}-menu`,n,`${e}-menu--${r}`,t&&`${e}-menu--responsive`,this.mergedCollapsed&&`${e}-menu--collapsed`],style:this.cssVars}),t?(d(),T(To,{key:2,ref:"overflowRef",onUpdateOverflow:this.onUpdateOverflow,getCounter:this.getCounter,onUpdateCount:this.onUpdateCount,updateCounter:this.updateCounter,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:i,counter:this.renderCounter},1032,["onUpdateOverflow","getCounter","onUpdateCount","updateCounter"])):i());return t?(d(),T(uo,{key:3,onResize:this.onResize},{default:u},1032,["onResize"])):u()}});const at={class:"brand"},ct={class:"header-title"},st=L({__name:"AdminLayout",setup(e){const r=ho(),n=fo(),a=F(null),i=F(!1);function t(f,b){return{key:b,label:()=>le(zo,{to:{path:b}},{default:()=>f})}}const u=[t("总览","/"),{key:"settings",label:"系统设置",children:[t("全局开关","/settings/global"),t("模型选择","/settings/models")]},t("服务商","/providers"),t("模型配置","/models"),t("AI 工具","/tools"),t("向量模型","/embedding"),{key:"channels",label:"频道",children:[t("聊天冷却","/cooldown"),t("预热频道","/warmup")]},t("词过滤","/filter"),t("A/B 实验","/ab"),{key:"data",label:"数据管理",children:[t("成员档案","/data/member_profiles"),t("记忆笔记","/data/memory_notes"),t("通用知识","/data/knowledge_documents"),t("对话块","/data/conversation_blocks"),t("帖子索引","/data/forum_threads"),t("用户金币","/data/user_coins"),t("金币流水（只读）","/data/coin_transactions"),t("贷款","/data/coin_loans"),t("好感度","/data/user_affection"),t("警告记录（只读）","/data/user_warnings"),t("商店商品","/data/shop_items"),t("工作事件","/data/work_events"),t("人设偏好","/data/user_persona_preference")]},t("经济工具","/economy"),t("封禁与频道","/moderation"),t("活动管理","/events"),t("人设与文案","/persona"),t("数值调参","/tuning"),t("操作日志","/audit")],v=g(()=>n.path.startsWith("/ab")?"/ab":n.path);async function m(){try{await yo.post("auth/logout")}catch{}wo(),r.push({name:"login"})}return po(async()=>{a.value=await go()}),(f,b)=>{const S=bo("router-view");return d(),T(K(Be),{style:{height:"100vh"},"has-sider":""},{default:W(()=>[Y(K(Go),{bordered:"","collapse-mode":"width","collapsed-width":64,width:220,collapsed:i.value,"show-trigger":"",onCollapse:b[0]||(b[0]=C=>i.value=!0),onExpand:b[1]||(b[1]=C=>i.value=!1)},{default:W(()=>[j("div",at,fe(i.value?"类":"类脑娘"),1),Y(K(it),{collapsed:i.value,"collapsed-width":64,"collapsed-icon-size":20,options:u,value:v.value},null,8,["collapsed","value"])]),_:1},8,["collapsed"]),Y(K(Be),null,{default:W(()=>[Y(K(Lo),{bordered:"",class:"header"},{default:W(()=>[j("span",ct,fe(String(K(n).meta.title??"")),1),Y(K(Ro),{align:"center",size:12},{default:W(()=>[a.value?(d(),T(K(So),{key:0,type:"info",size:"small",bordered:!1},{default:W(()=>[He(fe(a.value.user_id),1)]),_:1})):xo("",!0),Y(K(Co),{quaternary:"",size:"small",onClick:m},{default:W(()=>[...b[2]||(b[2]=[He("退出登录",-1)])]),_:1})]),_:1})]),_:1}),Y(K(Eo),{class:"content"},{default:W(()=>[Y(S)]),_:1})]),_:1})]),_:1})}}}),wt=Ao(st,[["__scopeId","data-v-d6f61d76"]]);export{wt as default};
