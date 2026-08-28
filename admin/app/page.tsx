import {api} from "../lib/api";
type Summary={niches:number;communities:number;active_products:number;pending_content:number;queued_publications:number;open_alerts:number;paid_orders:number;active_entitlements:number;revenue_confirmed:string};
export default async function Dashboard(){
 const s=await api<Summary>("/api/v1/dashboard/summary");
 const metrics=[
   ["Receita confirmada", s?`R$ ${Number(s.revenue_confirmed).toFixed(2)}`:"—"],
   ["Pedidos pagos",s?.paid_orders??"—"],["Acessos ativos",s?.active_entitlements??"—"],["Conteúdos aguardando",s?.pending_content??"—"],
   ["Comunidades",s?.communities??"—"],["Produtos ativos",s?.active_products??"—"],["Publicações na fila",s?.queued_publications??"—"],["Alertas abertos",s?.open_alerts??"—"]
 ];
 return <><div className="eyebrow">Control plane</div><h1 className="title">Dashboard</h1>{!s&&<div className="card warning">Backend offline ou token inválido. O painel continua carregando sem esconder o problema.</div>}<div className="grid">{metrics.map(([label,value])=><div className="card" key={label}><h3>{label}</h3><div className="metric">{value}</div></div>)}</div><section className="section card"><div className="row"><div><h2>Gate V1</h2><p className="muted">coletar → aprovar → publicar → pagamento → entitlement → acesso</p></div><span className="pill">fundação</span></div></section></>
}
