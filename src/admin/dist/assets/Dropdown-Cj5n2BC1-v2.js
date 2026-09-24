import{l as x,m as S,I as _,d as D,n as ne,bi as be,X as G,x as W,y as we,b$ as Oe,D as ye,E as v,k as pe,a,c as b,q as R,F,al as ge,t as y,r as g,T as oe,L as $,bc as xe,M as T,bu as Se,U as ee,bd as Ae,G as q,J as Z,c0 as Be,bv as Fe,bt as Te,b7 as Me,P as he,H as z,Y as Ee,N as C,c1 as Le,O as ce,ap as B}from"./index-BwbiZBuu-v2.js";import{B as je,V as He,b as Ve,r as Ue,p as Re,P as qe}from"./Popover-DqRNvEh6-v2.js";import{C as We}from"./ChevronRight-DgfR2faf-v2.js";import{f as Ge}from"./format-length-BJ9L9utZ-v2.js";import{h as ve}from"./happens-in-CM8LO42l-v2.js";import{u as Xe}from"./use-merged-state-DIGdH2Vz-v2.js";import{u as Je}from"./use-keyboard-DPfp5sUQ-v2.js";import{c as Ye}from"./create-B8zGgGzF-v2.js";function Qe(e){return n=>{n?e.value=n.$el:e.value=null}}var Ze=x("icon",`
 height: 1em;
 width: 1em;
 line-height: 1em;
 text-align: center;
 display: inline-block;
 position: relative;
 fill: currentColor;
`,[S("color-transition",{transition:"color .3s var(--n-bezier)"}),S("depth",{color:"var(--n-color)"},[_("svg",{opacity:"var(--n-opacity)",transition:"opacity .3s var(--n-bezier)"})]),_("svg",{height:"1em",width:"1em"})]);const eo={...ne.props,depth:[String,Number],size:[Number,String],color:String,component:[Object,Function]},oo=D({_n_icon__:!0,name:"Icon",inheritAttrs:!1,props:eo,setup(e){const{mergedClsPrefixRef:n,inlineThemeDisabled:d}=we(e),r=ne("Icon","-icon",Ze,Oe,e,n),t=v(()=>{const{depth:l}=e,{common:{cubicBezierEaseInOut:c},self:m}=r.value;if(l!==void 0){const{color:N,[`opacity${l}Depth`]:k}=m;return{"--n-bezier":c,"--n-color":N,"--n-opacity":k}}return{"--n-bezier":c,"--n-color":"","--n-opacity":""}}),i=d?ye("icon",v(()=>`${e.depth||"d"}`),t,e):void 0;return{mergedClsPrefix:n,mergedStyle:v(()=>{const{size:l,color:c}=e;return{fontSize:Ge(l),color:c}}),cssVars:d?void 0:t,themeClass:i?.themeClass,onRender:i?.onRender}},render(){const{$parent:e,depth:n,mergedClsPrefix:d,component:r,onRender:t,themeClass:i}=this;return e?.$options?._n_icon__&&be("icon","don't wrap `n-icon` inside `n-icon`"),t?.(),G("i",W(this.$attrs,{role:"img",class:[`${d}-icon`,i,{[`${d}-icon--depth`]:n,[`${d}-icon--color-transition`]:n!==void 0}],style:[this.cssVars,this.mergedStyle]}),r?G(r):this.$slots.default?.())}}),fe=pe("n-dropdown-menu"),re=pe("n-dropdown"),me=pe("n-dropdown-option");var Pe=D({name:"DropdownDivider",props:{clsPrefix:{type:String,required:!0}},render(){return a(),b("div",{class:R(`${this.clsPrefix}-dropdown-divider`)},null,2)}});function ue(e,n){return e.type==="submenu"||e.type===void 0&&e[n]!==void 0}function no(e){return e.type==="group"}function Ne(e){return e.type==="divider"}function ro(e){return e.type==="render"}function to(e,n,d){const r=F(e.value);let t=null;return ge(e,i=>{t!==null&&window.clearTimeout(t),i===!0?d&&!d.value?r.value=!0:t=window.setTimeout(()=>{r.value=!0},n):r.value=!1}),r}var ke=D({name:"DropdownOption",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0},parentKey:{type:[String,Number],default:null},placement:{type:String,default:"right-start"},props:Object,scrollable:Boolean},setup(e){const n=T(re),{hoverKeyRef:d,keyboardKeyRef:r,lastToggledSubmenuKeyRef:t,pendingKeyPathRef:i,activeKeyPathRef:l,animatedRef:c,mergedShowRef:m,renderLabelRef:N,renderIconRef:k,labelFieldRef:K,childrenFieldRef:P,renderOptionRef:M,nodePropsRef:E,menuPropsRef:I}=n,L=T(me,null),j=T(fe),H=T(Se),Y=v(()=>e.tmNode.rawNode),X=v(()=>{const{value:o}=P;return ue(e.tmNode.rawNode,o)}),te=v(()=>{const{disabled:o}=e.tmNode;return o}),ie=v(()=>{if(!X.value)return!1;const{key:o,disabled:s}=e.tmNode;if(s)return!1;const{value:w}=d,{value:O}=r,{value:se}=t,{value:A}=i;return w!==null?A.includes(o):O!==null?A.includes(o)&&A[A.length-1]!==o:se!==null?A.includes(o):!1}),de=v(()=>r.value===null&&!c.value),ae=to(ie,300,de),le=v(()=>!!L?.enteringSubmenuRef.value),V=F(!1);q(me,{enteringSubmenuRef:V});function U(){V.value=!0}function Q(){V.value=!1}function J(){const{parentKey:o,tmNode:s}=e;s.disabled||m.value&&(t.value=o,r.value=null,d.value=s.key)}function u(){const{tmNode:o}=e;o.disabled||m.value&&d.value!==o.key&&J()}function p(o){if(e.tmNode.disabled||!m.value)return;const{relatedTarget:s}=o;s&&!ve({target:s},"dropdownOption")&&!ve({target:s},"scrollbarRail")&&(d.value=null)}function h(){const{value:o}=X,{tmNode:s}=e;m.value&&!o&&!s.disabled&&(n.doSelect(s.key,s.rawNode),n.doUpdateShow(!1))}return{labelField:K,renderLabel:N,renderIcon:k,siblingHasIcon:j.showIconRef,siblingHasSubmenu:j.hasSubmenuRef,menuProps:I,popoverBody:H,animated:c,mergedShowSubmenu:v(()=>ae.value&&!le.value),rawNode:Y,hasSubmenu:X,pending:ee(()=>{const{value:o}=i,{key:s}=e.tmNode;return o.includes(s)}),childActive:ee(()=>{const{value:o}=l,{key:s}=e.tmNode,w=o.findIndex(O=>s===O);return w===-1?!1:w<o.length-1}),active:ee(()=>{const{value:o}=l,{key:s}=e.tmNode,w=o.findIndex(O=>s===O);return w===-1?!1:w===o.length-1}),mergedDisabled:te,renderOption:M,nodeProps:E,handleClick:h,handleMouseMove:u,handleMouseEnter:J,handleMouseLeave:p,handleSubmenuBeforeEnter:U,handleSubmenuAfterEnter:Q}},render(){const{animated:e,rawNode:n,mergedShowSubmenu:d,clsPrefix:r,siblingHasIcon:t,siblingHasSubmenu:i,renderLabel:l,renderIcon:c,renderOption:m,nodeProps:N,props:k,scrollable:K}=this;let P=null;if(d){const L=this.menuProps?.(n,n.children);P=(j=>(a(),y(Ce,W({key:1},L,{clsPrefix:r,scrollable:this.scrollable,tmNodes:this.tmNode.children,parentKey:this.tmNode.key}),null,16,["clsPrefix","scrollable","tmNodes","parentKey"])))()}const M={class:[`${r}-dropdown-option-body`,this.pending&&`${r}-dropdown-option-body--pending`,this.active&&`${r}-dropdown-option-body--active`,this.childActive&&`${r}-dropdown-option-body--child-active`,this.mergedDisabled&&`${r}-dropdown-option-body--disabled`],onMousemove:this.handleMouseMove,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onClick:this.handleClick},E=N?.(n),I=(a(),b("div",W({class:[`${r}-dropdown-option`,E?.class],"data-dropdown-option":!0},E),[g(()=>G("div",W(M,k),[(a(),b("div",{class:R([`${r}-dropdown-option-body__prefix`,t&&`${r}-dropdown-option-body__prefix--show-icon`])},[g(()=>[c?c(n):oe(n.icon)])],2)),(a(),b("div",{"data-dropdown-option":!0,class:R(`${r}-dropdown-option-body__label`)},[l?(a(),b($,{key:0},[g(()=>l(n))],64)):(a(),b($,{key:1},[g(()=>oe(n[this.labelField]??n.title))],64))],2)),(a(),b("div",{"data-dropdown-option":!0,class:R([`${r}-dropdown-option-body__suffix`,i&&`${r}-dropdown-option-body__suffix--has-submenu`])},[this.hasSubmenu?(a(),y(oo,{key:0},{_:1,default:xe(()=>(a(),y(We)))})):g(()=>null)],2))])),this.hasSubmenu?(a(),y(je,{key:0},{default:()=>[(a(),y(He,null,{default:()=>(a(),b("div",{class:R(`${r}-dropdown-offset-container`)},[(a(),y(Ve,{show:this.mergedShowSubmenu,placement:this.placement,to:K&&this.popoverBody||void 0,teleportDisabled:!K},{default:()=>(a(),b("div",{class:R(`${r}-dropdown-menu-wrapper`)},[e?(a(),y(Ae,{key:0,onBeforeEnter:this.handleSubmenuBeforeEnter,onAfterEnter:this.handleSubmenuAfterEnter,name:"fade-in-scale-up-transition",appear:!0},{default:()=>P},1032,["onBeforeEnter","onAfterEnter"])):(a(),b($,{key:1},[g(()=>P)],64))],2))},1032,["show","placement","to","teleportDisabled"]))],2))},1024))]},1024)):g(()=>null)],16));return m?m({node:I,option:n}):I}}),io=D({name:"DropdownGroupHeader",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){const{showIconRef:e,hasSubmenuRef:n}=T(fe),{renderLabelRef:d,labelFieldRef:r,nodePropsRef:t,renderOptionRef:i}=T(re);return{labelField:r,showIcon:e,hasSubmenu:n,renderLabel:d,nodeProps:t,renderOption:i}},render(){const{clsPrefix:e,hasSubmenu:n,showIcon:d,nodeProps:r,renderLabel:t,renderOption:i}=this,{rawNode:l}=this.tmNode,c=(a(),b("div",W({class:`${e}-dropdown-option`},r?.(l)),[Z("div",{class:R(`${e}-dropdown-option-body ${e}-dropdown-option-body--group`)},[Z("div",{"data-dropdown-option":!0,class:R([`${e}-dropdown-option-body__prefix`,d&&`${e}-dropdown-option-body__prefix--show-icon`])},[g(()=>oe(l.icon))],2),Z("div",{class:R(`${e}-dropdown-option-body__label`),"data-dropdown-option":!0},[t?(a(),b($,{key:0},[g(()=>t(l))],64)):(a(),b($,{key:1},[g(()=>oe(l.title??l[this.labelField]))],64))],2),Z("div",{class:R([`${e}-dropdown-option-body__suffix`,n&&`${e}-dropdown-option-body__suffix--has-submenu`]),"data-dropdown-option":!0},null,2)],2)],16));return i?i({node:c,option:l}):c}}),ao=D({name:"NDropdownGroup",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0},parentKey:{type:[String,Number],default:null}},render(){const{tmNode:e,parentKey:n,clsPrefix:d}=this,{children:r}=e;return a(),b($,null,[(a(),y(io,{clsPrefix:d,tmNode:e,key:e.key},null,8,["clsPrefix","tmNode"])),g(()=>r?.map(t=>{const{rawNode:i}=t;return i.show===!1?null:Ne(i)?G(Pe,{clsPrefix:d,key:t.key}):t.isGroup?(be("dropdown","`group` node is not allowed to be put in `group` node."),null):(a(),y(ke,{clsPrefix:d,tmNode:t,parentKey:n,key:t.key},null,8,["clsPrefix","tmNode","parentKey"]))}))],64)}}),lo=D({name:"DropdownRenderOption",props:{tmNode:{type:Object,required:!0}},render(){const{rawNode:{render:e,props:n}}=this.tmNode;return G("div",n,[e?.()])}}),Ce=D({name:"DropdownMenu",props:{scrollable:Boolean,showArrow:Boolean,arrowStyle:[String,Object],clsPrefix:{type:String,required:!0},tmNodes:{type:Array,default:()=>[]},parentKey:{type:[String,Number],default:null}},setup(e){const{renderIconRef:n,childrenFieldRef:d}=T(re);q(fe,{showIconRef:v(()=>{const t=n.value;return e.tmNodes.some(i=>{if(i.isGroup)return i.children?.some(({rawNode:c})=>t?t(c):c.icon);const{rawNode:l}=i;return t?t(l):l.icon})}),hasSubmenuRef:v(()=>{const{value:t}=d;return e.tmNodes.some(i=>{if(i.isGroup)return i.children?.some(({rawNode:c})=>ue(c,t));const{rawNode:l}=i;return ue(l,t)})})});const r=F(null);return q(Fe,null),q(Te,null),q(Se,r),{bodyRef:r}},render(){const{parentKey:e,clsPrefix:n,scrollable:d}=this,r=this.tmNodes.map(t=>{const{rawNode:i}=t;return i.show===!1?null:ro(i)?(a(),y(lo,{tmNode:t,key:t.key},null,8,["tmNode"])):Ne(i)?(a(),y(Pe,{clsPrefix:n,key:t.key},null,8,["clsPrefix"])):no(i)?(a(),y(ao,{clsPrefix:n,tmNode:t,parentKey:e,key:t.key},null,8,["clsPrefix","tmNode","parentKey"])):(a(),y(ke,{clsPrefix:n,tmNode:t,parentKey:e,key:t.key,props:i.props,scrollable:d},null,8,["clsPrefix","tmNode","parentKey","props","scrollable"]))});return a(),b("div",{class:R([`${n}-dropdown-menu`,d&&`${n}-dropdown-menu--scrollable`]),ref:"bodyRef"},[d?(a(),y(Be,{key:0,contentClass:`${n}-dropdown-menu__content`},{default:()=>r},1032,["contentClass"])):(a(),b($,{key:1},[g(()=>r)],64)),this.showArrow?(a(),b($,{key:2},[g(()=>Ue({clsPrefix:n,arrowStyle:this.arrowStyle,arrowClass:void 0,arrowWrapperClass:void 0,arrowWrapperStyle:void 0}))],64)):g(()=>null)],2)}}),so=x("dropdown-menu",`
 transform-origin: var(--v-transform-origin);
 background-color: var(--n-color);
 border-radius: var(--n-border-radius);
 box-shadow: var(--n-box-shadow);
 position: relative;
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
`,[Me(),x("dropdown-option",`
 position: relative;
 `,[_("a",`
 text-decoration: none;
 color: inherit;
 outline: none;
 `,[_("&::before",`
 content: "";
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)]),x("dropdown-option-body",`
 display: flex;
 cursor: pointer;
 position: relative;
 height: var(--n-option-height);
 line-height: var(--n-option-height);
 font-size: var(--n-font-size);
 color: var(--n-option-text-color);
 transition: color .3s var(--n-bezier);
 `,[_("&::before",`
 content: "";
 position: absolute;
 top: 0;
 bottom: 0;
 left: 4px;
 right: 4px;
 transition: background-color .3s var(--n-bezier);
 border-radius: var(--n-border-radius);
 `),he("disabled",[S("pending",`
 color: var(--n-option-text-color-hover);
 `,[z("prefix, suffix",`
 color: var(--n-option-text-color-hover);
 `),_("&::before","background-color: var(--n-option-color-hover);")]),S("active",`
 color: var(--n-option-text-color-active);
 `,[z("prefix, suffix",`
 color: var(--n-option-text-color-active);
 `),_("&::before","background-color: var(--n-option-color-active);")]),S("child-active",`
 color: var(--n-option-text-color-child-active);
 `,[z("prefix, suffix",`
 color: var(--n-option-text-color-child-active);
 `)])]),S("disabled",`
 cursor: not-allowed;
 opacity: var(--n-option-opacity-disabled);
 `),S("group",`
 font-size: calc(var(--n-font-size) - 1px);
 color: var(--n-group-header-text-color);
 `,[z("prefix",`
 width: calc(var(--n-option-prefix-width) / 2);
 `,[S("show-icon",`
 width: calc(var(--n-option-icon-prefix-width) / 2);
 `)])]),z("prefix",`
 width: var(--n-option-prefix-width);
 display: flex;
 justify-content: center;
 align-items: center;
 color: var(--n-prefix-color);
 transition: color .3s var(--n-bezier);
 z-index: 1;
 `,[S("show-icon",`
 width: var(--n-option-icon-prefix-width);
 `),x("icon",`
 font-size: var(--n-option-icon-size);
 `)]),z("label",`
 white-space: nowrap;
 flex: 1;
 z-index: 1;
 `),z("suffix",`
 box-sizing: border-box;
 flex-grow: 0;
 flex-shrink: 0;
 display: flex;
 justify-content: flex-end;
 align-items: center;
 min-width: var(--n-option-suffix-width);
 padding: 0 8px;
 transition: color .3s var(--n-bezier);
 color: var(--n-suffix-color);
 z-index: 1;
 `,[S("has-submenu",`
 width: var(--n-option-icon-suffix-width);
 `),x("icon",`
 font-size: var(--n-option-icon-size);
 `)]),x("dropdown-menu","pointer-events: all;")]),x("dropdown-offset-container",`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: -4px;
 bottom: -4px;
 `)]),x("dropdown-divider",`
 transition: background-color .3s var(--n-bezier);
 background-color: var(--n-divider-color);
 height: 1px;
 margin: 4px 0;
 `),x("dropdown-menu-wrapper",`
 transform-origin: var(--v-transform-origin);
 width: fit-content;
 `),_(">",[x("scrollbar",`
 height: inherit;
 max-height: inherit;
 `)]),he("scrollable",`
 padding: var(--n-padding);
 `),S("scrollable",[z("content",`
 padding: var(--n-padding);
 `)])]);const co={animated:{type:Boolean,default:!0},keyboard:{type:Boolean,default:!0},size:String,inverted:Boolean,placement:{type:String,default:"bottom"},onSelect:[Function,Array],options:{type:Array,default:()=>[]},menuProps:Function,showArrow:Boolean,renderLabel:Function,renderIcon:Function,renderOption:Function,nodeProps:Function,labelField:{type:String,default:"label"},keyField:{type:String,default:"key"},childrenField:{type:String,default:"children"},value:[String,Number]},uo=Object.keys(Re),po={...Re,...co,...ne.props};var xo=D({name:"Dropdown",inheritAttrs:!1,props:po,setup(e){const n=F(!1),d=Xe(C(e,"show"),n),r=v(()=>{const{keyField:u,childrenField:p}=e;return Ye(e.options,{getKey(h){return h[u]},getDisabled(h){return h.disabled===!0},getIgnored(h){return h.type==="divider"||h.type==="render"},getChildren(h){return h[p]}})}),t=v(()=>r.value.treeNodes),i=F(null),l=F(null),c=F(null),m=v(()=>i.value??l.value??c.value??null),N=v(()=>r.value.getPath(m.value).keyPath),k=v(()=>r.value.getPath(e.value).keyPath),K=ee(()=>e.keyboard&&d.value);Je({keydown:{ArrowUp:{prevent:!0,handler:de},ArrowRight:{prevent:!0,handler:ie},ArrowDown:{prevent:!0,handler:ae},ArrowLeft:{prevent:!0,handler:te},Enter:{prevent:!0,handler:le},Escape:X}},K);const{mergedClsPrefixRef:P,inlineThemeDisabled:M,mergedComponentPropsRef:E}=we(e),I=v(()=>e.size||E?.value?.Dropdown?.size||"medium"),L=ne("Dropdown","-dropdown",so,Le,e,P);q(re,{labelFieldRef:C(e,"labelField"),childrenFieldRef:C(e,"childrenField"),renderLabelRef:C(e,"renderLabel"),renderIconRef:C(e,"renderIcon"),hoverKeyRef:i,keyboardKeyRef:l,lastToggledSubmenuKeyRef:c,pendingKeyPathRef:N,activeKeyPathRef:k,animatedRef:C(e,"animated"),mergedShowRef:d,nodePropsRef:C(e,"nodeProps"),renderOptionRef:C(e,"renderOption"),menuPropsRef:C(e,"menuProps"),doSelect:j,doUpdateShow:H}),ge(d,u=>{!e.animated&&!u&&Y()});function j(u,p){const{onSelect:h}=e;h&&ce(h,u,p)}function H(u){const{"onUpdate:show":p,onUpdateShow:h}=e;p&&ce(p,u),h&&ce(h,u),n.value=u}function Y(){i.value=null,l.value=null,c.value=null}function X(){H(!1)}function te(){U("left")}function ie(){U("right")}function de(){U("up")}function ae(){U("down")}function le(){const u=V();u?.isLeaf&&d.value&&(j(u.key,u.rawNode),H(!1))}function V(){const{value:u}=r,{value:p}=m;return!u||p===null?null:u.getNode(p)??null}function U(u){const{value:p}=m,{value:{getFirstAvailableNode:h}}=r;let o=null;if(p===null){const s=h();s!==null&&(o=s.key)}else{const s=V();if(s){let w;switch(u){case"down":w=s.getNext();break;case"up":w=s.getPrev();break;case"right":w=s.getChild();break;case"left":w=s.getParent()}w&&(o=w.key)}}o!==null&&(i.value=null,l.value=o)}const Q=v(()=>{const{inverted:u}=e,p=I.value,{common:{cubicBezierEaseInOut:h},self:o}=L.value,{padding:s,dividerColor:w,borderRadius:O,optionOpacityDisabled:se,[B("optionIconSuffixWidth",p)]:A,[B("optionSuffixWidth",p)]:Ke,[B("optionIconPrefixWidth",p)]:Ie,[B("optionPrefixWidth",p)]:ze,[B("fontSize",p)]:_e,[B("optionHeight",p)]:$e,[B("optionIconSize",p)]:De}=o,f={"--n-bezier":h,"--n-font-size":_e,"--n-padding":s,"--n-border-radius":O,"--n-option-height":$e,"--n-option-prefix-width":ze,"--n-option-icon-prefix-width":Ie,"--n-option-suffix-width":Ke,"--n-option-icon-suffix-width":A,"--n-option-icon-size":De,"--n-divider-color":w,"--n-option-opacity-disabled":se};return u?(f["--n-color"]=o.colorInverted,f["--n-option-color-hover"]=o.optionColorHoverInverted,f["--n-option-color-active"]=o.optionColorActiveInverted,f["--n-option-text-color"]=o.optionTextColorInverted,f["--n-option-text-color-hover"]=o.optionTextColorHoverInverted,f["--n-option-text-color-active"]=o.optionTextColorActiveInverted,f["--n-option-text-color-child-active"]=o.optionTextColorChildActiveInverted,f["--n-prefix-color"]=o.prefixColorInverted,f["--n-suffix-color"]=o.suffixColorInverted,f["--n-group-header-text-color"]=o.groupHeaderTextColorInverted):(f["--n-color"]=o.color,f["--n-option-color-hover"]=o.optionColorHover,f["--n-option-color-active"]=o.optionColorActive,f["--n-option-text-color"]=o.optionTextColor,f["--n-option-text-color-hover"]=o.optionTextColorHover,f["--n-option-text-color-active"]=o.optionTextColorActive,f["--n-option-text-color-child-active"]=o.optionTextColorChildActive,f["--n-prefix-color"]=o.prefixColor,f["--n-suffix-color"]=o.suffixColor,f["--n-group-header-text-color"]=o.groupHeaderTextColor),f}),J=M?ye("dropdown",v(()=>`${I.value[0]}${e.inverted?"i":""}`),Q,e):void 0;return{mergedClsPrefix:P,mergedTheme:L,mergedSize:I,tmNodes:t,mergedShow:d,handleAfterLeave:()=>{e.animated&&Y()},doUpdateShow:H,cssVars:M?void 0:Q,themeClass:J?.themeClass,onRender:J?.onRender}},render(){const e=(r,t,i,l,c)=>{const{mergedClsPrefix:m,menuProps:N}=this;this.onRender?.();const k=N?.(void 0,this.tmNodes.map(P=>P.rawNode))||{},K={ref:Qe(t),class:[r,`${m}-dropdown`,`${m}-dropdown--${this.mergedSize}-size`,this.themeClass],clsPrefix:m,tmNodes:this.tmNodes,style:[...i,this.cssVars],showArrow:this.showArrow,arrowStyle:this.arrowStyle,scrollable:this.scrollable,onMouseenter:l,onMouseleave:c};return G(Ce,W(this.$attrs,K,k))},{mergedTheme:n}=this,d={show:this.mergedShow,theme:n.peers.Popover,themeOverrides:n.peerOverrides.Popover,internalOnAfterLeave:this.handleAfterLeave,internalRenderBody:e,onUpdateShow:this.doUpdateShow,"onUpdate:show":void 0};return a(),y(qe,Ee(this.$props,uo,d),{_:1,trigger:xe(()=>this.$slots.default?.())},16)}});export{xo as D,Qe as c};
