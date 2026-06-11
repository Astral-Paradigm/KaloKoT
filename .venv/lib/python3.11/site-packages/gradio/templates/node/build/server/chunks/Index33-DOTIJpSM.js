import './async-D55cHugf.js';
import { a as attr } from './index-6p4UEISu.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import { H as Hs } from './2-DRKHurlg.js';
import { q } from './Button-DLljsD6K.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Image-CUmtsNQ5.js';

function B(a,o){a.component(t=>{let{elem_id:d="",elem_classes:u=[],visible:n=true,variant:i="secondary",size:c="lg",value:e,icon:m,disabled:f=false,scale:_=null,min_width:v=void 0,on_click:b,children:h}=o;function w(){if(b?.(),!e?.url)return;let s;if(!e.orig_name&&e.url){const r=e.url.split("/");s=r[r.length-1],s=s.split("?")[0].split("#")[0];}else s=e.orig_name;const l=document.createElement("a");l.href=e.url,l.download=s||"file",document.body.appendChild(l),l.click(),document.body.removeChild(l);}q(t,{size:c,variant:i,elem_id:d,elem_classes:u,visible:n,onclick:w,scale:_,min_width:v,disabled:f,children:s=>{m?(s.push("<!--[-->"),s.push(`<img class="button-icon svelte-4ac0fl"${attr("src",m.url)}${attr("alt",`${e} icon`)}/>`)):s.push("<!--[!-->"),s.push("<!--]--> "),h?(s.push("<!--[-->"),h(s),s.push("<!---->")):s.push("<!--[!-->"),s.push("<!--]-->");}});});}function G(a,o){a.component(t=>{const{$$slots:d,$$events:u,...n}=o,i=new Hs(n);B(t,{value:i.props.value,variant:i.props.variant,elem_id:i.shared.elem_id,elem_classes:i.shared.elem_classes,size:i.props.size,scale:i.shared.scale,icon:i.props.icon,min_width:i.shared.min_width,visible:i.shared.visible,disabled:!i.shared.interactive,on_click:()=>i.dispatch("click"),children:c=>{c.push(`<!---->${escape_html(i.shared.label??"")}`);}});});}

export { B as BaseButton, G as default };
//# sourceMappingURL=Index33-DOTIJpSM.js.map
