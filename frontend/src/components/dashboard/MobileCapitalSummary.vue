<script setup lang="ts">
import {computed} from 'vue'
import {CircleDollarSign,Plane,WalletCards} from 'lucide-vue-next'
import type {Dashboard} from '../../types'

const props=defineProps<{data:Dashboard}>()
const money=(value:string)=>new Intl.NumberFormat('zh-CN',{style:'currency',currency:'CNY',maximumFractionDigits:0}).format(Number(value)||0)
const deployedPercent=computed(()=>{const total=Number(props.data.capital.total)||0;return total?Math.min(Number(props.data.capital.in_flight)/total*100,100):0})
</script>

<template>
  <section class="mobile-capital-summary" aria-label="资金态势摘要">
    <header><div><small>CAPITAL STATUS</small><h1>资金态势</h1></div><span :class="['quote-state',{ok:data.market.quote_status==='FRESH'}]"><i></i>{{data.market.quote_status==='FRESH'?'行情在线':'行情待更新'}}</span></header>
    <article class="capital-primary">
      <span class="metric-icon"><CircleDollarSign :size="18"/></span><div><small>总资金</small><strong>{{money(data.capital.total)}}</strong></div>
      <em>{{data.counts.available_slots}} 个可用舱位</em>
    </article>
    <div class="capital-metrics">
      <article><span><Plane :size="15"/>在航资金</span><b>{{money(data.capital.in_flight)}}</b><small>{{data.counts.in_flight}} 个航次</small></article>
      <article class="ready"><span><WalletCards :size="15"/>待返航</span><b>{{money(data.capital.ready_to_return)}}</b><small>{{data.counts.ready_to_return}} 个航次</small></article>
    </div>
    <div class="deployment"><span>资金调度率</span><b>{{deployedPercent.toFixed(0)}}%</b><i><em :style="{width:`${deployedPercent}%`}"></em></i></div>
  </section>
</template>

<style scoped>
.mobile-capital-summary{display:none}
@media(max-width:1050px){.mobile-capital-summary{display:grid;gap:10px;margin-bottom:12px;padding:16px;border:1px solid #dfe7ef;border-radius:15px;background:#fff;box-shadow:0 6px 20px rgba(35,55,76,.045)}.mobile-capital-summary>header{display:flex;align-items:center;justify-content:space-between}.mobile-capital-summary h1{margin:2px 0 0;font-size:20px;letter-spacing:-.03em}.mobile-capital-summary header small{color:#8b99a8;font-size:8px;font-weight:750;letter-spacing:.13em}.quote-state{display:flex;align-items:center;gap:5px;color:#a16b17;font-size:9px}.quote-state i{width:6px;height:6px;border-radius:50%;background:#e39b2d}.quote-state.ok{color:#18845d}.quote-state.ok i{background:#1e9e63}.capital-primary{display:grid;grid-template-columns:36px 1fr auto;align-items:center;gap:10px;padding:12px;border-radius:12px;background:linear-gradient(120deg,#f3f7fc,#f8fbfd)}.metric-icon{width:36px;height:36px;display:grid;place-items:center;border-radius:10px;background:#e5effb;color:#2769bd}.capital-primary div{display:grid;gap:2px}.capital-primary small,.capital-metrics small{color:#8190a0;font-size:9px}.capital-primary strong{font-size:22px;letter-spacing:-.04em}.capital-primary>em{color:#71849a;font-size:9px;font-style:normal}.capital-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px}.capital-metrics article{display:grid;gap:4px;padding:11px;border:1px solid #e2e9f0;border-radius:11px}.capital-metrics article.ready{border-color:#d6e9df;background:#f8fcfa}.capital-metrics span{display:flex;align-items:center;gap:5px;color:#6d7d8e;font-size:10px}.capital-metrics b{font-size:15px}.capital-metrics .ready b{color:#17835d}.deployment{display:grid;grid-template-columns:1fr auto;align-items:center;gap:5px;color:#6d7d8e;font-size:9px}.deployment b{color:#34475b;font-size:11px}.deployment>i{grid-column:1/-1;height:5px;overflow:hidden;border-radius:99px;background:#e8edf2}.deployment>i em{display:block;height:100%;border-radius:inherit;background:#367ac8}}
@media(min-width:761px) and (max-width:1050px){.mobile-capital-summary{grid-template-columns:1.2fr 1fr}.mobile-capital-summary>header,.deployment{grid-column:1/-1}.capital-metrics{align-self:stretch}}
</style>
