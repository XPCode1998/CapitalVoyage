<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {CalendarDays,ChevronDown,PlaneLanding,RotateCcw,Search} from 'lucide-vue-next'
import {get} from '../api/client'
import type {HistoryData} from '../types'
import {dateTime,money,number,percent} from '../utils/format'

const data=ref<HistoryData|null>(null),error=ref(''),query=ref('')
const resultFilter=ref<'ALL'|'PROFIT'|'LOSS'>('ALL'),expanded=ref<number|null>(null)
const records=computed(()=>data.value?.records.filter((record:any)=>{const text=`${record.voyage_no} ${record.name} ${record.symbol}`.toLowerCase();const value=Number(record.realized_return||0);return text.includes(query.value.trim().toLowerCase())&&(resultFilter.value==='ALL'||(resultFilter.value==='PROFIT'?value>=0:value<0))})||[])
async function load(){try{data.value=await get('/api/history')}catch(e){error.value=(e as Error).message}}
onMounted(load)
</script>

<template>
  <div class="page logbook-page">
    <p v-if="error" class="error-banner">飞行日志读取失败：{{error}}</p>
    <template v-if="data">
      <section class="logbook-summary" aria-label="钱途统计摘要">
        <div class="summary-lead"><span>累计实现收益</span><strong :class="{negative:Number(data.stats.total_realized_profit)<0}">{{money(data.stats.total_realized_profit)}}</strong></div>
        <div><b>{{number(data.stats.completed_voyages)}}</b><span>完成航次</span></div>
        <div><b>{{Number(data.stats.average_voyage_days).toFixed(1)}} 天</b><span>平均航程</span></div>
        <div><b>{{data.stats.longest_voyage_days}} 天</b><span>最长航程</span></div>
        <div><b>{{Number(data.stats.average_turnover).toFixed(1)}}</b><span>平均周转</span></div>
      </section>

      <section class="logbook-panel">
        <header class="logbook-toolbar">
          <div class="arrival-heading"><span class="terminal-code">TZX</span><div><p class="section-kicker">ARRIVAL LOG · 到港归档</p><h1>钱途飞行日志</h1><span>财富自由塔台 · 所有返航航班的成交与收益归档</span></div></div>
          <div class="logbook-filters">
            <label class="search-box"><Search :size="15"/><span class="sr-only">搜索航次</span><input v-model="query" placeholder="搜索航次或 ETF"/></label>
            <select v-model="resultFilter" aria-label="收益结果筛选"><option value="ALL">全部结果</option><option value="PROFIT">盈利航次</option><option value="LOSS">亏损航次</option></select>
          </div>
        </header>

        <div v-if="!records.length" class="logbook-empty"><PlaneLanding :size="26"/><b>{{data.records.length?'没有匹配的航班':'尚无到港航班'}}</b><span>{{data.records.length?'调整搜索词或收益筛选后再试。':'完成返航后，航班票根会自动归档到这里。'}}</span><button v-if="data.records.length" class="reset-filter" @click="query='';resultFilter='ALL'"><RotateCcw :size="13"/>清除筛选</button></div>
        <div v-else class="logbook-list">
          <div class="arrival-board-head"><span>航班 / FLIGHT</span><span>起飞机场 / ORIGIN</span><span>航路 / ROUTE</span><span>到港 / ARRIVAL</span><span>收益 / RESULT</span></div>
          <article v-for="record in records" :key="record.id" :class="['logbook-ticket',{open:expanded===record.id}]">
            <button class="logbook-main" :aria-expanded="expanded===record.id" :aria-controls="`logbook-detail-${record.id}`" @click="expanded=expanded===record.id?null:record.id">
              <div class="logbook-flight"><span class="landed-stamp"><PlaneLanding :size="13"/>LANDED</span><strong>{{record.voyage_no}}</strong><small>{{record.name}} · {{record.symbol}}</small></div>
              <div class="journey-point"><span>ETF 资金机场</span><b>{{record.symbol}}</b><small>{{dateTime(record.entry_time)}} · ¥{{record.entry_price}}</small></div>
              <div class="journey-line"><i></i><PlaneLanding :size="16"/><em>{{record.trading_days}} 个交易日</em></div>
              <div class="journey-point arrival"><span>财富自由塔台</span><b>WFT</b><small>{{dateTime(record.exit_time)}} · ¥{{record.exit_price}}</small></div>
              <div class="logbook-result"><span>实际收益</span><strong :class="{profit:Number(record.realized_return)>=0,loss:Number(record.realized_return)<0}">{{percent(record.realized_return)}}</strong><small v-if="record.realized_profit!==undefined">{{money(record.realized_profit)}}</small></div>
              <ChevronDown :class="['expand-icon',{rotate:expanded===record.id}]" :size="16"/>
            </button>
            <Transition name="detail-expand"><dl v-if="expanded===record.id" :id="`logbook-detail-${record.id}`" class="logbook-detail">
              <div><dt>返航份额</dt><dd>{{number(record.quantity||record.exit_quantity||0)}} 份</dd></div><div><dt>起航成本</dt><dd>{{record.entry_cost?money(record.entry_cost):'—'}}</dd></div><div><dt>返航金额</dt><dd>{{record.exit_amount?money(record.exit_amount):'—'}}</dd></div><div><dt>交易费用</dt><dd>{{record.total_fee?money(record.total_fee):'—'}}</dd></div><div><dt>归档时间</dt><dd>{{dateTime(record.exit_time)}}</dd></div>
            </dl></Transition>
          </article>
        </div>
      </section>
    </template>
    <div v-else-if="!error" class="loading"><CalendarDays :size="20"/>正在整理飞行日志…</div>
  </div>
