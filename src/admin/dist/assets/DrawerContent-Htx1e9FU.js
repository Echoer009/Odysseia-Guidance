import{d as X,ar as j,as as q,a,c as g,t as $,aW as ee,X as $e,q as m,p as R,r as S,S as te,x as _,v as Y,aZ as ke,F,M as re,a_ as V,y as oe,ak as xe,_ as Be,al as Ee,aD as Re,a$ as Fe,E as z,G as W,b0 as Me,b1 as Te,b2 as He,b3 as Oe,I as n,aV as A,l as h,m as w,H as B,b4 as De,n as ne,b5 as Pe,b6 as Ie,N as K,b7 as We,D as _e,b8 as Ae,O as E,b9 as Le,ba as Ne,J as G,L as J,ag as Ue,ah as je}from"./index-BRnOnDbo.js";import{f as Z}from"./format-length-DQpcrA0j.js";import{u as Q}from"./use-merged-state-auJtTBTB.js";const Xe=["onMouseenter","onMouseleave","onMousedown"],Ye={key:1,role:"none"};var Ve=X({name:"NDrawerContent",inheritAttrs:!1,props:{blockScroll:Boolean,show:{type:Boolean,default:void 0},displayDirective:{type:String,required:!0},placement:{type:String,required:!0},contentClass:String,contentStyle:[Object,String],nativeScrollbar:{type:Boolean,required:!0},scrollbarProps:Object,trapFocus:{type:Boolean,default:!0},autoFocus:{type:Boolean,default:!0},showMask:{type:[Boolean,String],required:!0},maxWidth:Number,maxHeight:Number,minWidth:Number,minHeight:Number,resizable:Boolean,onClickoutside:Function,onAfterLeave:Function,onAfterEnter:Function,onEsc:Function},setup(e){const t=F(!!e.show),r=F(null),v=re(V);let f=0,C="",u=null;const p=F(!1),y=F(!1),k=z(()=>e.placement==="top"||e.placement==="bottom"),{mergedClsPrefixRef:M,mergedRtlRef:T}=oe(e),H=xe("Drawer",T,M),x=o,b=i=>{y.value=!0,f=k.value?i.clientY:i.clientX,C=document.body.style.cursor,document.body.style.cursor=k.value?"ns-resize":"ew-resize",document.body.addEventListener("mousemove",D),document.body.addEventListener("mouseleave",x),document.body.addEventListener("mouseup",o)},P=()=>{u!==null&&(window.clearTimeout(u),u=null),y.value?p.value=!0:u=window.setTimeout(()=>{p.value=!0},300)},L=()=>{u!==null&&(window.clearTimeout(u),u=null),p.value=!1},{doUpdateHeight:N,doUpdateWidth:U}=v,O=i=>{const{maxWidth:s}=e;if(s&&i>s)return s;const{minWidth:d}=e;return d&&i<d?d:i},I=i=>{const{maxHeight:s}=e;if(s&&i>s)return s;const{minHeight:d}=e;return d&&i<d?d:i};function D(i){if(y.value)if(k.value){let s=r.value?.offsetHeight||0;const d=f-i.clientY;s+=e.placement==="bottom"?d:-d,s=I(s),N(s),f=i.clientY}else{let s=r.value?.offsetWidth||0;const d=f-i.clientX;s+=e.placement==="right"?d:-d,s=O(s),U(s),f=i.clientX}}function o(){y.value&&(f=0,y.value=!1,document.body.style.cursor=C,document.body.removeEventListener("mousemove",D),document.body.removeEventListener("mouseup",o),document.body.removeEventListener("mouseleave",x))}Be(()=>{e.show&&(t.value=!0)}),Ee(()=>e.show,i=>{i||o()}),Re(()=>{o()});const l=z(()=>{const{show:i}=e,s=[[q,i]];return e.showMask||s.push([Me,e.onClickoutside,void 0,{capture:!0}]),s});function c(){t.value=!1,e.onAfterLeave?.()}return Fe(z(()=>e.blockScroll&&t.value)),W(Te,r),W(He,null),W(Oe,null),{bodyRef:r,rtlEnabled:H,mergedClsPrefix:v.mergedClsPrefixRef,isMounted:v.isMountedRef,mergedTheme:v.mergedThemeRef,displayed:t,transitionName:z(()=>({right:"slide-in-from-right-transition",left:"slide-in-from-left-transition",top:"slide-in-from-top-transition",bottom:"slide-in-from-bottom-transition"})[e.placement]),handleAfterLeave:c,bodyDirectives:l,handleMousedownResizeTrigger:b,handleMouseenterResizeTrigger:P,handleMouseleaveResizeTrigger:L,isDragging:y,isHoverOnResizeTrigger:p}},render(){const{$slots:e,mergedClsPrefix:t}=this;return this.displayDirective==="show"||this.displayed||this.show?j((a(),g("div",Ye,[(a(),$(ke,{disabled:!this.showMask||!this.trapFocus,active:this.show,autoFocus:this.autoFocus,onEsc:this.onEsc},{default:()=>(a(),$(ee,{name:this.transitionName,appear:this.isMounted,onAfterEnter:this.onAfterEnter,onAfterLeave:this.handleAfterLeave},{default:()=>j($e("div",_(this.$attrs,{role:"dialog",ref:"bodyRef","aria-modal":"true",class:[`${t}-drawer`,this.rtlEnabled&&`${t}-drawer--rtl`,`${t}-drawer--${this.placement}-placement`,this.isDragging&&`${t}-drawer--unselectable`,this.nativeScrollbar&&`${t}-drawer--native-scrollbar`]}),[this.resizable?(a(),g("div",{key:2,class:m([`${t}-drawer__resize-trigger`,(this.isDragging||this.isHoverOnResizeTrigger)&&`${t}-drawer__resize-trigger--hover`]),onMouseenter:this.handleMouseenterResizeTrigger,onMouseleave:this.handleMouseleaveResizeTrigger,onMousedown:this.handleMousedownResizeTrigger},null,42,Xe)):null,this.nativeScrollbar?(a(),g("div",{key:3,class:m([`${t}-drawer-content-wrapper`,this.contentClass]),style:R(this.contentStyle),role:"none"},[S(()=>e.default?.())],6)):(a(),$(te,_({key:4},this.scrollbarProps,{contentStyle:this.contentStyle,contentClass:[`${t}-drawer-content-wrapper`,this.contentClass],theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar}),Y(e),1040,["contentStyle","contentClass","theme","themeOverrides"]))]),this.bodyDirectives)},1032,["name","appear","onAfterEnter","onAfterLeave"]))},1032,["disabled","active","autoFocus","onEsc"]))])),[[q,this.displayDirective==="if"||this.displayed||this.show]]):null}});const{cubicBezierEaseIn:qe,cubicBezierEaseOut:Ke}=A;function Ge({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-bottom"}={}){return[n(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${qe}`}),n(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${Ke}`}),n(`&.${r}-transition-enter-to`,{transform:"translateY(0)"}),n(`&.${r}-transition-enter-from`,{transform:"translateY(100%)"}),n(`&.${r}-transition-leave-from`,{transform:"translateY(0)"}),n(`&.${r}-transition-leave-to`,{transform:"translateY(100%)"})]}const{cubicBezierEaseIn:Je,cubicBezierEaseOut:Ze}=A;function Qe({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-left"}={}){return[n(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${Je}`}),n(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${Ze}`}),n(`&.${r}-transition-enter-to`,{transform:"translateX(0)"}),n(`&.${r}-transition-enter-from`,{transform:"translateX(-100%)"}),n(`&.${r}-transition-leave-from`,{transform:"translateX(0)"}),n(`&.${r}-transition-leave-to`,{transform:"translateX(-100%)"})]}const{cubicBezierEaseIn:et,cubicBezierEaseOut:tt}=A;function rt({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-right"}={}){return[n(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${et}`}),n(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${tt}`}),n(`&.${r}-transition-enter-to`,{transform:"translateX(0)"}),n(`&.${r}-transition-enter-from`,{transform:"translateX(100%)"}),n(`&.${r}-transition-leave-from`,{transform:"translateX(0)"}),n(`&.${r}-transition-leave-to`,{transform:"translateX(100%)"})]}const{cubicBezierEaseIn:ot,cubicBezierEaseOut:nt}=A;function it({duration:e="0.3s",leaveDuration:t="0.2s",name:r="slide-in-from-top"}={}){return[n(`&.${r}-transition-leave-active`,{transition:`transform ${t} ${ot}`}),n(`&.${r}-transition-enter-active`,{transition:`transform ${e} ${nt}`}),n(`&.${r}-transition-enter-to`,{transform:"translateY(0)"}),n(`&.${r}-transition-enter-from`,{transform:"translateY(-100%)"}),n(`&.${r}-transition-leave-from`,{transform:"translateY(0)"}),n(`&.${r}-transition-leave-to`,{transform:"translateY(-100%)"})]}var st=n([h("drawer",`
 word-break: break-word;
 line-height: var(--n-line-height);
 position: absolute;
 pointer-events: all;
 box-shadow: var(--n-box-shadow);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 background-color: var(--n-color);
 color: var(--n-text-color);
 box-sizing: border-box;
 `,[rt(),Qe(),it(),Ge(),w("unselectable",`
 user-select: none; 
 -webkit-user-select: none;
 `),w("native-scrollbar",[h("drawer-content-wrapper",`
 overflow: auto;
 height: 100%;
 `)]),B("resize-trigger",`
 position: absolute;
 background-color: #0000;
 transition: background-color .3s var(--n-bezier);
 `,[w("hover",`
 background-color: var(--n-resize-trigger-color-hover);
 `)]),h("drawer-content-wrapper",`
 box-sizing: border-box;
 `),h("drawer-content",`
 height: 100%;
 display: flex;
 flex-direction: column;
 `,[w("native-scrollbar",[h("drawer-body-content-wrapper",`
 height: 100%;
 overflow: auto;
 `)]),h("drawer-body",`
 flex: 1 0 0;
 overflow: hidden;
 `),h("drawer-body-content-wrapper",`
 box-sizing: border-box;
 padding: var(--n-body-padding);
 `),h("drawer-header",`
 font-weight: var(--n-title-font-weight);
 line-height: 1;
 font-size: var(--n-title-font-size);
 color: var(--n-title-text-color);
 padding: var(--n-header-padding);
 transition: border .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-divider-color);
 border-bottom: var(--n-header-border-bottom);
 display: flex;
 justify-content: space-between;
 align-items: center;
 `,[B("main",`
 flex: 1;
 `),B("close",`
 margin-left: 6px;
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `)]),h("drawer-footer",`
 display: flex;
 justify-content: flex-end;
 border-top: var(--n-footer-border-top);
 transition: border .3s var(--n-bezier);
 padding: var(--n-footer-padding);
 `)]),w("right-placement",`
 top: 0;
 bottom: 0;
 right: 0;
 border-top-left-radius: var(--n-border-radius);
 border-bottom-left-radius: var(--n-border-radius);
 `,[B("resize-trigger",`
 width: 3px;
 height: 100%;
 top: 0;
 left: 0;
 transform: translateX(-1.5px);
 cursor: ew-resize;
 `)]),w("left-placement",`
 top: 0;
 bottom: 0;
 left: 0;
 border-top-right-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `,[B("resize-trigger",`
 width: 3px;
 height: 100%;
 top: 0;
 right: 0;
 transform: translateX(1.5px);
 cursor: ew-resize;
 `)]),w("top-placement",`
 top: 0;
 left: 0;
 right: 0;
 border-bottom-left-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `,[B("resize-trigger",`
 width: 100%;
 height: 3px;
 bottom: 0;
 left: 0;
 transform: translateY(1.5px);
 cursor: ns-resize;
 `)]),w("bottom-placement",`
 left: 0;
 bottom: 0;
 right: 0;
 border-top-left-radius: var(--n-border-radius);
 border-top-right-radius: var(--n-border-radius);
 `,[B("resize-trigger",`
 width: 100%;
 height: 3px;
 top: 0;
 left: 0;
 transform: translateY(-1.5px);
 cursor: ns-resize;
 `)])]),n("body",[n(">",[h("drawer-container",`
 position: fixed;
 `)])]),h("drawer-container",`
 position: relative;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 `,[n("> *",`
 pointer-events: all;
 `)]),h("drawer-mask",`
 background-color: rgba(0, 0, 0, .3);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `,[w("invisible",`
 background-color: rgba(0, 0, 0, 0)
 `),De({enterDuration:"0.2s",leaveDuration:"0.2s",enterCubicBezier:"var(--n-bezier-in)",leaveCubicBezier:"var(--n-bezier-out)"})])]);const at=["onClick"],lt={...ne.props,show:Boolean,width:[Number,String],height:[Number,String],placement:{type:String,default:"right"},maskClosable:{type:Boolean,default:!0},showMask:{type:[Boolean,String],default:!0},to:[String,Object],displayDirective:{type:String,default:"if"},nativeScrollbar:{type:Boolean,default:!0},zIndex:Number,onMaskClick:Function,scrollbarProps:Object,contentClass:String,contentStyle:[Object,String],trapFocus:{type:Boolean,default:!0},onEsc:Function,autoFocus:{type:Boolean,default:!0},closeOnEsc:{type:Boolean,default:!0},blockScroll:{type:Boolean,default:!0},maxWidth:Number,maxHeight:Number,minWidth:Number,minHeight:Number,resizable:Boolean,defaultWidth:{type:[Number,String],default:251},defaultHeight:{type:[Number,String],default:251},onUpdateWidth:[Function,Array],onUpdateHeight:[Function,Array],"onUpdate:width":[Function,Array],"onUpdate:height":[Function,Array],"onUpdate:show":[Function,Array],onUpdateShow:[Function,Array],onAfterEnter:Function,onAfterLeave:Function,drawerStyle:[String,Object],drawerClass:String,target:null,onShow:Function,onHide:Function};var ft=X({name:"Drawer",inheritAttrs:!1,props:lt,setup(e){const{mergedClsPrefixRef:t,namespaceRef:r,inlineThemeDisabled:v}=oe(e),f=Ie(),C=ne("Drawer","-drawer",st,Le,e,t),u=F(e.defaultWidth),p=F(e.defaultHeight),y=Q(K(e,"width"),u),k=Q(K(e,"height"),p),M=z(()=>{const{placement:o}=e;return o==="top"||o==="bottom"?"":Z(y.value)}),T=z(()=>{const{placement:o}=e;return o==="left"||o==="right"?"":Z(k.value)}),H=o=>{const{onUpdateWidth:l,"onUpdate:width":c}=e;l&&E(l,o),c&&E(c,o),u.value=o},x=o=>{const{onUpdateHeight:l,"onUpdate:width":c}=e;l&&E(l,o),c&&E(c,o),p.value=o},b=z(()=>[{width:M.value,height:T.value},e.drawerStyle||""]);function P(o){const{onMaskClick:l,maskClosable:c}=e;c&&O(!1),l&&l(o)}function L(o){P(o)}const N=We();function U(o){e.onEsc?.(),e.show&&e.closeOnEsc&&Ae(o)&&(N.value||O(!1))}function O(o){const{onHide:l,onUpdateShow:c,"onUpdate:show":i}=e;c&&E(c,o),i&&E(i,o),l&&!o&&E(l,o)}W(V,{isMountedRef:f,mergedThemeRef:C,mergedClsPrefixRef:t,doUpdateShow:O,doUpdateHeight:x,doUpdateWidth:H});const I=z(()=>{const{common:{cubicBezierEaseInOut:o,cubicBezierEaseIn:l,cubicBezierEaseOut:c},self:{color:i,textColor:s,boxShadow:d,lineHeight:ie,headerPadding:se,footerPadding:ae,borderRadius:le,bodyPadding:de,titleFontSize:ce,titleTextColor:ue,titleFontWeight:he,headerBorderBottom:fe,footerBorderTop:be,closeIconColor:me,closeIconColorHover:ge,closeIconColorPressed:ve,closeColorHover:pe,closeColorPressed:ye,closeIconSize:we,closeSize:Se,closeBorderRadius:Ce,resizableTriggerColorHover:ze}}=C.value;return{"--n-line-height":ie,"--n-color":i,"--n-border-radius":le,"--n-text-color":s,"--n-box-shadow":d,"--n-bezier":o,"--n-bezier-out":c,"--n-bezier-in":l,"--n-header-padding":se,"--n-body-padding":de,"--n-footer-padding":ae,"--n-title-text-color":ue,"--n-title-font-size":ce,"--n-title-font-weight":he,"--n-header-border-bottom":fe,"--n-footer-border-top":be,"--n-close-icon-color":me,"--n-close-icon-color-hover":ge,"--n-close-icon-color-pressed":ve,"--n-close-size":Se,"--n-close-color-hover":pe,"--n-close-color-pressed":ye,"--n-close-icon-size":we,"--n-close-border-radius":Ce,"--n-resize-trigger-color-hover":ze}}),D=v?_e("drawer",void 0,I,e):void 0;return{mergedClsPrefix:t,namespace:r,mergedBodyStyle:b,handleOutsideClick:L,handleMaskClick:P,handleEsc:U,mergedTheme:C,cssVars:v?void 0:I,themeClass:D?.themeClass,onRender:D?.onRender,isMounted:f}},render(){const{mergedClsPrefix:e}=this;return a(),$(Pe,{to:this.to,show:this.show},{default:()=>(this.onRender?.(),j((a(),g("div",{class:m([`${e}-drawer-container`,this.namespace,this.themeClass]),style:R(this.cssVars),role:"none"},[this.showMask?(a(),$(ee,{key:0,name:"fade-in-transition",appear:this.isMounted},{default:()=>this.show?(a(),g("div",{key:1,"aria-hidden":!0,class:m([`${e}-drawer-mask`,this.showMask==="transparent"&&`${e}-drawer-mask--invisible`]),onClick:this.handleMaskClick},null,10,at)):null},1032,["appear"])):S(()=>null),(a(),$(Ve,_(this.$attrs,{class:[this.drawerClass,this.$attrs.class],style:[this.mergedBodyStyle,this.$attrs.style],blockScroll:this.blockScroll,contentStyle:this.contentStyle,contentClass:this.contentClass,placement:this.placement,scrollbarProps:this.scrollbarProps,show:this.show,displayDirective:this.displayDirective,nativeScrollbar:this.nativeScrollbar,onAfterEnter:this.onAfterEnter,onAfterLeave:this.onAfterLeave,trapFocus:this.trapFocus,autoFocus:this.autoFocus,resizable:this.resizable,maxHeight:this.maxHeight,minHeight:this.minHeight,maxWidth:this.maxWidth,minWidth:this.minWidth,showMask:this.showMask,onEsc:this.handleEsc,onClickoutside:this.handleOutsideClick}),Y(this.$slots),1040,["class","style","blockScroll","contentStyle","contentClass","placement","scrollbarProps","show","displayDirective","nativeScrollbar","onAfterEnter","onAfterLeave","trapFocus","autoFocus","resizable","maxHeight","minHeight","maxWidth","minWidth","showMask","onEsc","onClickoutside"]))],6)),[[Ne,{zIndex:this.zIndex,enabled:this.show}]]))},1032,["to","show"])}});const dt={title:String,headerClass:String,headerStyle:[Object,String],footerClass:String,footerStyle:[Object,String],bodyClass:String,bodyStyle:[Object,String],bodyContentClass:String,bodyContentStyle:[Object,String],nativeScrollbar:{type:Boolean,default:!0},scrollbarProps:Object,closable:Boolean};var bt=X({name:"DrawerContent",props:dt,slots:Object,setup(){const e=re(V,null);e||Ue("drawer-content","`n-drawer-content` must be placed inside `n-drawer`.");const{doUpdateShow:t}=e;function r(){t(!1)}return{handleCloseClick:r,mergedTheme:e.mergedThemeRef,mergedClsPrefix:e.mergedClsPrefixRef}},render(){const{title:e,mergedClsPrefix:t,nativeScrollbar:r,mergedTheme:v,bodyClass:f,bodyStyle:C,bodyContentClass:u,bodyContentStyle:p,headerClass:y,headerStyle:k,footerClass:M,footerStyle:T,scrollbarProps:H,closable:x,$slots:b}=this;return a(),g("div",{role:"none",class:m([`${t}-drawer-content`,r&&`${t}-drawer-content--native-scrollbar`])},[b.header||e||x?(a(),g("div",{key:0,class:m([`${t}-drawer-header`,y]),style:R(k),role:"none"},[G("div",{class:m(`${t}-drawer-header__main`),role:"heading","aria-level":"1"},[b.header!==void 0?(a(),g(J,{key:0},[S(()=>b.header())],64)):(a(),g(J,{key:1},[S(()=>e)],64))],2),S(()=>x&&(a(),$(je,{onClick:this.handleCloseClick,clsPrefix:t,class:m(`${t}-drawer-header__close`),absolute:!0},null,8,["onClick","clsPrefix","class"])))],6)):S(()=>null),r?(a(),g("div",{key:2,class:m([`${t}-drawer-body`,f]),style:R(C),role:"none"},[G("div",{class:m([`${t}-drawer-body-content-wrapper`,u]),style:R(p),role:"none"},[S(()=>b.default?.())],6)],6)):(a(),$(te,_({key:3,themeOverrides:v.peerOverrides.Scrollbar,theme:v.peers.Scrollbar},H,{class:`${t}-drawer-body`,contentClass:[`${t}-drawer-body-content-wrapper`,u],contentStyle:p}),Y(b),1040,["themeOverrides","theme","class","contentClass","contentStyle"])),b.footer?(a(),g("div",{key:4,class:m([`${t}-drawer-footer`,M]),style:R(T),role:"none"},[S(()=>b.footer())],6)):S(()=>null)],2)}});export{bt as D,ft as a};
