<script setup lang="ts">
import {onMounted,onUnmounted,ref} from 'vue'
import {useRouter} from 'vue-router'
import {get} from '../api/client'
import CapitalStatusPanel from '../components/dashboard/CapitalStatusPanel.vue'
import FlightNetworkMap from '../components/dashboard/FlightNetworkMap.vue'
import MobileCapitalSummary from '../components/dashboard/MobileCapitalSummary.vue'
import MarketStatusPanel from '../components/dashboard/MarketStatusPanel.vue'
import type {Dashboard,MarketStatus} from '../types'

const data=ref<Dashboard|null>(null),error=ref(''),loading=ref(false)
const marketStatus=ref<MarketStatus|null>(null)
const selectedRouteId=ref<number|null>(null)
const router=useRouter()
let refreshTimer:number|undefined

async function load(){if(loading.value)return;loading.value=true;error.value='';try{const [dashboard,status]=await Promise.all([get<Dashboard>('/api/dashboard'),get<MarketStatus>('/api/market/status')]);data.value=dashboard;marketStatus.value=status}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
function onVisibilityChange(){if(document.visibilityState==='visible')load()}

onMounted(()=>{document.body.classList.add('dashboard-lock');load();refreshTimer=window.setInterval(()=>{if(document.visibilityState==='visible')load()},15000);document.addEventListener('visibilitychange',onVisibilityChange)})
onUnmounted(()=>{document.body.classList.remove('dashboard-lock');if(refreshTimer!==undefined)window.clearInterval(refreshTimer);document.removeEventListener('visibilitychange',onVisibilityChange)})
</script>

<template>
  <div class="page dashboard-page">
    <p v-if="error" class="error-banner">更新失败：{{error}}。已保留最近一次态势。</p>

    <template v-if="data">
      <MarketStatusPanel v-if="marketStatus" :status="marketStatus"/>
      <MobileCapitalSummary :data="data"/>
      <section v-if="!data.routes.length" class="onboarding panel">
        <div><p class="section-kicker">开始使用</p><h1>建立第一笔 ETF 航次</h1><p>先确认资金和舱位，再记录券商的真实买入价格、份额和费用。系统会在可卖且达到目标收益时提醒你记录卖出。</p></div>
        <div class="onboarding-steps"><span><b>1</b>检查资金设置</span><span><b>2</b>记录实际买入</span><span><b>3</b>等待返航提醒</span></div>
        <div class="onboarding-actions"><button class="secondary" @click="router.push('/settings')">查看资金设置</button><button class="primary" @click="router.push('/voyages')">记录第一笔买入</button></div>
      </section>
      <section class="dashboard-core">
        <CapitalStatusPanel :capital="data.capital" :routes="data.routes" :available-slots="data.counts.available_slots"/>
        <FlightNetworkMap :airports="data.airports" :routes="data.routes" :selected-route-id="selectedRouteId" @select-route="selectedRouteId=$event" @open-manifest="router.push({path:'/voyages',query:{voyage:$event}})"/>
      </section>
    </template>
    <div v-else-if="loading" class="loading">正在建立财富航线态势…</div>
  </div>
</template>

<style scoped>
.dashboard-page{width:100%;max-width:none;height:100dvh;display:flex;flex-direction:column;padding:18px 22px;overflow:hidden}.dashboard-core{min-height:0;display:grid;flex:1;grid-template-columns:310px minmax(0,1fr);gap:12px}.dashboard-core>:deep(.flight-monitor){height:100%;margin:0}@media(max-width:1320px){.dashboard-core{grid-template-columns:290px minmax(0,1fr)}}@media(max-width:1120px){.dashboard-core{grid-template-columns:270px minmax(0,1fr)}}@media(max-width:1050px){.dashboard-core{display:block}.dashboard-core>:deep(.flight-monitor){height:100%}}@media(max-width:900px){.dashboard-page{height:auto;min-height:calc(100dvh - 96px);padding:14px;overflow:visible}.dashboard-core{height:auto;min-height:0}}
.onboarding{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(230px,.8fr) auto;align-items:center;gap:28px;margin-bottom:12px;padding:20px 22px}.onboarding h1{margin:5px 0 7px;font-size:22px}.onboarding p:not(.section-kicker){max-width:610px;margin:0;color:var(--ink-2);font-size:13px;line-height:1.6}.onboarding-steps{display:grid;gap:8px}.onboarding-steps span{display:flex;align-items:center;gap:8px;color:#526f8b;font-size:12px}.onboarding-steps b{width:21px;height:21px;display:grid;place-items:center;border-radius:50%;color:#2566ad;background:#e9f2fd;font-size:11px}.onboarding-actions{display:grid;gap:8px}.onboarding-actions button{white-space:nowrap}@media(max-width:1150px){.onboarding{grid-template-columns:1fr auto}.onboarding-steps{display:none}}@media(max-width:700px){.onboarding{grid-template-columns:1fr;gap:15px;padding:18px}.onboarding h1{font-size:20px}.onboarding-actions{grid-template-columns:1fr 1.25fr}.onboarding-actions button{min-height:44px}}
</style>
<style>
body.dashboard-lock{overflow:hidden}@media(max-width:900px){body.dashboard-lock{overflow:auto}}
</style>
