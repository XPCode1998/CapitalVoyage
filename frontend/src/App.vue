<script setup lang="ts">
import {onBeforeUnmount,onMounted,ref} from 'vue'
import {BookOpenText,Landmark,PlaneTakeoff,Radar,Settings} from 'lucide-vue-next'
import {get} from './api/client'

const nav=[['/','01','态势预览','OVERVIEW',Radar],['/voyages','02','调度中心','DISPATCH',PlaneTakeoff],['/returns','03','返航中心','RETURNS',Landmark],['/history','04','钱途记录','LOGBOOK',BookOpenText]] as const
const mobileNav=[...nav,['/settings','05','设置','SETTINGS',Settings]] as const
const serviceState=ref<'checking'|'online'|'closed'|'stale'|'offline'>('checking')
let statusTimer:number|undefined

async function refreshServiceState(){
  if(!navigator.onLine){serviceState.value='offline';return}
  try{
    await get<{status:string}>('/api/health')
    const market=await get<{status:string;quote_status:string}>('/api/market/status')
    serviceState.value=market.status==='CLOSED'?'closed':market.quote_status==='FRESH'?'online':'stale'
  }catch{serviceState.value='offline'}
}
const serviceLabel=()=>({checking:'连接中',online:'行情在线',closed:'已休市',stale:'行情延迟',offline:'服务离线'}[serviceState.value])
function onConnectivityChange(){refreshServiceState()}
function onVisibilityChange(){if(document.visibilityState==='visible')refreshServiceState()}
onMounted(()=>{refreshServiceState();statusTimer=window.setInterval(refreshServiceState,30_000);window.addEventListener('online',onConnectivityChange);window.addEventListener('offline',onConnectivityChange);document.addEventListener('visibilitychange',onVisibilityChange)})
onBeforeUnmount(()=>{if(statusTimer!==undefined)window.clearInterval(statusTimer);window.removeEventListener('online',onConnectivityChange);window.removeEventListener('offline',onConnectivityChange);document.removeEventListener('visibilitychange',onVisibilityChange)})
</script>

<template>
  <div class="shell">
    <aside>
      <div class="brand"><img class="brand-mark" src="/brand/qian-tu-mark.svg" alt="钱途 Logo"/><div><strong>钱途</strong><span>CapitalVoyage</span></div></div>
      <nav aria-label="主导航"><RouterLink v-for="[path,index,label,en,Icon] in nav" :key="path" :to="path"><component :is="Icon" :size="21"/><span class="nav-copy"><i>{{index}}</i><b>{{label}}</b><small>{{en}}</small></span></RouterLink></nav>
      <RouterLink class="side-settings" to="/settings"><Settings :size="20"/><span><b>设置</b><small>SYSTEM SETTINGS</small></span></RouterLink>
    </aside>
    <main>
      <header class="mobile-topbar">
        <div class="mobile-brand"><img src="/brand/qian-tu-mark.svg" alt=""/><span><b>{{$route.meta.title}}</b><small>CAPITALVOYAGE</small></span></div>
        <i :class="['mobile-live',serviceState]"><span></span>{{serviceLabel()}}</i>
      </header>
      <RouterView/>
    </main>
    <nav class="mobile-bottom-nav" aria-label="手机主导航">
      <RouterLink v-for="[path,index,label,en,Icon] in mobileNav" :key="path" :to="path">
        <component :is="Icon" :size="21"/><span>{{label}}</span><small>{{index}} · {{en}}</small>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.mobile-topbar,.mobile-bottom-nav{display:none}
@media(max-width:900px){
  .mobile-topbar{position:fixed;inset:0 0 auto;z-index:20;height:calc(58px + env(safe-area-inset-top));display:flex;align-items:flex-end;justify-content:space-between;padding:env(safe-area-inset-top) 16px 10px;background:rgba(255,255,255,.94);border-bottom:1px solid var(--line);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px)}
  .mobile-brand{display:flex;align-items:center;gap:10px;min-width:0}.mobile-brand img{width:31px;height:31px}.mobile-brand>span{min-width:0;display:grid;gap:1px}.mobile-brand b{overflow:hidden;color:#26384b;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.mobile-brand small{color:#8b9aaa;font-size:7px;font-weight:750;letter-spacing:.12em}
  .mobile-live{display:flex;align-items:center;gap:5px;padding-bottom:7px;color:#718091;font-size:9px;font-style:normal;font-weight:700;letter-spacing:.04em}.mobile-live span{width:6px;height:6px;border-radius:50%;background:var(--tower-green);box-shadow:0 0 0 3px rgba(30,158,99,.1)}.mobile-live.closed span{background:#8e9aa6;box-shadow:0 0 0 3px rgba(142,154,166,.12)}.mobile-live.stale span{background:var(--approach-amber);box-shadow:0 0 0 3px rgba(227,155,45,.12)}.mobile-live.offline span{background:var(--beacon-red);box-shadow:0 0 0 3px rgba(217,83,79,.12)}.mobile-live.checking span{background:#8e9aa6}
  .mobile-bottom-nav{position:fixed;inset:auto 0 0;z-index:25;width:100%;height:calc(64px + env(safe-area-inset-bottom));display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin:0;padding:5px 6px env(safe-area-inset-bottom);border-top:1px solid rgba(216,225,234,.9);background:rgba(255,255,255,.96);box-shadow:0 -8px 24px rgba(32,52,73,.07);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
  .mobile-bottom-nav a{position:relative;min-width:0;min-height:0;margin:0;padding:0;display:grid;place-content:center;justify-items:center;gap:2px;border:0;border-radius:10px;color:#8190a0;text-decoration:none}.mobile-bottom-nav a>span{font-size:10px;font-weight:650}.mobile-bottom-nav a>small{font-size:6px;font-weight:700;letter-spacing:.04em}.mobile-bottom-nav a.router-link-active,.mobile-bottom-nav a.returning{color:#2165b6;background:#f0f6fd}.mobile-bottom-nav a.router-link-active::before,.mobile-bottom-nav a.returning::before{content:"";position:absolute;inset:0 auto auto 50%;width:20px;height:3px;border:0;border-radius:0 0 3px 3px;background:#3b82d0;transform:translateX(-50%)}
}
</style>
