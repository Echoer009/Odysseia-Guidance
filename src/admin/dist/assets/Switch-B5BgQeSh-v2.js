import{i as ve,bg as ge,bh as me,l as X,H as a,bi as Y,I as H,m as s,P as q,d as we,n as Q,bj as O,a as b,c as y,J as k,r as l,q as i,p as J,y as pe,ax as xe,F as U,D as ye,N as ke,E as D,O as A,an as p,t as G,bk as Se,ap as x,aR as E,bl as d,bm as Ce,x as Be}from"./index-Dil_0rw6-v2.js";import{u as Re}from"./use-merged-state-BU3zbU1b-v2.js";function _e(e){const{primaryColor:c,opacityDisabled:f,borderRadius:n,textColor3:S}=e;return{...ge,iconColor:S,textColor:"white",loadingColor:c,opacityDisabled:f,railColor:"rgba(0, 0, 0, .14)",railColorActive:c,buttonBoxShadow:"0 1px 4px 0 rgba(0, 0, 0, 0.3), inset 0 0 1px 0 rgba(0, 0, 0, 0.05)",buttonColor:"#FFF",railBorderRadiusSmall:n,railBorderRadiusMedium:n,railBorderRadiusLarge:n,buttonBorderRadiusSmall:n,buttonBorderRadiusMedium:n,buttonBorderRadiusLarge:n,boxShadowFocus:`0 0 0 2px ${me(c,{alpha:.2})}`}}const $e={common:ve,self:_e};var ze=X("switch",`
 height: var(--n-height);
 min-width: var(--n-width);
 vertical-align: middle;
 user-select: none;
 -webkit-user-select: none;
 display: inline-flex;
 outline: none;
 justify-content: center;
 align-items: center;
`,[a("children-placeholder",`
 height: var(--n-rail-height);
 display: flex;
 flex-direction: column;
 overflow: hidden;
 pointer-events: none;
 visibility: hidden;
 `),a("rail-placeholder",`
 display: flex;
 flex-wrap: none;
 `),a("button-placeholder",`
 width: calc(1.75 * var(--n-rail-height));
 height: var(--n-rail-height);
 `),X("base-loading",`
 position: absolute;
 top: 50%;
 left: 50%;
 transform: translateX(-50%) translateY(-50%);
 font-size: calc(var(--n-button-width) - 4px);
 color: var(--n-loading-color);
 transition: color .3s var(--n-bezier);
 `,[Y({left:"50%",top:"50%",originalTransform:"translateX(-50%) translateY(-50%)"})]),a("checked, unchecked",`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 box-sizing: border-box;
 position: absolute;
 white-space: nowrap;
 top: 0;
 bottom: 0;
 display: flex;
 align-items: center;
 line-height: 1;
 `),a("checked",`
 right: 0;
 padding-right: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),a("unchecked",`
 left: 0;
 justify-content: flex-end;
 padding-left: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),H("&:focus",[a("rail",`
 box-shadow: var(--n-box-shadow-focus);
 `)]),s("round",[a("rail","border-radius: calc(var(--n-rail-height) / 2);",[a("button","border-radius: calc(var(--n-button-height) / 2);")])]),q("disabled",[q("icon",[s("rubber-band",[s("pressed",[a("rail",[a("button","max-width: var(--n-button-width-pressed);")])]),a("rail",[H("&:active",[a("button","max-width: var(--n-button-width-pressed);")])]),s("active",[s("pressed",[a("rail",[a("button","left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));")])]),a("rail",[H("&:active",[a("button","left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));")])])])])])]),s("active",[a("rail",[a("button","left: calc(100% - var(--n-button-width) - var(--n-offset))")])]),a("rail",`
 overflow: hidden;
 height: var(--n-rail-height);
 min-width: var(--n-rail-width);
 border-radius: var(--n-rail-border-radius);
 cursor: pointer;
 position: relative;
 transition:
 opacity .3s var(--n-bezier),
 background .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-rail-color);
 `,[a("button-icon",`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 font-size: calc(var(--n-button-height) - 4px);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 display: flex;
 justify-content: center;
 align-items: center;
 line-height: 1;
 `,[Y()]),a("button",`
 align-items: center; 
 top: var(--n-offset);
 left: var(--n-offset);
 height: var(--n-button-height);
 width: var(--n-button-width-pressed);
 max-width: var(--n-button-width);
 border-radius: var(--n-button-border-radius);
 background-color: var(--n-button-color);
 box-shadow: var(--n-button-box-shadow);
 box-sizing: border-box;
 cursor: inherit;
 content: "";
 position: absolute;
 transition:
 background-color .3s var(--n-bezier),
 left .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 max-width .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 `)]),s("active",[a("rail","background-color: var(--n-rail-color-active);")]),s("loading",[a("rail",`
 cursor: wait;
 `)]),s("disabled",[a("rail",`
 cursor: not-allowed;
 opacity: .5;
 `)])]);const Ve=["aria-checked","tabindex","onClick","onFocus","onBlur","onKeyup","onKeydown"],Fe={...Q.props,size:String,value:{type:[String,Number,Boolean],default:void 0},loading:Boolean,defaultValue:{type:[String,Number,Boolean],default:!1},disabled:{type:Boolean,default:void 0},round:{type:Boolean,default:!0},"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array],checkedValue:{type:[String,Number,Boolean],default:!0},uncheckedValue:{type:[String,Number,Boolean],default:!1},railStyle:Function,rubberBand:{type:Boolean,default:!0},spinProps:Object,onChange:[Function,Array]};let $;var De=we({name:"Switch",props:Fe,slots:Object,setup(e){$===void 0&&(typeof CSS<"u"?typeof CSS.supports<"u"?$=CSS.supports("width","max(1px)"):$=!1:$=!0);const{mergedClsPrefixRef:c,inlineThemeDisabled:f,mergedComponentPropsRef:n}=pe(e),S=Q("Switch","-switch",ze,$e,e,c),v=xe(e,{mergedSize(t){if(e.size!==void 0)return e.size;if(t)return t.mergedSize.value;const w=n?.value?.Switch?.size;return w||"medium"}}),{mergedSizeRef:C,mergedDisabledRef:g}=v,B=U(e.defaultValue),z=ke(e,"value"),m=Re(z,B),V=D(()=>m.value===e.checkedValue),o=U(!1),r=U(!1),R=D(()=>{const{railStyle:t}=e;if(t)return t({focused:r.value,checked:V.value})});function F(t){const{"onUpdate:value":w,onChange:P,onUpdateValue:T}=e,{nTriggerFormInput:K,nTriggerFormChange:W}=v;w&&A(w,t),T&&A(T,t),P&&A(P,t),B.value=t,K(),W()}function Z(){const{nTriggerFormFocus:t}=v;t()}function ee(){const{nTriggerFormBlur:t}=v;t()}function te(){e.loading||g.value||(m.value!==e.checkedValue?F(e.checkedValue):F(e.uncheckedValue))}function ae(){r.value=!0,Z()}function oe(){r.value=!1,ee(),o.value=!1}function ie(t){e.loading||g.value||t.key===" "&&(m.value!==e.checkedValue?F(e.checkedValue):F(e.uncheckedValue),o.value=!1)}function ne(t){e.loading||g.value||t.key===" "&&(t.preventDefault(),o.value=!0)}const I=D(()=>{const{value:t}=C,{self:{opacityDisabled:w,railColor:P,railColorActive:T,buttonBoxShadow:K,buttonColor:W,boxShadowFocus:re,loadingColor:le,textColor:se,iconColor:de,[x("buttonHeight",t)]:u,[x("buttonWidth",t)]:ce,[x("buttonWidthPressed",t)]:ue,[x("railHeight",t)]:h,[x("railWidth",t)]:_,[x("railBorderRadius",t)]:he,[x("buttonBorderRadius",t)]:be},common:{cubicBezierEaseInOut:fe}}=S.value;let M,N,j;return $?(M=`calc((${h} - ${u}) / 2)`,N=`max(${h}, ${u})`,j=`max(${_}, calc(${_} + ${u} - ${h}))`):(M=E((d(h)-d(u))/2),N=E(Math.max(d(h),d(u))),j=d(h)>d(u)?_:E(d(_)+d(u)-d(h))),{"--n-bezier":fe,"--n-button-border-radius":be,"--n-button-box-shadow":K,"--n-button-color":W,"--n-button-width":ce,"--n-button-width-pressed":ue,"--n-button-height":u,"--n-height":N,"--n-offset":M,"--n-opacity-disabled":w,"--n-rail-border-radius":he,"--n-rail-color":P,"--n-rail-color-active":T,"--n-rail-height":h,"--n-rail-width":_,"--n-width":j,"--n-box-shadow-focus":re,"--n-loading-color":le,"--n-text-color":se,"--n-icon-color":de}}),L=f?ye("switch",D(()=>C.value[0]),I,e):void 0;return{handleClick:te,handleBlur:oe,handleFocus:ae,handleKeyup:ie,handleKeydown:ne,mergedRailStyle:R,pressed:o,mergedClsPrefix:c,mergedValue:m,checked:V,mergedDisabled:g,cssVars:f?void 0:I,themeClass:L?.themeClass,onRender:L?.onRender}},render(){const{mergedClsPrefix:e,mergedDisabled:c,checked:f,mergedRailStyle:n,onRender:S,$slots:v}=this;S?.();const{checked:C,unchecked:g,icon:B,"checked-icon":z,"unchecked-icon":m}=v,V=!(O(B)&&O(z)&&O(m));return b(),y("div",{role:"switch","aria-checked":f,class:i([`${e}-switch`,this.themeClass,V&&`${e}-switch--icon`,f&&`${e}-switch--active`,c&&`${e}-switch--disabled`,this.round&&`${e}-switch--round`,this.loading&&`${e}-switch--loading`,this.pressed&&`${e}-switch--pressed`,this.rubberBand&&`${e}-switch--rubber-band`]),tabindex:this.mergedDisabled?void 0:0,style:J(this.cssVars),onClick:this.handleClick,onFocus:this.handleFocus,onBlur:this.handleBlur,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},[k("div",{class:i(`${e}-switch__rail`),"aria-hidden":"true",style:J(n)},[l(()=>p(C,o=>p(g,r=>o||r?(b(),y("div",{key:4,"aria-hidden":!0,class:i(`${e}-switch__children-placeholder`)},[k("div",{class:i(`${e}-switch__rail-placeholder`)},[k("div",{class:i(`${e}-switch__button-placeholder`)},null,2),l(()=>o)],2),k("div",{class:i(`${e}-switch__rail-placeholder`)},[k("div",{class:i(`${e}-switch__button-placeholder`)},null,2),l(()=>r)],2)],2)):null))),k("div",{class:i(`${e}-switch__button`)},[l(()=>p(B,o=>p(z,r=>p(m,R=>(b(),G(Se,null,{default:()=>this.loading?(b(),G(Ce,Be({key:"loading",clsPrefix:e,strokeWidth:20},this.spinProps),null,16,["clsPrefix"])):this.checked&&(r||o)?(b(),y("div",{class:i(`${e}-switch__button-icon`),key:r?"checked-icon":"icon"},[l(()=>r||o)],2)):!this.checked&&(R||o)?(b(),y("div",{class:i(`${e}-switch__button-icon`),key:R?"unchecked-icon":"icon"},[l(()=>R||o)],2)):null},1024)))))),l(()=>p(C,o=>o&&(b(),y("div",{key:"checked",class:i(`${e}-switch__checked`)},[l(()=>o)],2)))),l(()=>p(g,o=>o&&(b(),y("div",{key:"unchecked",class:i(`${e}-switch__unchecked`)},[l(()=>o)],2))))],2)],6)],46,Ve)}});export{De as S};
