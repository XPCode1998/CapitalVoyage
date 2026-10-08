<script setup lang="ts">
import {computed} from 'vue'
import {CircleAlert,Clock3,RadioTower,ShieldCheck,WifiOff} from 'lucide-vue-next'
import type {MarketStatus} from '../../types'
import {dateTime} from '../../utils/format'

const props=defineProps<{status:MarketStatus}>()
const state=computed(()=>{
  if(props.status.status==='CLOSED')return {kind:'closed',title:'市场已休市',detail:'展示最近一笔有效报价，返航判断将在下个交易时段恢复。',Icon:Clock3}
  if(props.status.quote_status==='FRESH'){
    const fallback=Object.keys(props.status.sources||{}).includes('akshare')
    return fallback?{kind:'fallback',title:'备用行情已接管',detail:'腾讯行情暂不可用，当前报价由 AKShare 补充。',Icon:RadioTower}:{kind:'ready',title:'行情正常',detail:'当前行情可用于收益与返航判断。',Icon:ShieldCheck}
  }
  if(props.status.quote_status==='STALE')return {kind:'stale',title:'行情延迟',detail:'已有历史报价，但已超过可用于返航判断的时限。',Icon:CircleAlert}
  return {kind:'unavailable',title:'行情不可用',detail:'所有免费行情源暂未返回有效报价，系统不会触发返航。',Icon:WifiOff}
})
const sources=computed(()=>Object.keys(props.status.sources||{}).join(' · ')||'等待行情')
const updated=computed(()=>props.status.updated_at?dateTime(props.status.updated_at):'暂无有效报价')
</script>

<template>
  <section :class="['market-status',state.kind]" aria-live="polite">
    <component :is="state.Icon" :size="18"/>
    <div class="market-copy"><strong>{{state.title}}</strong><span>{{state.detail}}</span></div>
    <dl>
      <div><dt>数据源</dt><dd>{{sources}}</dd></div>
      <div><dt>报价时间</dt><dd>{{updated}}</dd></div>
      <div v-if="status.age_seconds!==null&&status.age_seconds!==undefined"><dt>报价年龄</dt><dd>{{status.age_seconds}} 秒</dd></div>
    </dl>
    <small v-if="status.last_error">最近请求失败，系统会自动重试。</small>
  </section>
</template>

<style scoped>
.market-status{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:12px;margin-bottom:12px;padding:12px 15px;border:1px solid #d9e5f2;border-radius:13px;background:#f7fbff;color:#365a82}.market-status>svg{color:#3175c7}.market-copy{display:grid;gap:3px}.market-copy strong{font-size:13px}.market-copy span{color:#637d9a;font-size:11px}.market-status dl{display:flex;gap:18px;margin:0}.market-status dl div{display:grid;gap:2px}.market-status dt{color:#8296aa;font-size:9px}.market-status dd{margin:0;color:#38556f;font-size:11px;font-weight:650}.market-status>small{grid-column:2/-1;color:#93601c;font-size:10px}.market-status.fallback{border-color:#e7d6ac;background:#fffaf0;color:#8f651d}.market-status.fallback>svg{color:#d1962d}.market-status.stale{border-color:#efd8aa;background:#fffaf0;color:#8f651d}.market-status.stale>svg{color:#d1962d}.market-status.unavailable{border-color:#efcfd2;background:#fff6f6;color:#9f464b}.market-status.unavailable>svg{color:#c94850}.market-status.closed{border-color:#dde4ea;background:#fafbfd;color:#657585}.market-status.closed>svg{color:#718294}@media(max-width:900px){.market-status{grid-template-columns:auto minmax(0,1fr);align-items:start;margin-bottom:10px}.market-status dl{grid-column:1/-1;gap:12px;padding-left:30px}.market-copy span{font-size:10px}.market-status>small{grid-column:1/-1}.market-status dd{font-size:10px}}
</style>
