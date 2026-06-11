import { f as fallback } from './async-D55cHugf.js';
import { b as store_get, a as attr, f as attr_class, g as attr_style, i as stringify, s as slot, u as unsubscribe_stores, d as bind_props } from './index-6p4UEISu.js';
import { H as Hs } from './2-DRKHurlg.js';
import { t as tick, c as createEventDispatcher } from './index-server-CQz6EZl_.js';
import { F } from './Walkthrough.svelte_svelte_type_style_lang-CEJkYHRG.js';
import { y } from './Index.svelte_svelte_type_style_lang-DavxexVt.js';
import { g as getContext } from './context-CBkBucIx.js';
import './escaping-CBnpiEl5.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './index3-2ivdxlrV.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function N(d,e){d.component(o=>{var r;let m,i=fallback(e.elem_id,""),l=fallback(e.elem_classes,()=>[],true),s=e.label,c=fallback(e.id,()=>({}),true),_=e.visible,f=e.interactive,u=e.order,n=e.scale,h=e.component_id;const p=createEventDispatcher(),{register_tab:v,unregister_tab:g,selected_tab:x,selected_tab_index:k}=getContext(F);let b;function y$1(a,B){return a=JSON.parse(a),v(a,B)}m=JSON.stringify({label:s,id:c,elem_id:i,visible:_,interactive:f,scale:n,component_id:h}),b=y$1(m,u),store_get(r??={},"$selected_tab_index",k)===b&&tick().then(()=>p("select",{value:s,index:b})),o.push(`<div${attr("id",i)}${attr_class(`tabitem ${stringify(l.join(" "))}`,"svelte-dmtrd3",{"grow-children":n>=1})} role="tabpanel"${attr_style("",{display:store_get(r??={},"$selected_tab",x)===c&&_!==false?"flex":"none","flex-grow":n})}>`),y(o,{scale:n>=1?n:null,children:a=>{a.push("<!--[-->"),slot(a,e,"default",{}),a.push("<!--]-->");},$$slots:{default:true}}),o.push("<!----></div>"),r&&unsubscribe_stores(r),bind_props(e,{elem_id:i,elem_classes:l,label:s,id:c,visible:_,interactive:f,order:u,scale:n,component_id:h});});}function q(d,e){d.component(o=>{let{$$slots:r,$$events:m,...i}=e;const l=new Hs(i);N(o,{elem_id:l.shared.elem_id,elem_classes:l.shared.elem_classes,label:l.shared.label,visible:l.shared.visible,interactive:l.shared.interactive,id:l.props.id,order:l.props.order,scale:l.props.scale,component_id:l.props.component_id,children:s=>{s.push("<!--[-->"),slot(s,e,"default",{}),s.push("<!--]-->");},$$slots:{default:true}});});}

export { N as BaseTabItem, q as default };
//# sourceMappingURL=Index37-Ipj8EpuU.js.map
