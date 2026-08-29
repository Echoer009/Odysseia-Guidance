import{I as h,l as e,P as H,m as P,H as L,aM as q,aN as J,d as N,n as F,aj as K,a as i,c as a,r as s,p as u,q as n,J as _,y as W,D as Q,E as M,aO as U,aP as X,ap as j}from"./index-BRnOnDbo.js";import{u as Y,g as Z}from"./Space-BRkhH41f.js";function V(t,m="default",c=[]){const{children:d}=t;if(d!==null&&typeof d=="object"&&!Array.isArray(d)){const l=d[m];if(typeof l=="function")return l()}return c}var ee=h([e("descriptions",{fontSize:"var(--n-font-size)"},[e("descriptions-separator",`
 display: inline-block;
 margin: 0 8px 0 2px;
 `),e("descriptions-table-wrapper",[e("descriptions-table",[e("descriptions-table-row",[e("descriptions-table-header",{padding:"var(--n-th-padding)"}),e("descriptions-table-content",{padding:"var(--n-td-padding)"})])])]),H("bordered",[e("descriptions-table-wrapper",[e("descriptions-table",[e("descriptions-table-row",[h("&:last-child",[e("descriptions-table-content",{paddingBottom:0})])])])])]),P("left-label-placement",[e("descriptions-table-content",[h("> *",{verticalAlign:"top"})])]),P("left-label-align",[h("th",{textAlign:"left"})]),P("center-label-align",[h("th",{textAlign:"center"})]),P("right-label-align",[h("th",{textAlign:"right"})]),P("bordered",[e("descriptions-table-wrapper",`
 border-radius: var(--n-border-radius);
 overflow: hidden;
 background: var(--n-merged-td-color);
 border: 1px solid var(--n-merged-border-color);
 `,[e("descriptions-table",[e("descriptions-table-row",[h("&:not(:last-child)",[e("descriptions-table-content",{borderBottom:"1px solid var(--n-merged-border-color)"}),e("descriptions-table-header",{borderBottom:"1px solid var(--n-merged-border-color)"})]),e("descriptions-table-header",`
 font-weight: 400;
 background-clip: padding-box;
 background-color: var(--n-merged-th-color);
 `,[h("&:not(:last-child)",{borderRight:"1px solid var(--n-merged-border-color)"})]),e("descriptions-table-content",[h("&:not(:last-child)",{borderRight:"1px solid var(--n-merged-border-color)"})])])])])]),e("descriptions-header",`
 font-weight: var(--n-th-font-weight);
 font-size: 18px;
 transition: color .3s var(--n-bezier);
 line-height: var(--n-line-height);
 margin-bottom: 16px;
 color: var(--n-title-text-color);
 `),e("descriptions-table-wrapper",`
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[e("descriptions-table",`
 width: 100%;
 border-collapse: separate;
 border-spacing: 0;
 box-sizing: border-box;
 `,[e("descriptions-table-row",`
 box-sizing: border-box;
 transition: border-color .3s var(--n-bezier);
 `,[e("descriptions-table-header",`
 font-weight: var(--n-th-font-weight);
 line-height: var(--n-line-height);
 display: table-cell;
 box-sizing: border-box;
 color: var(--n-th-text-color);
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),e("descriptions-table-content",`
 vertical-align: top;
 line-height: var(--n-line-height);
 display: table-cell;
 box-sizing: border-box;
 color: var(--n-td-text-color);
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[L("content",`
 transition: color .3s var(--n-bezier);
 display: inline-block;
 color: var(--n-td-text-color);
 `)]),L("label",`
 font-weight: var(--n-th-font-weight);
 transition: color .3s var(--n-bezier);
 display: inline-block;
 margin-right: 14px;
 color: var(--n-th-text-color);
 `)])])])]),e("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color);
 --n-merged-td-color: var(--n-td-color);
 --n-merged-border-color: var(--n-border-color);
 `),q(e("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color-modal);
 --n-merged-td-color: var(--n-td-color-modal);
 --n-merged-border-color: var(--n-border-color-modal);
 `)),J(e("descriptions-table-wrapper",`
 --n-merged-th-color: var(--n-th-color-popover);
 --n-merged-td-color: var(--n-td-color-popover);
 --n-merged-border-color: var(--n-border-color-popover);
 `))]);const oe="DESCRIPTION_ITEM_FLAG";function re(t){return typeof t=="object"&&t&&!Array.isArray(t)?t.type&&t.type.DESCRIPTION_ITEM_FLAG:!1}const te=["colspan"],ne=["colspan"],se=["colspan"],le=["colspan"],ie={...F.props,title:String,column:{type:Number,default:3},columns:Number,labelPlacement:{type:String,default:"top"},labelAlign:{type:String,default:"left"},separator:{type:String,default:":"},size:String,bordered:Boolean,labelClass:String,labelStyle:[Object,String],contentClass:String,contentStyle:[Object,String]};var pe=N({name:"Descriptions",props:ie,slots:Object,setup(t){const{mergedClsPrefixRef:m,inlineThemeDisabled:c,mergedComponentPropsRef:d}=W(t),l=M(()=>t.size||d?.value?.Descriptions?.size||"medium"),f=F("Descriptions","-descriptions",ee,X,t,m),R=M(()=>{const{bordered:p}=t,g=l.value,{common:{cubicBezierEaseInOut:T},self:{titleTextColor:r,thColor:I,thColorModal:B,thColorPopover:A,thTextColor:O,thFontWeight:o,tdTextColor:w,tdColor:E,tdColorModal:b,tdColorPopover:v,borderColor:C,borderColorModal:S,borderColorPopover:y,borderRadius:x,lineHeight:z,[j("fontSize",g)]:$,[j(p?"thPaddingBordered":"thPadding",g)]:D,[j(p?"tdPaddingBordered":"tdPadding",g)]:G}}=f.value;return{"--n-title-text-color":r,"--n-th-padding":D,"--n-td-padding":G,"--n-font-size":$,"--n-bezier":T,"--n-th-font-weight":o,"--n-line-height":z,"--n-th-text-color":O,"--n-td-text-color":w,"--n-th-color":I,"--n-th-color-modal":B,"--n-th-color-popover":A,"--n-td-color":E,"--n-td-color-modal":b,"--n-td-color-popover":v,"--n-border-radius":x,"--n-border-color":C,"--n-border-color-modal":S,"--n-border-color-popover":y}}),k=c?Q("descriptions",M(()=>{let p="";const{bordered:g}=t;return g&&(p+="a"),p+=l.value[0],p}),R,t):void 0;return{mergedClsPrefix:m,cssVars:c?void 0:R,themeClass:k?.themeClass,onRender:k?.onRender,compitableColumn:Y(t,["columns","column"]),inlineThemeDisabled:c,mergedSize:l}},render(){const t=this.$slots.default,m=t?K(t()):[];m.length;const{contentClass:c,labelClass:d,compitableColumn:l,labelPlacement:f,labelAlign:R,mergedSize:k,bordered:p,title:g,cssVars:T,mergedClsPrefix:r,separator:I,onRender:B}=this;B?.();const A=m.filter(o=>re(o)),O=A.reduce((o,w,E)=>{const b=w.props||{},v=A.length-1===E,C=["label"in b?b.label:V(w,"label")],S=[V(w)],y=b.span||1,x=o.span;o.span+=y;const z=b.labelStyle||b["label-style"]||this.labelStyle,$=b.contentStyle||b["content-style"]||this.contentStyle;if(f==="left")p?o.row.push((i(),a("th",{key:1,class:n([`${r}-descriptions-table-header`,d]),colspan:1,style:u(z)},[s(()=>C)],6)),(i(),a("td",{key:2,class:n([`${r}-descriptions-table-content`,c]),colspan:v?(l-x)*2+1:y*2-1,style:u($)},[s(()=>S)],14,te))):o.row.push((i(),a("td",{key:3,class:n(`${r}-descriptions-table-content`),colspan:v?(l-x)*2:y*2},[_("span",{class:n([`${r}-descriptions-table-content__label`,d]),style:u(z)},[s(()=>[...C,I&&(i(),a("span",{key:4,class:n(`${r}-descriptions-separator`)},[s(()=>I)],2))])],6),_("span",{class:n([`${r}-descriptions-table-content__content`,c]),style:u($)},[s(()=>S)],6)],10,ne)));else{const D=v?(l-x)*2:y*2;o.row.push((i(),a("th",{key:5,class:n([`${r}-descriptions-table-header`,d]),colspan:D,style:u(z)},[s(()=>C)],14,se))),o.secondRow.push((i(),a("td",{key:6,class:n([`${r}-descriptions-table-content`,c]),colspan:D,style:u($)},[s(()=>S)],14,le)))}return(o.span>=l||v)&&(o.span=0,o.row.length&&(o.rows.push(o.row),o.row=[]),f!=="left"&&o.secondRow.length&&(o.rows.push(o.secondRow),o.secondRow=[])),o},{span:0,row:[],secondRow:[],rows:[]}).rows.map(o=>(i(),a("tr",{class:n(`${r}-descriptions-table-row`)},[s(()=>o)],2)));return i(),a("div",{style:u(T),class:n([`${r}-descriptions`,this.themeClass,`${r}-descriptions--${f}-label-placement`,`${r}-descriptions--${R}-label-align`,`${r}-descriptions--${k}-size`,p&&`${r}-descriptions--bordered`])},[g||this.$slots.header?(i(),a("div",{key:0,class:n(`${r}-descriptions-header`)},[s(()=>g||Z(this,"header"))],2)):s(()=>null),_("div",{class:n(`${r}-descriptions-table-wrapper`)},[_("table",{class:n(`${r}-descriptions-table`)},[_("tbody",null,[s(()=>f==="top"&&(i(),a("tr",{class:n(`${r}-descriptions-table-row`),style:{visibility:"collapse"}},[s(()=>U(l*2,(i(),a("td"))))],2))),s(()=>O)])],2)],2)],6)}});const ae={label:String,span:{type:Number,default:1},labelClass:String,labelStyle:[Object,String],contentClass:String,contentStyle:[Object,String]};var be=N({name:"DescriptionsItem",[oe]:!0,props:ae,slots:Object,render(){return null}});export{pe as D,be as a};
