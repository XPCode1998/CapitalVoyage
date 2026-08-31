export interface ApiEnvelope<T>{data:T|null;error:{code:string;message:string}|null}

export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}})
  const body=(await response.json()) as ApiEnvelope<T>
  if(!response.ok||body.error) throw new Error(body.error?.message||`请求失败 (${response.status})`)
  return body.data as T
}

export const get=<T>(path:string)=>api<T>(path)
export const post=<T>(path:string,data?:unknown)=>api<T>(path,{method:'POST',body:data===undefined?undefined:JSON.stringify(data)})
export const patch=<T>(path:string,data:unknown)=>api<T>(path,{method:'PATCH',body:JSON.stringify(data)})
export const put=<T>(path:string,data:unknown)=>api<T>(path,{method:'PUT',body:JSON.stringify(data)})

