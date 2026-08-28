import "./globals.css";
import Link from "next/link";

export const metadata = { title: "Nanoni Admin", description: "Nanoni control plane" };

const links = [
  ["/", "Dashboard"],
  ["/content", "Conteúdo"],
  ["/catalog", "Catálogo"],
  ["/commerce", "Vendas/Acessos"],
  ["/operations", "Operação"],
];

export default function RootLayout({children}:{children:React.ReactNode}){
  return <html lang="pt-BR"><body><div className="shell">
    <aside className="sidebar"><div className="brand">NANONI</div><nav className="nav">{links.map(([href,label])=><Link key={href} href={href}>{label}</Link>)}</nav></aside>
    <main className="main">{children}</main>
  </div></body></html>
}
