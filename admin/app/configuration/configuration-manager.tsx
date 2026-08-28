"use client";

import {FormEvent, useCallback, useEffect, useMemo, useState} from "react";

type Row = Record<string, any> & {id:string};
type Field = {
  key:string; label:string; kind?:"text"|"number"|"money"|"boolean"|"select"|"multi"|"json"|"textarea";
  required?:boolean; options?:string[]; resource?:string; placeholder?:string;
};
type Resource = {
  key:string; label:string; singular:string; fields:Field[]; activeKey?:string;
  activeValue?:unknown; inactiveValue?:unknown;
};

const resources:Resource[]=[
  {key:"niches",label:"Nichos",singular:"Nicho",activeKey:"active",fields:[
    {key:"name",label:"Nome",required:true},{key:"slug",label:"Slug",required:true},{key:"description",label:"Descrição",kind:"textarea"},{key:"sort_order",label:"Ordem",kind:"number"},{key:"active",label:"Ativo",kind:"boolean"}]},
  {key:"microniches",label:"Micronichos",singular:"Micronicho",activeKey:"active",fields:[
    {key:"niche_id",label:"Nicho",kind:"select",resource:"niches",required:true},{key:"name",label:"Nome",required:true},{key:"slug",label:"Slug",required:true},{key:"description",label:"Descrição",kind:"textarea"},{key:"sort_order",label:"Ordem",kind:"number"},{key:"active",label:"Ativo",kind:"boolean"}]},
  {key:"communities",label:"Comunidades",singular:"Comunidade",activeKey:"active",fields:[
    {key:"niche_id",label:"Nicho",kind:"select",resource:"niches",required:true},{key:"name",label:"Nome",required:true},{key:"slug",label:"Slug",required:true},{key:"description",label:"Descrição",kind:"textarea"},{key:"active",label:"Ativa",kind:"boolean"}]},
  {key:"community-versions",label:"Versões",singular:"Versão",activeKey:"active_for_sale",fields:[
    {key:"community_id",label:"Comunidade",kind:"select",resource:"communities",required:true},{key:"version",label:"Número",kind:"number",required:true},{key:"name",label:"Nome",required:true},{key:"promise_snapshot",label:"Promessa/benefícios (JSON)",kind:"json"},{key:"microniche_ids",label:"Micronichos incluídos",kind:"multi",resource:"microniches"},{key:"active_for_sale",label:"Disponível para venda",kind:"boolean"}]},
  {key:"destinations",label:"Destinos",singular:"Destino",activeKey:"status",activeValue:"ACTIVE",inactiveValue:"OFFLINE",fields:[
    {key:"community_id",label:"Comunidade",kind:"select",resource:"communities"},{key:"name",label:"Nome",required:true},{key:"destination_type",label:"Tipo",kind:"select",options:["FREE_CHANNEL","VIP_FORUM","VAULT_CHANNEL","ADMIN_ALERT_CHAT"],required:true},{key:"telegram_chat_id",label:"Chat ID",required:true},{key:"username",label:"Username"},{key:"status",label:"Status",kind:"select",options:["ACTIVE","DEGRADED","OFFLINE"]},{key:"protected_content",label:"Proteger conteúdo",kind:"boolean"}]},
  {key:"topics",label:"Tópicos",singular:"Tópico",activeKey:"active",fields:[
    {key:"destination_id",label:"Destino",kind:"select",resource:"destinations",required:true},{key:"microniche_id",label:"Micronicho (somente conteúdo)",kind:"select",resource:"microniches"},{key:"name",label:"Nome",required:true},{key:"role",label:"Finalidade",kind:"select",options:["CONTENT","GENERAL","REQUESTS"],required:true},{key:"message_thread_id",label:"Thread ID",kind:"number",required:true},{key:"active",label:"Ativo",kind:"boolean"}]},
  {key:"products",label:"Produtos",singular:"Produto",activeKey:"active",fields:[
    {key:"community_version_id",label:"Versão",kind:"select",resource:"community-versions",required:true},{key:"name",label:"Nome",required:true},{key:"slug",label:"Slug",required:true},{key:"description",label:"Descrição",kind:"textarea"},{key:"active",label:"Ativo",kind:"boolean"}]},
  {key:"price-plans",label:"Planos",singular:"Plano",activeKey:"active",fields:[
    {key:"product_id",label:"Produto",kind:"select",resource:"products",required:true},{key:"kind",label:"Tipo",kind:"select",options:["WEEKLY","MONTHLY","LIFETIME","CUSTOM"],required:true},{key:"amount",label:"Valor",kind:"money",required:true},{key:"currency",label:"Moeda",placeholder:"BRL"},{key:"duration_days",label:"Duração em dias",kind:"number"},{key:"lifetime",label:"Lifetime",kind:"boolean"},{key:"featured",label:"Destaque",kind:"boolean"},{key:"sort_order",label:"Ordem",kind:"number"},{key:"active",label:"Ativo",kind:"boolean"}]},
  {key:"offers",label:"Ofertas",singular:"Oferta",activeKey:"active",fields:[
    {key:"name",label:"Nome",required:true},{key:"kind",label:"Tipo",kind:"select",options:["DISCOUNT","ADD_ON","BUNDLE","UPGRADE","WINBACK"],required:true},{key:"products",label:"Produtos relacionados",kind:"multi",resource:"products"},{key:"conditions",label:"Condições (JSON)",kind:"json",placeholder:'[{"condition_type":"NEW_CUSTOMER","config":{}}]'},{key:"config",label:"Configuração (JSON)",kind:"json"},{key:"starts_at",label:"Início (ISO)"},{key:"ends_at",label:"Fim (ISO)"},{key:"active",label:"Ativa",kind:"boolean"}]},
  {key:"copy-slots",label:"Slots de copy",singular:"Slot",activeKey:"active",fields:[
    {key:"key",label:"Chave/contexto",required:true},{key:"description",label:"Descrição de uso",kind:"textarea"},{key:"active",label:"Ativo",kind:"boolean"}]},
  {key:"copy-variants",label:"Variantes de copy",singular:"Variante",activeKey:"active",fields:[
    {key:"slot_id",label:"Slot",kind:"select",resource:"copy-slots",required:true},{key:"product_id",label:"Produto opcional",kind:"select",resource:"products"},{key:"text",label:"Texto livre",kind:"textarea",required:true},{key:"weight",label:"Peso",kind:"number"},{key:"valid_from",label:"Válida desde (ISO)"},{key:"valid_to",label:"Válida até (ISO)"},{key:"active",label:"Ativa",kind:"boolean"}]},
];