</template>

<style scoped>
.logbook-page{max-width:1680px}.logbook-summary{display:grid;grid-template-columns:1.55fr repeat(4,1fr);min-height:94px;margin-bottom:12px;border:1px solid var(--line);border-radius:var(--radius-region);background:#fff;box-shadow:0 5px 18px rgba(36,55,78,.035)}.logbook-summary>div{display:flex;flex-direction:column;justify-content:center;padding:16px 22px;border-right:1px solid var(--line-soft)}.logbook-summary>div:last-child{border:0}.logbook-summary span{color:var(--muted-2);font-size:10px}.logbook-summary b{margin-bottom:5px;font-size:18px}.summary-lead{background:linear-gradient(115deg,#f8fcfa,#fff);border-radius:14px 0 0 14px}.summary-lead strong{margin-top:5px;color:var(--tower-green);font-size:27px;letter-spacing:-.04em}.summary-lead strong.negative{color:var(--beacon-red)}.logbook-panel{overflow:hidden;border:1px solid var(--line);border-radius:var(--radius-region);background:#fff}.logbook-toolbar{display:flex;justify-content:space-between;align-items:end;gap:22px;padding:22px 24px 18px;border-bottom:1px solid var(--line-soft)}.logbook-toolbar h1{margin:4px 0 3px;font-size:20px;letter-spacing:-.025em}.logbook-toolbar>div>span{color:var(--muted-2);font-size:11px}.logbook-filters{display:flex;gap:8px}.search-box{height:36px;display:flex;align-items:center;gap:8px;padding:0 11px;border:1px solid var(--line);border-radius:var(--radius-control);color:#8c98a5}.search-box input{width:180px;padding:0;border:0;box-shadow:none;background:transparent}.logbook-filters select{width:114px;height:36px;padding:0 30px 0 10px;font-size:11px}.logbook-list{padding:4px 16px 14px}.logbook-ticket{position:relative;border-bottom:1px solid var(--line-soft)}.logbook-main{width:100%;min-height:104px;display:grid;grid-template-columns:1.15fr .95fr 1.3fr .95fr .8fr 22px;align-items:center;gap:14px;padding:14px 8px;border:0;background:#fff;text-align:left}.logbook-main:hover{background:#f9fbfd}.logbook-flight,.journey-point,.logbook-result{display:grid;gap:4px}.landed-stamp{width:max-content;display:inline-flex;align-items:center;gap:4px;color:var(--tower-green);font-size:7px;font-weight:750;letter-spacing:.1em}.logbook-flight strong{font-size:16px}.logbook-flight small,.journey-point small,.logbook-result span{color:var(--muted-2);font-size:9px}.journey-point span{color:#98a3ae;font-size:8px}.journey-point b{font-size:11px}.journey-line{position:relative;height:44px;display:grid;place-items:center;color:var(--tower-green)}.journey-line i{position:absolute;top:20px;left:0;right:0;border-top:1px dashed #cad5df}.journey-line svg{position:relative;padding:3px;box-sizing:content-box;border-radius:50%;background:#fff}.journey-line em{position:absolute;bottom:0;color:#8996a3;font-size:8px;font-style:normal}.logbook-result{text-align:right}.logbook-result strong{font-size:18px}.logbook-result .profit{color:var(--tower-green)}.logbook-result .loss{color:var(--beacon-red)}.logbook-result small{color:#657384;font-size:9px}.expand-icon{color:#91a0ae;transition:transform .2s}.expand-icon.rotate{transform:rotate(180deg)}.logbook-detail{display:grid;grid-template-columns:repeat(5,1fr);margin:0 8px 14px;padding:14px 16px;border-radius:10px;background:#f6f9fb}.logbook-detail div{padding:0 15px;border-right:1px solid #e2e9ef}.logbook-detail div:first-child{padding-left:0}.logbook-detail div:last-child{border:0}.logbook-detail dt{color:#8c98a5;font-size:8px}.logbook-detail dd{margin:5px 0 0;color:#344456;font-size:11px;font-weight:650}.logbook-empty{min-height:300px;display:grid;place-content:center;justify-items:center;gap:8px;color:#95a1ad}.logbook-empty b{color:#536171;font-size:13px}.logbook-empty span{font-size:10px}.loading{display:flex;justify-content:center;align-items:center;gap:8px}.detail-expand-enter-active,.detail-expand-leave-active{transition:opacity .18s ease,transform .18s ease}.detail-expand-enter-from,.detail-expand-leave-to{opacity:0;transform:translateY(-4px)}
@media(max-width:1100px){.logbook-summary{grid-template-columns:1.4fr repeat(2,1fr)}.logbook-summary>div:nth-child(3){border-right:0}.logbook-summary>div:nth-child(n+4){border-top:1px solid var(--line-soft)}.logbook-main{grid-template-columns:1fr .9fr 1fr .9fr}.logbook-result{grid-column:4}.expand-icon{display:none}.journey-line{grid-column:3}.logbook-detail{grid-template-columns:repeat(3,1fr);gap:12px}.logbook-detail div{border:0;padding:0}}@media(max-width:900px){.logbook-summary{grid-template-columns:1fr 1fr}.summary-lead{grid-column:1/-1;border-radius:14px 14px 0 0}.logbook-summary>div{padding:14px}.logbook-toolbar{align-items:stretch;flex-direction:column}.logbook-filters{width:100%}.search-box{flex:1}.search-box input{width:100%}.logbook-main{grid-template-columns:1fr 1fr;gap:16px}.journey-line{display:none}.journey-point.arrival{grid-column:2}.logbook-result{grid-column:1/-1;text-align:left}.logbook-detail{grid-template-columns:1fr 1fr}}
</style>
<style scoped>
.reset-filter{display:inline-flex;align-items:center;gap:5px;margin-top:5px;padding:7px 10px;border:1px solid #dce4ec;border-radius:7px;background:#fff;color:#496079;font-size:9px;font-weight:650}.reset-filter:hover{background:#f5f8fb}
</style>

<style scoped>
.arrival-heading{display:flex;align-items:center;gap:13px}.terminal-code{width:52px;height:52px;display:grid;place-items:center;border-radius:9px;background:#183e69;color:#fff;font-size:17px;font-weight:750;letter-spacing:.08em;box-shadow:inset 0 -3px 0 rgba(0,0,0,.12)}.arrival-heading>div{display:grid}.arrival-board-head{display:grid;grid-template-columns:1.15fr .95fr 1.3fr .95fr .8fr 22px;gap:14px;padding:10px 17px 8px;border-bottom:1px solid #dbe4ed;color:#8594a3;font-size:7px;font-weight:700;letter-spacing:.08em}.arrival-board-head span:nth-child(5){text-align:right}.logbook-list{display:grid;gap:9px;padding-top:10px}.logbook-ticket{overflow:hidden;border:1px solid #dfe6ed;border-radius:11px;background:#fff;box-shadow:0 3px 10px rgba(37,55,76,.035)}.logbook-ticket::before,.logbook-ticket::after{content:"";position:absolute;top:50%;z-index:2;width:12px;height:24px;border:1px solid #dfe6ed;border-radius:14px;background:var(--canvas-bg);transform:translateY(-50%)}.logbook-ticket::before{left:-7px}.logbook-ticket::after{right:-7px}.logbook-main{padding-left:17px;padding-right:17px}.logbook-flight{padding-left:8px;border-left:3px solid var(--tower-green)}.journey-point b{font-size:16px;letter-spacing:.04em}.journey-point small{white-space:nowrap}.logbook-detail{margin-left:16px;margin-right:16px;border-top:1px dashed #cdd8e3;border-radius:0 0 9px 9px}.logbook-ticket.open{border-color:#b9cec3;box-shadow:0 7px 20px rgba(34,84,63,.07)}
@media(max-width:1100px){.arrival-board-head{display:none}}@media(max-width:900px){.terminal-code{width:44px;height:44px;font-size:14px}.arrival-heading{align-items:flex-start}.logbook-list{padding:10px}.logbook-ticket::before,.logbook-ticket::after{display:none}}
</style>
<style scoped>
.logbook-summary span{font-size:11px}.arrival-board-head{font-size:10px}.landed-stamp{font-size:10px}.logbook-flight small,.journey-point small,.logbook-result span{font-size:11px}.journey-point span{font-size:10px}.journey-line em{font-size:10px}.logbook-result small{font-size:11px}.logbook-detail dt{font-size:10px}.logbook-detail dd{font-size:12px}.logbook-empty span{font-size:11px}.reset-filter{min-height:36px;font-size:11px}
</style>
