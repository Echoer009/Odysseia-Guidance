import{T as Xt}from"./Tag-BOw3g_sQ.js";import{I as ne}from"./Input-5F652rO1.js";import{ac as Gt,ad as Se,ae as Kt,d as fe,X as re,af as Yt,F as W,k as Jt,a as p,c as _,r as C,p as oe,q as P,M as ot,ag as Zt,x as Re,J as ue,L as X,t as M,K as it,T as Qt,ah as ea,E as ie,ai as ta,l as o,I as T,m as b,H as F,P as aa,B as ce,n as lt,aj as We,Z as Ee,y as na,ak as ra,al as pe,am as be,o as st,_ as oa,D as ia,an as Xe,ao as la,ap as Z,aq as ke,ar as sa,as as da,at as ca,v as Ge,G as ua,au as fa,N as Q,O as we,w as x,b as u,e as d,ab as pa,g as Ae,C as ba,a9 as va,a5 as ve,aa as Ke}from"./index-Cn3eNn6t.js";import{S as ma}from"./Select-GIjsnw-h.js";import{D as ga}from"./DataTable-MtccZ3Wa.js";import{u as Ye,S as Ce}from"./Space-DeFGV75_.js";import{F as ha}from"./Form-lpQlMEiW.js";import{F as L}from"./FormItem-BDO9dwOa.js";import{I as ae}from"./InputNumber-stp9cNdu.js";import{P as xa}from"./Popconfirm-CUIJqFHO.js";import{S as me}from"./Switch-COXDSuI7.js";import{A as ya}from"./Add-B4NYyzfY.js";import{C as _a}from"./ChevronLeft-Bh3JO0rl.js";import{C as ka}from"./ChevronRight-Dm-MUzlC.js";import{u as wa}from"./use-merged-state-D95XVr8c.js";import{c as Ca,a as Je,o as Sa}from"./Popover-CZiQPGnn.js";import{_ as Ra}from"./CapabilityTags.vue_vue_type_script_setup_true_lang-Cd5UXfns.js";import"./Suffix-Bt_xhlWZ.js";import"./create-B264eiVS.js";import"./happens-in-CM8LO42l.js";import"./next-frame-once-C5Ksf8W7.js";import"./prop-CUltvu8b.js";import"./Dropdown-D4GXwCF-.js";import"./format-length-GpG_jwN9.js";import"./CheckboxGroup-DT6aynZM.js";import"./Ellipsis-BqzK8xkV.js";import"./Tooltip-BaaPmlE3.js";var Ta=/\s/;function za(e){for(var l=e.length;l--&&Ta.test(e.charAt(l)););return l}var $a=/^\s+/;function Pa(e){return e&&e.slice(0,za(e)+1).replace($a,"")}var Ze=NaN,Ba=/^[-+]0x[0-9a-f]+$/i,Wa=/^0b[01]+$/i,Ea=/^0o[0-7]+$/i,Aa=parseInt;function Qe(e){if(typeof e=="number")return e;if(Gt(e))return Ze;if(Se(e)){var l=typeof e.valueOf=="function"?e.valueOf():e;e=Se(l)?l+"":l}if(typeof e!="string")return e===0?e:+e;e=Pa(e);var f=Wa.test(e);return f||Ea.test(e)?Aa(e.slice(2),f?2:8):Ba.test(e)?Ze:+e}var Le=function(){return Kt.Date.now()},La="Expected a function",ja=Math.max,Ia=Math.min;function Oa(e,l,f){var h,v,S,k,g,y,w=0,a=!1,j=!1,O=!0;if(typeof e!="function")throw new TypeError(La);l=Qe(l)||0,Se(f)&&(a=!!f.leading,j="maxWait"in f,S=j?ja(Qe(f.maxWait)||0,l):S,O="trailing"in f?!!f.trailing:O);function D(r){var H=h,K=v;return h=v=void 0,w=r,k=e.apply(K,H),k}function E(r){return w=r,g=setTimeout(I,l),a?D(r):k}function B(r){var H=r-y,K=r-w,q=l-H;return j?Ia(q,S-K):q}function V(r){var H=r-y,K=r-w;return y===void 0||H>=l||H<0||j&&K>=S}function I(){var r=Le();if(V(r))return G(r);g=setTimeout(I,B(r))}function G(r){return g=void 0,O&&h?D(r):(h=v=void 0,k)}function ee(){g!==void 0&&clearTimeout(g),w=0,h=y=v=g=void 0}function c(){return g===void 0?k:G(Le())}function i(){var r=Le(),H=V(r);if(h=arguments,v=this,y=r,H){if(g===void 0)return E(y);if(j)return clearTimeout(g),g=setTimeout(I,l),D(y)}return g===void 0&&(g=setTimeout(I,l)),k}return i.cancel=ee,i.flush=c,i}var Ha="Expected a function";function Ua(e,l,f){var h=!0,v=!0;if(typeof e!="function")throw new TypeError(Ha);return Se(f)&&(h="leading"in f?!!f.leading:h,v="trailing"in f?!!f.trailing:v),Oa(e,l,{leading:h,maxWait:l,trailing:v})}const Fa=Je(".v-x-scroll",{overflow:"auto",scrollbarWidth:"none"},[Je("&::-webkit-scrollbar",{width:0,height:0})]),Ma=fe({name:"XScroll",props:{disabled:Boolean,onScroll:Function},setup(){const e=W(null);function l(v){!(v.currentTarget.offsetWidth<v.currentTarget.scrollWidth)||v.deltaY===0||(v.currentTarget.scrollLeft+=v.deltaY+v.deltaX,v.preventDefault())}const f=Yt();return Fa.mount({id:"vueuc/x-scroll",head:!0,anchorMetaName:Ca,ssr:f}),Object.assign({selfRef:e,handleWheel:l},{scrollTo(...v){var S;(S=e.value)===null||S===void 0||S.scrollTo(...v)}})},render(){return re("div",{ref:"selfRef",onScroll:this.onScroll,onWheel:this.disabled?void 0:this.handleWheel,class:"v-x-scroll"},this.$slots)}}),He=Jt("n-tabs"),dt={tab:[String,Number,Object,Function],name:{type:[String,Number],required:!0},disabled:Boolean,displayDirective:{type:String,default:"if"},closable:{type:Boolean,default:void 0},tabProps:Object,label:[String,Number,Object,Function]};var et=fe({__TAB_PANE__:!0,name:"TabPane",alias:["TabPanel"],props:dt,slots:Object,setup(e){const l=ot(He,null);return l||Zt("tab-pane","`n-tab-pane` must be placed inside `n-tabs`."),{style:l.paneStyleRef,class:l.paneClassRef,mergedClsPrefix:l.mergedClsPrefixRef}},render(){return p(),_("div",{class:P([`${this.mergedClsPrefix}-tab-pane`,this.class]),style:oe(this.style)},[C(()=>this.$slots.default?.())],6)}});const Da=["data-name","data-disabled"],Na={internalLeftPadded:Boolean,internalAddable:Boolean,internalCreatedByPane:Boolean,...ta(dt,["displayDirective"])};var Oe=fe({__TAB__:!0,inheritAttrs:!1,name:"Tab",props:Na,setup(e){const{mergedClsPrefixRef:l,valueRef:f,typeRef:h,closableRef:v,tabStyleRef:S,addTabStyleRef:k,tabClassRef:g,addTabClassRef:y,tabChangeIdRef:w,onBeforeLeaveRef:a,triggerRef:j,handleAdd:O,activateTab:D,handleClose:E}=ot(He);return{trigger:j,mergedClosable:ie(()=>{if(e.internalAddable)return!1;const{closable:B}=e;return B===void 0?v.value:B}),style:S,addStyle:k,tabClass:g,addTabClass:y,clsPrefix:l,value:f,type:h,handleClose(B){B.stopPropagation(),!e.disabled&&E(e.name)},activateTab(){if(e.disabled)return;if(e.internalAddable){O();return}const{name:B}=e,V=++w.id;if(B!==f.value){const{value:I}=a;I?Promise.resolve(I(e.name,f.value)).then(G=>{G&&w.id===V&&D(B)}):D(B)}}}},render(){const{internalAddable:e,clsPrefix:l,name:f,disabled:h,label:v,tab:S,value:k,mergedClosable:g,trigger:y,$slots:{default:w}}=this,a=v??S;return p(),_("div",{class:P(`${l}-tabs-tab-wrapper`)},[this.internalLeftPadded?(p(),_("div",{key:0,class:P(`${l}-tabs-tab-pad`)},null,2)):C(()=>null),(p(),_("div",Re({key:f,"data-name":f,"data-disabled":h?!0:void 0},Re({class:[`${l}-tabs-tab`,k===f&&`${l}-tabs-tab--active`,h&&`${l}-tabs-tab--disabled`,g&&`${l}-tabs-tab--closable`,e&&`${l}-tabs-tab--addable`,e?this.addTabClass:this.tabClass],onClick:y==="click"?this.activateTab:void 0,onMouseenter:y==="hover"?this.activateTab:void 0,style:e?this.addStyle:this.style},this.internalCreatedByPane?this.tabProps||{}:this.$attrs)),[ue("span",{class:P(`${l}-tabs-tab__label`)},[e?(p(),_(X,{key:0},[ue("div",{class:P(`${l}-tabs-tab__height-placeholder`)}," ",2),(p(),M(it,{clsPrefix:l},{default:()=>(p(),M(ya))},1032,["clsPrefix"]))],64)):(p(),_(X,{key:1},[w?(p(),_(X,{key:0},[C(()=>w())],64)):(p(),_(X,{key:1},[typeof a=="object"?(p(),_(X,{key:0},[C(()=>a)],64)):(p(),_(X,{key:1},[C(()=>Qt(a??f))],64))],64))],64))],2),g&&this.type==="card"?(p(),M(ea,{key:0,clsPrefix:l,class:P(`${l}-tabs-tab__close`),onClick:this.handleClose,disabled:h},null,8,["clsPrefix","class","onClick","disabled"])):C(()=>null)],16,Da))],2)}}),Va=o("tabs",`
 box-sizing: border-box;
 width: 100%;
 display: flex;
 flex-direction: column;
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
`,[T("&.transition-disabled",[o("tabs-tab",`
 transition: none !important;
 `),o("tabs-nav-scroll-content",`
 transition: none !important;
 `),o("tabs-tab-pad",`
 transition: none !important;
 `)]),b("segment-type",[o("tabs-rail",[T("&.transition-disabled",[o("tabs-capsule",`
 transition: none;
 `)])])]),b("top",[o("tab-pane",`
 padding: var(--n-pane-padding-top) var(--n-pane-padding-right) var(--n-pane-padding-bottom) var(--n-pane-padding-left);
 `)]),b("left",[o("tab-pane",`
 padding: var(--n-pane-padding-right) var(--n-pane-padding-bottom) var(--n-pane-padding-left) var(--n-pane-padding-top);
 `)]),b("left, right",`
 flex-direction: row;
 `,[o("tabs-bar",`
 width: 2px;
 right: 0;
 transition:
 top .2s var(--n-bezier),
 max-height .2s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),o("tabs-tab",`
 padding: var(--n-tab-padding-vertical); 
 `)]),b("right",`
 flex-direction: row-reverse;
 `,[o("tab-pane",`
 padding: var(--n-pane-padding-left) var(--n-pane-padding-top) var(--n-pane-padding-right) var(--n-pane-padding-bottom);
 `),o("tabs-bar",`
 left: 0;
 `)]),b("bottom",`
 flex-direction: column-reverse;
 justify-content: flex-end;
 `,[o("tab-pane",`
 padding: var(--n-pane-padding-bottom) var(--n-pane-padding-right) var(--n-pane-padding-top) var(--n-pane-padding-left);
 `),o("tabs-bar",`
 top: 0;
 `)]),o("tabs-rail",`
 position: relative;
 padding: 3px;
 border-radius: var(--n-tab-border-radius);
 width: 100%;
 background-color: var(--n-color-segment);
 transition: background-color .3s var(--n-bezier);
 display: flex;
 align-items: center;
 `,[o("tabs-capsule",`
 border-radius: var(--n-tab-border-radius);
 position: absolute;
 left: 0;
 top: 0;
 pointer-events: none;
 background-color: var(--n-tab-color-segment);
 box-shadow: 0 1px 3px 0 rgba(0, 0, 0, .08);
 transition: transform 0.3s var(--n-bezier);
 `),o("tabs-tab-wrapper",`
 flex-basis: 0;
 flex-grow: 1;
 display: flex;
 align-items: center;
 justify-content: center;
 `,[o("tabs-tab",`
 overflow: hidden;
 border-radius: var(--n-tab-border-radius);
 width: 100%;
 display: flex;
 align-items: center;
 justify-content: center;
 `,[b("active",`
 font-weight: var(--n-font-weight-strong);
 color: var(--n-tab-text-color-active);
 `),T("&:hover",`
 color: var(--n-tab-text-color-hover);
 `)])])]),b("flex",[o("tabs-nav",`
 width: 100%;
 position: relative;
 `,[o("tabs-wrapper",`
 width: 100%;
 `,[o("tabs-tab",`
 margin-right: 0;
 `)])])]),o("tabs-nav",`
 box-sizing: border-box;
 line-height: 1.5;
 display: flex;
 transition: border-color .3s var(--n-bezier);
 `,[F("prefix, suffix",`
 display: flex;
 align-items: center;
 `),F("prefix","padding-right: 16px;"),F("suffix","padding-left: 16px;")]),b("top, bottom",[T(">",[o("tabs-nav",[o("tabs-nav-scroll-wrapper",[T("&::before",`
 top: 0;
 bottom: 0;
 left: 0;
 width: 20px;
 `),T("&::after",`
 top: 0;
 bottom: 0;
 right: 0;
 width: 20px;
 `),b("shadow-start",[T("&::before",`
 box-shadow: inset 10px 0 8px -8px rgba(0, 0, 0, .12);
 `)]),b("shadow-end",[T("&::after",`
 box-shadow: inset -10px 0 8px -8px rgba(0, 0, 0, .12);
 `)])])])])]),b("left, right",[o("tabs-nav-scroll-content",`
 flex-direction: column;
 `),T(">",[o("tabs-nav",[o("tabs-nav-scroll-wrapper",[T("&::before",`
 top: 0;
 left: 0;
 right: 0;
 height: 20px;
 `),T("&::after",`
 bottom: 0;
 left: 0;
 right: 0;
 height: 20px;
 `),b("shadow-start",[T("&::before",`
 box-shadow: inset 0 10px 8px -8px rgba(0, 0, 0, .12);
 `)]),b("shadow-end",[T("&::after",`
 box-shadow: inset 0 -10px 8px -8px rgba(0, 0, 0, .12);
 `)])])])])]),o("tabs-nav-scroll-wrapper",`
 flex: 1;
 position: relative;
 overflow: hidden;
 `,[o("tabs-nav-y-scroll",`
 height: 100%;
 width: 100%;
 overflow-y: auto; 
 scrollbar-width: none;
 `,[T("&::-webkit-scrollbar, &::-webkit-scrollbar-track-piece, &::-webkit-scrollbar-thumb",`
 width: 0;
 height: 0;
 display: none;
 `)]),T("&::before, &::after",`
 transition: box-shadow .3s var(--n-bezier);
 pointer-events: none;
 content: "";
 position: absolute;
 z-index: 1;
 `),T("&.transition-disabled",[T("&::before, &::after",`
 transition: none;
 `)])]),o("tabs-nav-scroll-content",`
 display: flex;
 position: relative;
 min-width: 100%;
 min-height: 100%;
 width: fit-content;
 box-sizing: border-box;
 `),o("tabs-wrapper",`
 display: inline-flex;
 flex-wrap: nowrap;
 position: relative;
 `),o("tabs-tab-wrapper",`
 display: flex;
 flex-wrap: nowrap;
 flex-shrink: 0;
 flex-grow: 0;
 `),o("tabs-tab",`
 cursor: pointer;
 white-space: nowrap;
 flex-wrap: nowrap;
 display: inline-flex;
 align-items: center;
 color: var(--n-tab-text-color);
 font-size: var(--n-tab-font-size);
 background-clip: padding-box;
 padding: var(--n-tab-padding);
 transition:
 box-shadow .3s var(--n-bezier),
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[b("disabled",{cursor:"not-allowed"}),F("close",`
 margin-inline-start: 6px;
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),F("label",`
 display: flex;
 align-items: center;
 z-index: 1;
 `)]),o("tabs-bar",`
 position: absolute;
 bottom: 0;
 height: 2px;
 border-radius: 1px;
 background-color: var(--n-bar-color);
 transition:
 left .2s var(--n-bezier),
 max-width .2s var(--n-bezier),
 opacity .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `,[T("&.transition-disabled",`
 transition: none;
 `),b("disabled",`
 background-color: var(--n-tab-text-color-disabled)
 `)]),o("tabs-pane-wrapper",`
 position: relative;
 overflow: hidden;
 transition: max-height .2s var(--n-bezier);
 `),o("tab-pane",`
 color: var(--n-pane-text-color);
 width: 100%;
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 opacity .2s var(--n-bezier);
 left: 0;
 right: 0;
 top: 0;
 `,[T("&.next-transition-leave-active, &.prev-transition-leave-active, &.next-transition-enter-active, &.prev-transition-enter-active",`
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 transform .2s var(--n-bezier),
 opacity .2s var(--n-bezier);
 `),T("&.next-transition-leave-active, &.prev-transition-leave-active",`
 position: absolute;
 `),T("&.next-transition-enter-from, &.prev-transition-leave-to",`
 transform: translateX(32px);
 opacity: 0;
 `),T("&.next-transition-leave-to, &.prev-transition-enter-from",`
 transform: translateX(-32px);
 opacity: 0;
 `),T("&.next-transition-leave-from, &.next-transition-enter-to, &.prev-transition-leave-from, &.prev-transition-enter-to",`
 transform: translateX(0);
 opacity: 1;
 `)]),o("tabs-tab-pad",`
 box-sizing: border-box;
 width: var(--n-tab-gap);
 flex-grow: 0;
 flex-shrink: 0;
 `),b("line-type, bar-type",[o("tabs-tab",`
 font-weight: var(--n-tab-font-weight);
 box-sizing: border-box;
 vertical-align: bottom;
 `,[T("&:hover",{color:"var(--n-tab-text-color-hover)"}),b("active",`
 color: var(--n-tab-text-color-active);
 font-weight: var(--n-tab-font-weight-active);
 `),b("disabled",{color:"var(--n-tab-text-color-disabled)"})])]),o("tabs-nav",[F("prefix, suffix",`
 border-color: var(--n-tab-border-color);
 `),o("tabs-nav-scroll-content",`
 border-color: var(--n-tab-border-color);
 `),b("line-type",[b("top",[F("prefix, suffix",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),o("tabs-nav-scroll-content",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),o("tabs-bar",`
 bottom: -1px;
 `)]),b("left",[F("prefix, suffix",`
 border-right: 1px solid var(--n-tab-border-color);
 `),o("tabs-nav-scroll-content",`
 border-right: 1px solid var(--n-tab-border-color);
 `),o("tabs-bar",`
 right: -1px;
 `)]),b("right",[F("prefix, suffix",`
 border-left: 1px solid var(--n-tab-border-color);
 `),o("tabs-nav-scroll-content",`
 border-left: 1px solid var(--n-tab-border-color);
 `),o("tabs-bar",`
 left: -1px;
 `)]),b("bottom",[F("prefix, suffix",`
 border-top: 1px solid var(--n-tab-border-color);
 `),o("tabs-nav-scroll-content",`
 border-top: 1px solid var(--n-tab-border-color);
 `),o("tabs-bar",`
 top: -1px;
 `)]),F("prefix, suffix",`
 transition: border-color .3s var(--n-bezier);
 `),o("tabs-nav-scroll-content",`
 transition: border-color .3s var(--n-bezier);
 `),o("tabs-bar",`
 border-radius: 0;
 `)]),b("card-type",[F("prefix, suffix",`
 transition: border-color .3s var(--n-bezier);
 `),o("tabs-pad",`
 flex-grow: 1;
 transition: border-color .3s var(--n-bezier);
 `),o("tabs-tab-pad",`
 transition: border-color .3s var(--n-bezier);
 `),o("tabs-tab",`
 font-weight: var(--n-tab-font-weight);
 border: 1px solid var(--n-tab-border-color);
 background-color: var(--n-tab-color);
 box-sizing: border-box;
 position: relative;
 vertical-align: bottom;
 display: flex;
 justify-content: space-between;
 font-size: var(--n-tab-font-size);
 color: var(--n-tab-text-color);
 `,[b("addable",`
 padding-left: 8px;
 padding-right: 8px;
 font-size: 16px;
 justify-content: center;
 `,[F("height-placeholder",`
 width: 0;
 font-size: var(--n-tab-font-size);
 `),aa("disabled",[T("&:hover",`
 color: var(--n-tab-text-color-hover);
 `)])]),b("closable","padding-inline-end: 8px;"),b("active",`
 background-color: #0000;
 font-weight: var(--n-tab-font-weight-active);
 color: var(--n-tab-text-color-active);
 `),b("disabled","color: var(--n-tab-text-color-disabled);")])]),b("left, right",`
 flex-direction: column; 
 `,[F("prefix, suffix",`
 padding: var(--n-tab-padding-vertical);
 `),o("tabs-wrapper",`
 flex-direction: column;
 `),o("tabs-tab-wrapper",`
 flex-direction: column;
 `,[o("tabs-tab-pad",`
 height: var(--n-tab-gap-vertical);
 width: 100%;
 `)])]),b("top",[b("card-type",[o("tabs-scroll-padding","border-bottom: 1px solid var(--n-tab-border-color);"),F("prefix, suffix",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),o("tabs-tab",`
 border-top-left-radius: var(--n-tab-border-radius);
 border-top-right-radius: var(--n-tab-border-radius);
 `,[b("active",`
 border-bottom: 1px solid #0000;
 `)]),o("tabs-tab-pad",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),o("tabs-pad",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `)])]),b("left",[b("card-type",[o("tabs-scroll-padding","border-right: 1px solid var(--n-tab-border-color);"),F("prefix, suffix",`
 border-right: 1px solid var(--n-tab-border-color);
 `),o("tabs-tab",`
 border-top-left-radius: var(--n-tab-border-radius);
 border-bottom-left-radius: var(--n-tab-border-radius);
 `,[b("active",`
 border-right: 1px solid #0000;
 `)]),o("tabs-tab-pad",`
 border-right: 1px solid var(--n-tab-border-color);
 `),o("tabs-pad",`
 border-right: 1px solid var(--n-tab-border-color);
 `)])]),b("right",[b("card-type",[o("tabs-scroll-padding","border-left: 1px solid var(--n-tab-border-color);"),F("prefix, suffix",`
 border-left: 1px solid var(--n-tab-border-color);
 `),o("tabs-tab",`
 border-top-right-radius: var(--n-tab-border-radius);
 border-bottom-right-radius: var(--n-tab-border-radius);
 `,[b("active",`
 border-left: 1px solid #0000;
 `)]),o("tabs-tab-pad",`
 border-left: 1px solid var(--n-tab-border-color);
 `),o("tabs-pad",`
 border-left: 1px solid var(--n-tab-border-color);
 `)])]),b("bottom",[b("card-type",[o("tabs-scroll-padding","border-top: 1px solid var(--n-tab-border-color);"),F("prefix, suffix",`
 border-top: 1px solid var(--n-tab-border-color);
 `),o("tabs-tab",`
 border-bottom-left-radius: var(--n-tab-border-radius);
 border-bottom-right-radius: var(--n-tab-border-radius);
 `,[b("active",`
 border-top: 1px solid #0000;
 `)]),o("tabs-tab-pad",`
 border-top: 1px solid var(--n-tab-border-color);
 `),o("tabs-pad",`
 border-top: 1px solid var(--n-tab-border-color);
 `)])])]),o("tabs-scroll-button",[b("start",`
 padding-left: 10px;
 padding-right: 6px;
 `),b("end",`
 padding-right: 10px;
 padding-left: 6px;
 `),b("up",`
 padding-bottom: 10px;
 `),b("down",`
 padding-top: 10px;
 `)])]),tt=fe({name:"TabsButton",props:{type:{type:String,default:"next"},mergedClsPrefix:{type:String,required:!0},vertical:Boolean,disabled:Boolean,rtl:Boolean,theme:Object,themeOverrides:Object,onClick:Function},setup(e){return{handleClick:()=>{e.disabled||e.onClick?.(e.type)}}},render(){const{mergedClsPrefix:e,disabled:l,type:f,vertical:h,rtl:v,theme:S,themeOverrides:k,handleClick:g}=this,y=f==="next",w=h?y:v?!y:y;return p(),M(ce,{text:!0,disabled:l,size:"small",theme:S,themeOverrides:k,onClick:g,class:P([`${e}-tabs-scroll-button`,!h&&f==="prev"&&`${e}-tabs-scroll-button--start`,!h&&f==="next"&&`${e}-tabs-scroll-button--end`,h&&f==="prev"&&`${e}-tabs-scroll-button--up`,h&&f==="next"&&`${e}-tabs-scroll-button--down`])},{icon:()=>(p(),M(it,{clsPrefix:e,style:oe(h?{transform:"rotate(90deg)"}:void 0)},{default:()=>w?(p(),M(ka,{key:1})):(p(),M(_a,{key:2}))},1032,["clsPrefix","style"]))},1032,["disabled","theme","themeOverrides","onClick","class"])}});const je=Ua,qa={...lt.props,value:[String,Number],defaultValue:[String,Number],trigger:{type:String,default:"click"},type:{type:String,default:"bar"},closable:Boolean,justifyContent:String,size:String,placement:{type:String,default:"top"},tabStyle:[String,Object],tabClass:String,addTabStyle:[String,Object],addTabClass:String,barWidth:Number,paneClass:String,paneStyle:[String,Object],paneWrapperClass:String,paneWrapperStyle:[String,Object],addable:[Boolean,Object],tabsPadding:{type:Number,default:0},animated:Boolean,onBeforeLeave:Function,onAdd:Function,"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array],onClose:[Function,Array],labelSize:String,activeName:[String,Number],onActiveNameChange:[Function,Array],showScrollButton:Boolean,centerActiveTab:Boolean};var Xa=fe({name:"Tabs",props:qa,slots:Object,setup(e,{slots:l}){const{mergedClsPrefixRef:f,inlineThemeDisabled:h,mergedComponentPropsRef:v,mergedRtlRef:S}=na(e),k=ra("Tabs",S,f),g=ie(()=>{const{placement:t}=e;return t==="start"?k?.value?"right":"left":t==="end"?k?.value?"left":"right":t}),y=lt("Tabs","-tabs",Va,la,e,f),w=W(null),a=W(null),j=W(null),O=W(null),D=W(null),E=W(null),B=W(null),V=W(!0),I=W(!0),G=Ye(e,["labelSize","size"]),ee=ie(()=>{if(G.value)return G.value;const t=v?.value?.Tabs?.size;return t||"medium"}),c=Ye(e,["activeName","value"]),i=W(c.value??e.defaultValue??(l.default?We(l.default())[0]?.props?.name:null)),r=wa(c,i),H={id:0},K=ie(()=>{if(!(!e.justifyContent||e.type==="card"))return{display:"flex",justifyContent:e.justifyContent}});pe(r,()=>{H.id=0,N(),be(()=>{Te()})});function q(){const{value:t}=r;return t===null?null:w.value?.querySelector(`[data-name="${t}"]`)}function ge(t){if(e.type==="card")return;const{value:n}=j;if(!n)return;const s=n.style.opacity==="0";if(t){const m=`${f.value}-tabs-bar--disabled`,{barWidth:R}=e,A=g.value;if(t.dataset.disabled==="true"?n.classList.add(m):n.classList.remove(m),["top","bottom"].includes(A)){if(z(["top","maxHeight","height"]),typeof R=="number"&&t.offsetWidth>=R){const $=Math.floor((t.offsetWidth-R)/2)+t.offsetLeft;n.style.left=`${$}px`,n.style.maxWidth=`${R}px`}else n.style.left=`${t.offsetLeft}px`,n.style.maxWidth=`${t.offsetWidth}px`;n.style.width="8192px",s&&(n.style.transition="none"),n.offsetWidth,s&&(n.style.transition="",n.style.opacity="1")}else{if(z(["left","maxWidth","width"]),typeof R=="number"&&t.offsetHeight>=R){const $=Math.floor((t.offsetHeight-R)/2)+t.offsetTop;n.style.top=`${$}px`,n.style.maxHeight=`${R}px`}else n.style.top=`${t.offsetTop}px`,n.style.maxHeight=`${t.offsetHeight}px`;n.style.height="8192px",s&&(n.style.transition="none"),n.offsetHeight,s&&(n.style.transition="",n.style.opacity="1")}}}function Y(){if(e.type==="card")return;const{value:t}=j;t&&(t.style.opacity="0")}function z(t){const{value:n}=j;if(n)for(const s of t)n.style[s]=""}function N(){if(e.type==="card")return;const t=q();t?ge(t):Y()}function le(t,n,s,m){const R=t.getBoundingClientRect(),A=n.getBoundingClientRect(),$=s?"left":"top",U=s?"right":"bottom";let J=0;m?J=(A[$]+A[U])/2-(R[$]+R[U])/2:A[$]<R[$]?J=A[$]-R[$]:A[U]>R[U]&&(J=A[U]-R[U]),J!==0&&t.scrollBy({[$]:J,behavior:"smooth"})}function Te(){const t=["top","bottom"].includes(g.value),n=q();if(n)if(t){const s=E.value?.$el;if(!s)return;le(s,n,t,e.centerActiveTab)}else{const{value:s}=B;if(!s)return;le(s,n,t,e.centerActiveTab)}}const he=W(null);let ze=0,te=null;function ct(t){const n=he.value;if(n){ze=t.getBoundingClientRect().height;const s=`${ze}px`,m=()=>{n.style.height=s,n.style.maxHeight=s};te?(m(),te(),te=null):te=m}}function ut(t){const n=he.value;if(n){const s=t.getBoundingClientRect().height,m=()=>{document.body.offsetHeight,n.style.maxHeight=`${s}px`,n.style.height=`${Math.max(ze,s)}px`};te?(te(),te=null,m()):te=m}}function ft(){const t=he.value;if(t){t.style.maxHeight="",t.style.height="";const{paneWrapperStyle:n}=e;if(typeof n=="string")t.style.cssText=n;else if(n){const{maxHeight:s,height:m}=n;s!==void 0&&(t.style.maxHeight=s),m!==void 0&&(t.style.height=m)}}}const Ue={value:[]},Fe=W("next");function pt(t){const n=r.value;let s="next";for(const m of Ue.value){if(m===n)break;if(m===t){s="prev";break}}Fe.value=s,bt(t)}function bt(t){const{onActiveNameChange:n,onUpdateValue:s,"onUpdate:value":m}=e;n&&we(n,t),s&&we(s,t),m&&we(m,t),i.value=t}function vt(t){const{onClose:n}=e;n&&we(n,t)}function mt(t){if(["top","bottom"].includes(g.value)){const{value:n}=E;if(!n)return;const s=n.$el;if(!s)return;const m=s.offsetWidth,R=!!k?.value,A=t==="next"?m:-m;s.scrollBy({left:R?-A:A,behavior:"smooth"})}else{const{value:n}=B;if(!n)return;const s=n.offsetHeight,m=t==="next"?n.scrollTop+s:n.scrollTop-s;n.scrollTo({top:m,left:0,behavior:"smooth"})}}let $e=!0;function Pe(){const{value:t}=j;if(!t)return;$e&&($e=!1);const n="transition-disabled";t.classList.add(n),N(),t.classList.remove(n)}const se=W(null);function xe({transitionDisabled:t}){const n=w.value;if(!n)return;t&&n.classList.add("transition-disabled");const s=q();s&&se.value&&(se.value.style.width=`${s.offsetWidth}px`,se.value.style.height=`${s.offsetHeight}px`,se.value.style.transform=`translate(${s.offsetLeft}px, ${s.offsetTop}px)`,t&&se.value.offsetWidth),t&&n.classList.remove("transition-disabled")}pe([r],()=>{e.type==="segment"&&be(()=>{xe({transitionDisabled:!1})})}),st(()=>{e.type==="segment"&&xe({transitionDisabled:!0})});let Me=0;function gt(t){if(t.contentRect.width===0&&t.contentRect.height===0||Me===t.contentRect.width)return;Me=t.contentRect.width;const{type:n}=e;(n==="line"||n==="bar")&&($e||e.justifyContent?.startsWith("space"))&&Pe(),n!=="segment"&&ye(Ne())}const ht=je(gt,64);function De(){const{type:t}=e;t==="line"||t==="bar"?Pe():t==="segment"&&xe({transitionDisabled:!0})}pe([()=>e.justifyContent,()=>e.size],()=>{be(()=>{(e.type==="line"||e.type==="bar")&&Pe()})}),pe([g,()=>k?.value],()=>{be(()=>{De(),ye(Ne(),{instantly:!0})})}),pe(()=>e.type,()=>{be(()=>{const t=a.value;t&&(t.classList.add("transition-disabled"),De(),t.offsetWidth,t.classList.remove("transition-disabled"))})});const de=W(!1);function xt(t){const{target:n,contentRect:{width:s,height:m}}=t,R=n.parentElement.parentElement.offsetWidth,A=n.parentElement.parentElement.offsetHeight,$=g.value;if(!de.value)$==="top"||$==="bottom"?R<s&&(de.value=!0):A<m&&(de.value=!0);else{const{value:U}=D;if(!U)return;$==="top"||$==="bottom"?R-s>U.$el.offsetWidth&&(de.value=!1):A-m>U.$el.offsetHeight&&(de.value=!1)}ye(E.value?.$el||null)}const yt=je(xt,64);function _t(){const{onAdd:t}=e;t&&t()}const Be=W(!1);function Ne(){const t=g.value;return(t==="top"||t==="bottom"?E.value?.$el:B.value)||null}function ye(t,n={instantly:!1}){if(!t)return;const s=n.instantly?O.value:null;s&&s.classList.add("transition-disabled");const m=1,R=g.value;if(R==="top"||R==="bottom"){const{scrollLeft:A,scrollWidth:$,offsetWidth:U}=t,J=Math.abs(A);V.value=J<=m,I.value=J+U>=$-m,Be.value=U<$-m}else{const{scrollTop:A,scrollHeight:$,offsetHeight:U}=t;V.value=A<=m,I.value=A+U>=$-m,Be.value=U<$-m}s&&(s.offsetWidth,s.classList.remove("transition-disabled"))}const kt=je(t=>{ye(t.target)},64);ua(He,{triggerRef:Q(e,"trigger"),tabStyleRef:Q(e,"tabStyle"),tabClassRef:Q(e,"tabClass"),addTabStyleRef:Q(e,"addTabStyle"),addTabClassRef:Q(e,"addTabClass"),paneClassRef:Q(e,"paneClass"),paneStyleRef:Q(e,"paneStyle"),mergedClsPrefixRef:f,typeRef:Q(e,"type"),closableRef:Q(e,"closable"),valueRef:r,tabChangeIdRef:H,onBeforeLeaveRef:Q(e,"onBeforeLeave"),activateTab:pt,handleClose:vt,handleAdd:_t}),Sa(()=>{N(),Te()}),oa(()=>{const{value:t}=O;if(!t)return;const{value:n}=f,s=`${n}-tabs-nav-scroll-wrapper--shadow-start`,m=`${n}-tabs-nav-scroll-wrapper--shadow-end`;V.value?t.classList.remove(s):t.classList.add(s),I.value?t.classList.remove(m):t.classList.add(m)});const wt={syncBarPosition:()=>{N()},scrollToCurrentTab:()=>{Te()}},Ct=()=>{xe({transitionDisabled:!0})},Ve=ie(()=>{const{value:t}=ee,{type:n}=e,s=`${t}${{card:"Card",bar:"Bar",line:"Line",segment:"Segment"}[n]}`,{self:{barColor:m,closeIconColor:R,closeIconColorHover:A,closeIconColorPressed:$,tabColor:U,tabBorderColor:J,paneTextColor:St,tabFontWeight:Rt,tabBorderRadius:Tt,tabFontWeightActive:zt,colorSegment:$t,fontWeightStrong:Pt,tabColorSegment:Bt,closeSize:Wt,closeIconSize:Et,closeColorHover:At,closeColorPressed:Lt,closeBorderRadius:jt,[Z("panePadding",t)]:_e,[Z("tabPadding",s)]:It,[Z("tabPaddingVertical",s)]:Ot,[Z("tabGap",s)]:Ht,[Z("tabGap",`${s}Vertical`)]:Ut,[Z("tabTextColor",n)]:Ft,[Z("tabTextColorActive",n)]:Mt,[Z("tabTextColorHover",n)]:Dt,[Z("tabTextColorDisabled",n)]:Nt,[Z("tabFontSize",t)]:Vt},common:{cubicBezierEaseInOut:qt}}=y.value;return{"--n-bezier":qt,"--n-color-segment":$t,"--n-bar-color":m,"--n-tab-font-size":Vt,"--n-tab-text-color":Ft,"--n-tab-text-color-active":Mt,"--n-tab-text-color-disabled":Nt,"--n-tab-text-color-hover":Dt,"--n-pane-text-color":St,"--n-tab-border-color":J,"--n-tab-border-radius":Tt,"--n-close-size":Wt,"--n-close-icon-size":Et,"--n-close-color-hover":At,"--n-close-color-pressed":Lt,"--n-close-border-radius":jt,"--n-close-icon-color":R,"--n-close-icon-color-hover":A,"--n-close-icon-color-pressed":$,"--n-tab-color":U,"--n-tab-font-weight":Rt,"--n-tab-font-weight-active":zt,"--n-tab-padding":It,"--n-tab-padding-vertical":Ot,"--n-tab-gap":Ht,"--n-tab-gap-vertical":Ut,"--n-pane-padding-left":ke(_e,"left"),"--n-pane-padding-right":ke(_e,"right"),"--n-pane-padding-top":ke(_e,"top"),"--n-pane-padding-bottom":ke(_e,"bottom"),"--n-font-weight-strong":Pt,"--n-tab-color-segment":Bt}}),qe=h?ia("tabs",ie(()=>`${ee.value[0]}${e.type[0]}`),Ve,e):void 0;return{mergedClsPrefix:f,mergedValue:r,renderedNames:new Set,segmentCapsuleElRef:se,tabsPaneWrapperRef:he,tabsElRef:w,selfElRef:a,barElRef:j,addTabInstRef:D,xScrollInstRef:E,scrollWrapperElRef:O,addTabFixed:de,tabWrapperStyle:K,handleNavResize:ht,mergedSize:ee,handleScroll:kt,handleTabsResize:yt,cssVars:h?void 0:Ve,themeClass:qe?.themeClass,animationDirection:Fe,renderNameListRef:Ue,yScrollElRef:B,handleSegmentResize:Ct,onAnimationBeforeLeave:ct,onAnimationEnter:ut,onAnimationAfterEnter:ft,onRender:qe?.onRender,startReachedRef:V,endReachedRef:I,isOverflow:Be,handleButtonClick:mt,mergedTheme:y,rtlEnabled:k,mergedPlacement:g,...wt}},render(){const{mergedClsPrefix:e,type:l,mergedPlacement:f,addTabFixed:h,addable:v,mergedSize:S,renderNameListRef:k,onRender:g,paneWrapperClass:y,paneWrapperStyle:w,startReachedRef:a,endReachedRef:j,isOverflow:O,showScrollButton:D,handleButtonClick:E,mergedTheme:B,rtlEnabled:V,$slots:{default:I,prefix:G,suffix:ee}}=this;g?.();const c=I?We(I()).filter(z=>z.type.__TAB_PANE__===!0):[],i=I?We(I()).filter(z=>z.type.__TAB__===!0):[],r=!i.length,H=l==="card",K=l==="segment",q=!H&&!K&&this.justifyContent;k.value=[];const ge=()=>{const z=(p(),_("div",{style:oe(this.tabWrapperStyle),class:P(`${e}-tabs-wrapper`)},[q?C(()=>null):(p(),_("div",{key:1,class:P(`${e}-tabs-scroll-padding`),style:oe(f==="top"||f==="bottom"?{width:`${this.tabsPadding}px`}:{height:`${this.tabsPadding}px`})},null,6)),r?(p(),_(X,{key:2},[C(()=>c.map((N,le)=>(k.value.push(N.props.name),Ie((p(),M(Oe,Re(N.props,{internalCreatedByPane:!0,internalLeftPadded:le!==0&&(!q||q==="center"||q==="start"||q==="end")}),Ge(N.children?{default:N.children.tab}:void 0),1040,["internalLeftPadded"]))))))],64)):(p(),_(X,{key:3},[C(()=>i.map((N,le)=>(k.value.push(N.props.name),Ie(le!==0&&!q?rt(N):N))))],64)),!h&&v&&H?(p(),_(X,{key:4},[C(()=>nt(v,(r?c.length:i.length)!==0))],64)):C(()=>null),q?C(()=>null):(p(),_("div",{key:7,class:P(`${e}-tabs-scroll-padding`),style:oe({width:`${this.tabsPadding}px`})},null,6)),H?C(()=>null):(p(),_("div",{key:9,ref:"barElRef",class:P(`${e}-tabs-bar`)},null,2))],6));return p(),_("div",{ref:"tabsElRef",class:P(`${e}-tabs-nav-scroll-content`)},[H&&v?(p(),M(Ee,{key:0,onResize:this.handleTabsResize},{default:()=>z},1032,["onResize"])):(p(),_(X,{key:1},[C(()=>z)],64)),H?(p(),_("div",{key:2,class:P(`${e}-tabs-pad`)},null,2)):C(()=>null)],2)},Y=K?"top":f;return p(),_("div",{ref:"selfElRef",class:P([`${e}-tabs`,this.themeClass,`${e}-tabs--${l}-type`,`${e}-tabs--${S}-size`,q&&`${e}-tabs--flex`,`${e}-tabs--${Y}`,V&&`${e}-tabs--rtl`]),style:oe(this.cssVars)},[ue("div",{class:P([`${e}-tabs-nav--${l}-type`,`${e}-tabs-nav--${Y}`,`${e}-tabs-nav`])},[C(()=>Xe(G,z=>z&&(p(),_("div",{class:P(`${e}-tabs-nav__prefix`)},[C(()=>z)],2)))),K?(p(),M(Ee,{key:0,onResize:this.handleSegmentResize},{default:()=>(p(),_("div",{class:P(`${e}-tabs-rail`),ref:"tabsElRef"},[ue("div",{class:P(`${e}-tabs-capsule`),ref:"segmentCapsuleElRef"},[ue("div",{class:P(`${e}-tabs-wrapper`)},[ue("div",{class:P(`${e}-tabs-tab`)},null,2)],2)],2),r?(p(),_(X,{key:0},[C(()=>c.map((z,N)=>(k.value.push(z.props.name),p(),M(Oe,Re(z.props,{internalCreatedByPane:!0,internalLeftPadded:N!==0}),Ge(z.children?{default:z.children.tab}:void 0),1040,["internalLeftPadded"]))))],64)):(p(),_(X,{key:1},[C(()=>i.map((z,N)=>(k.value.push(z.props.name),N===0?z:rt(z))))],64))],2))},1032,["onResize"])):(p(),_(X,{key:1},[C(()=>D&&O&&(p(),M(tt,{mergedClsPrefix:e,type:"prev",vertical:Y==="left"||Y==="right",disabled:a,rtl:!!V,theme:B.peers.Button,themeOverrides:B.peerOverrides.Button,onClick:E},null,8,["mergedClsPrefix","vertical","disabled","rtl","theme","themeOverrides","onClick"]))),(p(),M(Ee,{onResize:this.handleNavResize},{default:()=>(p(),_("div",{class:P(`${e}-tabs-nav-scroll-wrapper`),ref:"scrollWrapperElRef"},[["top","bottom"].includes(Y)?(p(),M(Ma,{key:0,ref:"xScrollInstRef",onScroll:this.handleScroll},{default:ge},1032,["onScroll"])):(p(),_("div",{key:1,class:P(`${e}-tabs-nav-y-scroll`),onScroll:this.handleScroll,ref:"yScrollElRef"},[C(()=>ge())],42,["onScroll"]))],2))},1032,["onResize"])),C(()=>D&&O&&(p(),M(tt,{mergedClsPrefix:e,type:"next",vertical:Y==="left"||Y==="right",disabled:j,rtl:!!V,theme:B.peers.Button,themeOverrides:B.peerOverrides.Button,onClick:E},null,8,["mergedClsPrefix","vertical","disabled","rtl","theme","themeOverrides","onClick"])))],64)),h&&v&&H?(p(),_(X,{key:2},[C(()=>nt(v,!0))],64)):C(()=>null),C(()=>Xe(ee,z=>z&&(p(),_("div",{class:P(`${e}-tabs-nav__suffix`)},[C(()=>z)],2))))],2),C(()=>r&&(this.animated&&(Y==="top"||Y==="bottom")?(p(),_("div",{key:1,ref:"tabsPaneWrapperRef",style:oe(w),class:P([`${e}-tabs-pane-wrapper`,y])},[C(()=>at(c,this.mergedValue,this.renderedNames,this.onAnimationBeforeLeave,this.onAnimationEnter,this.onAnimationAfterEnter,this.animationDirection))],6)):at(c,this.mergedValue,this.renderedNames)))],6)}});function at(e,l,f,h,v,S,k){const g=[];return e.forEach(y=>{const{name:w,displayDirective:a,"display-directive":j}=y.props,O=E=>a===E||j===E,D=l===w;if(y.key!==void 0&&(y.key=w),D||O("show")||O("show:lazy")&&f.has(w)){f.has(w)||f.add(w);const E=!O("if");g.push(E?sa(y,[[da,D]]):y)}}),k?(p(),M(ca,{name:`${k}-transition`,onBeforeLeave:h,onEnter:v,onAfterEnter:S},{default:()=>g},1032,["name","onBeforeLeave","onEnter","onAfterEnter"])):g}function nt(e,l){return p(),M(Oe,{ref:"addTabInstRef",key:"__addable",name:"__addable",internalCreatedByPane:!0,internalAddable:!0,internalLeftPadded:l,disabled:typeof e=="object"&&e.disabled},null,8,["internalLeftPadded","disabled"])}function rt(e){const l=fa(e);return l.props?l.props.internalLeftPadded=!0:l.props={internalLeftPadded:!0},l}function Ie(e){return Array.isArray(e.dynamicProps)?e.dynamicProps.includes("internalLeftPadded")||e.dynamicProps.push("internalLeftPadded"):e.dynamicProps=["internalLeftPadded"],e}const kn=fe({__name:"ModelsPage",setup(e){function l(){return{temperature:1,top_p:.95,top_k:0,max_output_tokens:8192,presence_penalty:0,frequency_penalty:0,thinking_budget_tokens:0}}function f(){return{system_prompt:"",jailbreak_user_prompt:"",jailbreak_model_response:"",jailbreak_final_instruction:"",use_cache_optimized_build:!1}}function h(){return{id:null,model_name:"",display_name:"",provider_id:null,actual_model:"",supports_vision:!1,supports_tools:!1,supports_thinking:!1,max_output_tokens:8192,enabled:!0,generation_config:l(),prompt_config:f()}}const v=W(!0),S=W(!1),k=W([]),g=W([]),y=W(!1),w=W(null),a=va(h()),j={model_name:{required:!0,message:"请输入模型标识",trigger:["blur","input"]},provider_id:{required:!0,type:"number",message:"请选择服务商",trigger:["blur","change"]}},O=ie(()=>g.value.map(c=>({label:`${c.display_name||c.name}（${c.name}）`,value:c.id})));function D(c){const i=g.value.find(r=>r.id===c);return i?i.display_name||i.name:String(c)}async function E(){v.value=!0;try{const c=await Promise.all([ve.get("models"),ve.get("providers")]);k.value=Array.isArray(c[0])?c[0]:[],g.value=Array.isArray(c[1])?c[1]:[]}catch{}finally{v.value=!1}}function B(){Object.assign(a,h()),a.generation_config=l(),a.prompt_config=f(),y.value=!0}function V(c){a.id=c.id,a.model_name=c.model_name??"",a.display_name=c.display_name??"",a.provider_id=c.provider_id??null,a.actual_model=c.actual_model??"",a.supports_vision=!!c.supports_vision,a.supports_tools=!!c.supports_tools,a.supports_thinking=!!c.supports_thinking,a.max_output_tokens=c.max_output_tokens??null,a.enabled=!!c.enabled,Object.assign(a.generation_config,l(),c.generation_config??{}),Object.assign(a.prompt_config,f(),c.prompt_config??{}),y.value=!0}async function I(){try{await w.value?.validate()}catch{return}const c={model_name:a.model_name.trim(),display_name:a.display_name.trim(),provider_id:a.provider_id,actual_model:a.actual_model.trim(),supports_vision:a.supports_vision,supports_tools:a.supports_tools,supports_thinking:a.supports_thinking,max_output_tokens:a.max_output_tokens??0,enabled:a.enabled,generation_config:{temperature:a.generation_config.temperature??0,top_p:a.generation_config.top_p??0,top_k:a.generation_config.top_k??0,max_output_tokens:a.generation_config.max_output_tokens??0,presence_penalty:a.generation_config.presence_penalty??0,frequency_penalty:a.generation_config.frequency_penalty??0,thinking_budget_tokens:a.generation_config.thinking_budget_tokens??0},prompt_config:{...a.prompt_config}};S.value=!0;try{a.id==null?await ve.post("models",c):await ve.put(`models/${a.id}`,c),y.value=!1,Ke("已保存"),await E()}catch{}finally{S.value=!1}}async function G(c){try{await ve.delete(`models/${c.id}`),Ke("已删除"),await E()}catch{}}const ee=[{title:"模型标识",key:"model_name",width:180},{title:"显示名",key:"display_name",width:160},{title:"服务商",key:"provider_id",width:130,render:c=>D(c.provider_id)},{title:"实际模型",key:"actual_model",ellipsis:{tooltip:!0}},{title:"能力",key:"capabilities",width:200,render:c=>re(Ra,{vision:c.supports_vision,tools:c.supports_tools,thinking:c.supports_thinking})},{title:"状态",key:"enabled",width:90,render:c=>re(Xt,{type:c.enabled?"success":"default",size:"small",bordered:!1},{default:()=>c.enabled?"启用":"停用"})},{title:"操作",key:"actions",width:150,render:c=>re(Ce,{size:8},{default:()=>[re(ce,{size:"small",onClick:()=>V(c)},{default:()=>"编辑"}),re(xa,{onPositiveClick:()=>{G(c)}},{default:()=>"确认删除该模型？",trigger:()=>re(ce,{size:"small",type:"error",secondary:!0},{default:()=>"删除"})})]})}];return st(()=>{E()}),(c,i)=>(p(),M(d(ba),{title:"模型配置",class:"page-card"},{"header-extra":x(()=>[u(d(ce),{type:"primary",size:"small",onClick:B},{default:x(()=>[...i[23]||(i[23]=[Ae("新增模型",-1)])]),_:1})]),default:x(()=>[u(d(ga),{columns:ee,data:k.value,loading:v.value,"row-key":r=>r.id,size:"small"},null,8,["data","loading","row-key"]),u(d(pa),{show:y.value,"onUpdate:show":i[22]||(i[22]=r=>y.value=r),preset:"card",title:a.id==null?"新增模型":"编辑模型",style:{width:"760px"}},{footer:x(()=>[u(d(Ce),{justify:"end"},{default:x(()=>[u(d(ce),{onClick:i[21]||(i[21]=r=>y.value=!1)},{default:x(()=>[...i[24]||(i[24]=[Ae("取消",-1)])]),_:1}),u(d(ce),{type:"primary",loading:S.value,onClick:I},{default:x(()=>[...i[25]||(i[25]=[Ae("保存",-1)])]),_:1},8,["loading"])]),_:1})]),default:x(()=>[u(d(ha),{ref_key:"formRef",ref:w,model:a,rules:j,"label-placement":"left","label-width":"140"},{default:x(()=>[u(d(Xa),{type:"line",animated:""},{default:x(()=>[u(d(et),{name:"basic",tab:"基本信息"},{default:x(()=>[u(d(Ce),{vertical:"",size:"small"},{default:x(()=>[u(d(L),{label:"模型标识",path:"model_name"},{default:x(()=>[u(d(ne),{value:a.model_name,"onUpdate:value":i[0]||(i[0]=r=>a.model_name=r),placeholder:"唯一标识，如 gemini-2.5-pro"},null,8,["value"])]),_:1}),u(d(L),{label:"显示名"},{default:x(()=>[u(d(ne),{value:a.display_name,"onUpdate:value":i[1]||(i[1]=r=>a.display_name=r),placeholder:"显示名称"},null,8,["value"])]),_:1}),u(d(L),{label:"服务商",path:"provider_id"},{default:x(()=>[u(d(ma),{value:a.provider_id,"onUpdate:value":i[2]||(i[2]=r=>a.provider_id=r),options:O.value,filterable:"",placeholder:"选择服务商"},null,8,["value","options"])]),_:1}),u(d(L),{label:"实际模型"},{default:x(()=>[u(d(ne),{value:a.actual_model,"onUpdate:value":i[3]||(i[3]=r=>a.actual_model=r),placeholder:"实际调用的模型 ID"},null,8,["value"])]),_:1}),u(d(L),{label:"最大输出 Token"},{default:x(()=>[u(d(ae),{value:a.max_output_tokens,"onUpdate:value":i[4]||(i[4]=r=>a.max_output_tokens=r),min:1,max:2e6,step:256,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"支持视觉"},{default:x(()=>[u(d(me),{value:a.supports_vision,"onUpdate:value":i[5]||(i[5]=r=>a.supports_vision=r)},null,8,["value"])]),_:1}),u(d(L),{label:"支持工具"},{default:x(()=>[u(d(me),{value:a.supports_tools,"onUpdate:value":i[6]||(i[6]=r=>a.supports_tools=r)},null,8,["value"])]),_:1}),u(d(L),{label:"支持思考"},{default:x(()=>[u(d(me),{value:a.supports_thinking,"onUpdate:value":i[7]||(i[7]=r=>a.supports_thinking=r)},null,8,["value"])]),_:1}),u(d(L),{label:"启用"},{default:x(()=>[u(d(me),{value:a.enabled,"onUpdate:value":i[8]||(i[8]=r=>a.enabled=r)},null,8,["value"])]),_:1})]),_:1})]),_:1}),u(d(et),{name:"params",tab:"参数与提示词"},{default:x(()=>[u(d(Ce),{vertical:"",size:"small"},{default:x(()=>[u(d(L),{label:"temperature"},{default:x(()=>[u(d(ae),{value:a.generation_config.temperature,"onUpdate:value":i[9]||(i[9]=r=>a.generation_config.temperature=r),min:0,max:2,step:.05,precision:2,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"top_p"},{default:x(()=>[u(d(ae),{value:a.generation_config.top_p,"onUpdate:value":i[10]||(i[10]=r=>a.generation_config.top_p=r),min:0,max:1,step:.01,precision:2,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"top_k"},{default:x(()=>[u(d(ae),{value:a.generation_config.top_k,"onUpdate:value":i[11]||(i[11]=r=>a.generation_config.top_k=r),min:0,max:4096,step:1,precision:0,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"生成最大 Token"},{default:x(()=>[u(d(ae),{value:a.generation_config.max_output_tokens,"onUpdate:value":i[12]||(i[12]=r=>a.generation_config.max_output_tokens=r),min:0,max:2e6,step:256,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"presence_penalty"},{default:x(()=>[u(d(ae),{value:a.generation_config.presence_penalty,"onUpdate:value":i[13]||(i[13]=r=>a.generation_config.presence_penalty=r),min:-2,max:2,step:.1,precision:2,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"frequency_penalty"},{default:x(()=>[u(d(ae),{value:a.generation_config.frequency_penalty,"onUpdate:value":i[14]||(i[14]=r=>a.generation_config.frequency_penalty=r),min:-2,max:2,step:.1,precision:2,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"思考预算 Token"},{default:x(()=>[u(d(ae),{value:a.generation_config.thinking_budget_tokens,"onUpdate:value":i[15]||(i[15]=r=>a.generation_config.thinking_budget_tokens=r),min:-1,max:2e6,step:128,precision:0,style:{width:"200px"}},null,8,["value"])]),_:1}),u(d(L),{label:"System Prompt"},{default:x(()=>[u(d(ne),{value:a.prompt_config.system_prompt,"onUpdate:value":i[16]||(i[16]=r=>a.prompt_config.system_prompt=r),type:"textarea",rows:6,placeholder:"系统提示词"},null,8,["value"])]),_:1}),u(d(L),{label:"越狱用户提示"},{default:x(()=>[u(d(ne),{value:a.prompt_config.jailbreak_user_prompt,"onUpdate:value":i[17]||(i[17]=r=>a.prompt_config.jailbreak_user_prompt=r),type:"textarea",rows:4,placeholder:"jailbreak_user_prompt"},null,8,["value"])]),_:1}),u(d(L),{label:"越狱模型回复"},{default:x(()=>[u(d(ne),{value:a.prompt_config.jailbreak_model_response,"onUpdate:value":i[18]||(i[18]=r=>a.prompt_config.jailbreak_model_response=r),type:"textarea",rows:4,placeholder:"jailbreak_model_response"},null,8,["value"])]),_:1}),u(d(L),{label:"越狱最终指令"},{default:x(()=>[u(d(ne),{value:a.prompt_config.jailbreak_final_instruction,"onUpdate:value":i[19]||(i[19]=r=>a.prompt_config.jailbreak_final_instruction=r),type:"textarea",rows:4,placeholder:"jailbreak_final_instruction"},null,8,["value"])]),_:1}),u(d(L),{label:"缓存优化构建"},{default:x(()=>[u(d(me),{value:a.prompt_config.use_cache_optimized_build,"onUpdate:value":i[20]||(i[20]=r=>a.prompt_config.use_cache_optimized_build=r)},null,8,["value"])]),_:1})]),_:1})]),_:1})]),_:1})]),_:1},8,["model"])]),_:1},8,["show","title"])]),_:1}))}});export{kn as default};