const defaults=(resource:Resource)=>Object.fromEntries(resource.fields.map(field=>[
  field.key, field.kind==="boolean" ? true : field.kind==="json" ? (field.key==="conditions"?"[]":"{}") : field.kind==="multi" ? [] : ""
]));

async function request(path:string, init?:RequestInit){
  const response=await fetch(`/api/admin-config/${path}`,{...init,headers:{"Content-Type":"application/json",...(init?.headers??{})}});
  if(!response.ok){let detail=`Erro ${response.status}`;try{const body=await response.json();detail=body.detail??detail}catch{}throw new Error(typeof detail==="string"?detail:JSON.stringify(detail));}
  return response.status===204?null:response.json();
}

export default function ConfigurationManager(){
  const [selected,setSelected]=useState(resources[0].key);
  const [rows,setRows]=useState<Record<string,Row[]>>({});
  const [form,setForm]=useState<Record<string,any>>(defaults(resources[0]));
  const [editing,setEditing]=useState<string|null>(null);
  const [message,setMessage]=useState<{type:"ok"|"error";text:string}|null>(null);
  const [busy,setBusy]=useState(false);
  const resource=useMemo(()=>resources.find(item=>item.key===selected)!,[selected]);

  const load=useCallback(async()=>{
    const entries=await Promise.all(resources.map(async item=>[item.key,await request(item.key)] as const));
    setRows(Object.fromEntries(entries));
  },[]);
  useEffect(()=>{load().catch(error=>setMessage({type:"error",text:error.message}))},[load]);
  useEffect(()=>{setForm(defaults(resource));setEditing(null);setMessage(null)},[resource]);

  const labelFor=(resourceKey:string,id:any)=>{
    const item=(rows[resourceKey]??[]).find(row=>row.id===id);
    return item?.name??item?.key??id;
  };
  const display=(field:Field,value:any)=>{
    if(field.resource&&Array.isArray(value))return value.map(id=>labelFor(field.resource!,typeof id==="string"?id:id.product_id)).join(", ");
    if(field.resource&&value)return labelFor(field.resource,value);
    if(typeof value==="boolean")return value?"Sim":"Não";
    if(value&&typeof value==="object")return JSON.stringify(value);
    return value??"—";
  };
  const payload=()=>{
    const result:Record<string,any>={};
    for(const field of resource.fields){let value=form[field.key];if(value===""||value===undefined){if(editing&&!field.required&&value==="")result[field.key]=null;continue;}
      if(field.kind==="number")value=Number(value);
      if(field.kind==="json")value=typeof value==="string"?JSON.parse(value||(field.key==="conditions"?"[]":"{}")):value;
      if(field.kind==="multi"&&resource.key==="offers"&&field.key==="products")value=(value as string[]).map(product_id=>({product_id,role:"TARGET"}));
      result[field.key]=value;
    }
    if(resource.key==="price-plans"&&result.lifetime)result.duration_days=null;
    return result;
  };
  const submit=async(event:FormEvent)=>{event.preventDefault();setBusy(true);setMessage(null);try{
    await request(editing?`${resource.key}/${editing}`:resource.key,{method:editing?"PATCH":"POST",body:JSON.stringify(payload())});
    await load();setForm(defaults(resource));setEditing(null);setMessage({type:"ok",text:`${resource.singular} salvo com sucesso.`});
  }catch(error){setMessage({type:"error",text:(error as Error).message})}finally{setBusy(false)}};
  const edit=(row:Row)=>{const next=defaults(resource);for(const field of resource.fields){let value=row[field.key];
    if(resource.key==="offers"&&field.key==="products")value=(row.products??[]).map((item:any)=>item.product_id);
    if(field.kind==="json")value=JSON.stringify(value??(field.key==="conditions"?[]:{}),null,2);
    next[field.key]=value??(field.kind==="multi"?[]:"");}setForm(next);setEditing(row.id);window.scrollTo({top:0,behavior:"smooth"});};
  const remove=async(row:Row)=>{if(!confirm(`Remover ${resource.singular.toLowerCase()}?`))return;try{await request(`${resource.key}/${row.id}`,{method:"DELETE"});await load();setMessage({type:"ok",text:"Removido com sucesso."})}catch(error){setMessage({type:"error",text:(error as Error).message})}};
  const toggle=async(row:Row)=>{if(!resource.activeKey)return;const key=resource.activeKey;const active=resource.activeValue??true;const inactive=resource.inactiveValue??false;try{await request(`${resource.key}/${row.id}`,{method:"PATCH",body:JSON.stringify({[key]:row[key]===active?inactive:active})});await load()}catch(error){setMessage({type:"error",text:(error as Error).message})}};

  return <div className="config-layout"><nav className="config-nav">{resources.map(item=><button className={selected===item.key?"active":""} key={item.key} onClick={()=>setSelected(item.key)}>{item.label}<span>{rows[item.key]?.length??0}</span></button>)}</nav><div className="config-workspace">
    <section className="card"><div className="row"><div><h2>{editing?`Editar ${resource.singular}`:`Novo ${resource.singular}`}</h2><p className="muted">Campos e relações são persistidos no banco.</p></div>{editing&&<button className="button secondary" onClick={()=>{setEditing(null);setForm(defaults(resource))}}>Cancelar edição</button>}</div>
      {message&&<div className={`notice ${message.type}`}>{message.text}</div>}
      <form className="admin-form" onSubmit={submit}>{resource.fields.map(field=><label key={field.key}><span>{field.label}{field.required?" *":""}</span>{field.kind==="boolean"?<input type="checkbox" checked={Boolean(form[field.key])} onChange={e=>setForm({...form,[field.key]:e.target.checked})}/>:field.kind==="select"?<select required={field.required} value={form[field.key]??""} onChange={e=>setForm({...form,[field.key]:e.target.value})}><option value="">Selecione</option>{(field.options??(rows[field.resource!]??[]).map(item=>item.id)).map(option=><option key={option} value={option}>{field.resource?labelFor(field.resource,option):option}</option>)}</select>:field.kind==="multi"?<select multiple value={form[field.key]??[]} onChange={e=>setForm({...form,[field.key]:Array.from(e.target.selectedOptions,option=>option.value)})}>{(rows[field.resource!]??[]).map(item=><option key={item.id} value={item.id}>{item.name??item.key}</option>)}</select>:field.kind==="textarea"||field.kind==="json"?<textarea required={field.required} rows={field.kind==="json"?5:3} placeholder={field.placeholder} value={form[field.key]??""} onChange={e=>setForm({...form,[field.key]:e.target.value})}/>:<input required={field.required} type={field.kind==="number"||field.kind==="money"?"number":"text"} step={field.kind==="money"?"0.01":"1"} placeholder={field.placeholder} value={form[field.key]??""} onChange={e=>setForm({...form,[field.key]:e.target.value})}/>}</label>)}<div className="form-actions"><button className="button primary" disabled={busy}>{busy?"Salvando...":editing?"Salvar alterações":"Criar"}</button></div></form>
    </section>
    <section className="card section"><div className="row"><h2>{resource.label}</h2><button className="button secondary" onClick={()=>load()}>Atualizar</button></div><div className="table-wrap"><table className="table"><thead><tr>{resource.fields.slice(0,5).map(field=><th key={field.key}>{field.label}</th>)}<th>Ações</th></tr></thead><tbody>{(rows[resource.key]??[]).map(row=><tr key={row.id}>{resource.fields.slice(0,5).map(field=><td key={field.key}>{display(field,row[field.key])}</td>)}<td className="actions"><button onClick={()=>edit(row)}>Editar</button>{resource.activeKey&&<button onClick={()=>toggle(row)}>Ativar/desativar</button>}<button className="danger" onClick={()=>remove(row)}>Remover</button></td></tr>)}</tbody></table>{!rows[resource.key]?.length&&<div className="empty">Nenhum registro.</div>}</div></section>
  </div></div>;
}
