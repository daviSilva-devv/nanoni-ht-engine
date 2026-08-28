const base = process.env.NANONI_BACKEND_URL ?? "http://127.0.0.1:8010";
const token = process.env.NANONI_ADMIN_TOKEN ?? "change-me-local";

export async function api<T>(path:string):Promise<T|null>{
  try{
    const response = await fetch(`${base}${path}`, {headers:{"X-Admin-Token":token}, cache:"no-store"});
    if(!response.ok) return null;
    return await response.json() as T;
  }catch{return null;}
}
