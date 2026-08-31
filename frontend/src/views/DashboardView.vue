<script setup lang="ts">
import {onMounted,onUnmounted,ref} from 'vue'
import {useRouter} from 'vue-router'
import {get} from '../api/client'
import CapitalStatusPanel from '../components/dashboard/CapitalStatusPanel.vue'
import FlightNetworkMap from '../components/dashboard/FlightNetworkMap.vue'
import type {Dashboard} from '../types'

const data=ref<Dashboard|null>(null),error=ref(''),loading=ref(false)
const selectedRouteId=ref<number|null>(null)
const router=useRouter()
let refreshTimer:number|undefined

async function load(){if(loading.value)return;loading.value=true;error.value='';try{data.value=await get<Dashboard>('/api/dashboard')}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
function onVisibilityChange(){if(document.visibilityState==='visible')load()}

onMounted(()=>{document.body.classList.add('dashboard-lock');load();refreshTimer=window.setInterval(()=>{if(document.visibilityState==='visible')load()},15000);document.addEventListener('visibilitychange',onVisibilityChange)})
onUnmounted(()=>{document.body.classList.remove('dashboard-lock');if(refreshTimer!==undefined)window.clearInterval(refreshTimer);document.removeEventListener('visibilitychange',onVisibilityChange)})
</script>

<template>
  <div class="page dashboard-page">
    <p v-if="error" class="error-banner">更新失败：{{error}}。已保留最近一次态势。</p>

    <template v-if="data">
      <section class="dashboard-core">
        <CapitalStatusPanel :capital="data.capital" :routes="data.routes" :available-slots="data.counts.available_slots"/>
        <FlightNetworkMap :airports="data.airports" :routes="data.routes" :selected-route-id="selectedRouteId" @select-route="selectedRouteId=$event" @open-manifest="router.push({path:'/voyages',query:{voyage:$event}})"/>
      </section>
    </template>
    <div v-else-if="loading" class="loading">正在建立财富航线态势…</div>
  </div>
</template>

<style scoped>
.dashboard-page{width:100%;max-width:none;height:100dvh;display:flex;flex-direction:column;padding:18px 22px;overflow:hidden}.dashboard-core{min-height:0;display:grid;flex:1;grid-template-columns:310px minmax(0,1fr);gap:12px}.dashboard-core>:deep(.flight-monitor){height:100%;margin:0}@media(max-width:1320px){.dashboard-core{grid-template-columns:290px minmax(0,1fr)}}@media(max-width:1120px){.dashboard-core{grid-template-columns:270px minmax(0,1fr)}}@media(max-width:1050px){.dashboard-core{display:block}.dashboard-core>:deep(.flight-monitor){height:100%}}@media(max-width:760px){.dashboard-page{height:auto;min-height:calc(100dvh - 96px);padding:14px;overflow:visible}.dashboard-core{height:auto;min-height:0}}
</style>
<style>
body.dashboard-lock{overflow:hidden}@media(max-width:760px){body.dashboard-lock{overflow:auto}}
</style>
