<script setup lang="ts">
import {computed,onMounted,reactive,ref} from 'vue'
import {Anchor,Scale} from 'lucide-vue-next'
import {get,post} from '../api/client'
import AppModal from '../components/AppModal.vue'
import type {ReturnGroup} from '../types'
import {number,percent} from '../utils/format'

const groups=ref<ReturnGroup[]>([]),active=ref<ReturnGroup|null>(null),reconcileGroup=ref<ReturnGroup|null>(null)
const message=ref(''),error=ref(''),modalError=ref(''),loading=ref(true),opening=ref(false),saving=ref(false),reconciling=ref(false)
const exitForm=reactive({total_quantity:0,exit_price:'',exit_time:'',total_fee:'5',allocations:[] as {voyage_id?:number;voyage_no:string;quantity:number}[]})
const brokerQty=ref(0),reconcileResult=ref<any>(null)
const allocationTotal=computed(()=>exitForm.allocations.reduce((sum,item)=>sum+Number(item.quantity||0),0))
const allocationMatches=computed(()=>allocationTotal.value===Number(exitForm.total_quantity))
function localDateTime(){const date=new Date();return new Date(date.getTime()-date.getTimezoneOffset()*60_000).toISOString().slice(0,16)}
async function load(){loading.value=true;error.value='';try{groups.value=await get<ReturnGroup[]>('/api/returns/ready')}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
async function openExit(group:ReturnGroup){if(opening.value)return;opening.value=true;modalError.value='';try{const voyages:any[]=await get('/api/voyages');exitForm.allocations=group.ready_voyages.map(item=>({voyage_id:voyages.find(voyage=>voyage.voyage_no===item.voyage_no)?.id,voyage_no:item.voyage_no,quantity:item.remaining_quantity}));if(exitForm.allocations.some(item=>!item.voyage_id))throw new Error('航次资料尚未同步，请刷新后重试');exitForm.total_quantity=group.ready_quantity;exitForm.exit_price=group.ready_voyages[0]?.monitor_price||'';exitForm.exit_time=localDateTime();exitForm.total_fee='5';active.value=group}catch(e){error.value=(e as Error).message}finally{opening.value=false}}
async function submitExit(){if(!active.value||saving.value)return;modalError.value='';if(Number(exitForm.total_quantity)<=0||Number(exitForm.exit_price)<=0||Number(exitForm.total_fee)<0){modalError.value='请填写有效的卖出份额、成交均价和费用';return}if(!allocationMatches.value){modalError.value='航次分配合计必须与实际卖出份额一致';return}if(exitForm.allocations.some(item=>Number(item.quantity)<=0)){modalError.value='每个航次的分配份额必须大于 0';return}if(new Date(exitForm.exit_time)>new Date()){modalError.value='成交时间不能晚于当前时间';return}saving.value=true;try{await post('/api/exits',{symbol:active.value.symbol,exit_time:new Date(exitForm.exit_time).toISOString(),exit_price:exitForm.exit_price,total_quantity:exitForm.total_quantity,total_fee:exitForm.total_fee,allocations:exitForm.allocations.map(item=>({voyage_id:item.voyage_id,quantity:item.quantity}))});active.value=null;message.value='返航记录已保存，航次与舱位状态已更新。';await load()}catch(e){modalError.value=(e as Error).message}finally{saving.value=false}}
async function reconcile(){if(!reconcileGroup.value||reconciling.value)return;if(Number(brokerQty.value)<0){modalError.value='券商份额不能小于 0';return}reconciling.value=true;modalError.value='';try{reconcileResult.value=await post('/api/reconcile',{symbol:reconcileGroup.value.symbol,broker_quantity:brokerQty.value})}catch(e){modalError.value=(e as Error).message}finally{reconciling.value=false}}
function closeExit(){active.value=null;modalError.value=''}
function closeReconcile(){reconcileGroup.value=null;reconcileResult.value=null;modalError.value=''}
onMounted(load)
</script>
<template>
  <div class="page returns-page">
    <header class="returns-page-header"><div><p class="section-kicker">LANDING SETTLEMENT · 返航中心</p><h1>待返航航次</h1><p>仅列出行情有效、已可卖且达到目标收益的航次。确认成交后，系统按你指定的分配完成归档。</p></div><div class="return-count"><span>READY TO RETURN</span><b>{{groups.reduce((total,group)=>total+group.ready_voyages.length,0)}}</b></div></header>
    <p v-if="message" class="success-banner" role="status">{{message}}</p><p v-if="error" class="error-banner" role="alert">{{error}}</p>
    <div v-if="loading" class="panel loading" aria-live="polite">正在核对返航条件…</div>
    <div v-else-if="!groups.length" class="panel empty large"><Anchor :size="30"/><h2>暂无可返航航次</h2><p>系统会持续根据买一价和净收益线监控。</p></div>
    <section v-for="group in groups" :key="group.symbol" class="return-group panel"><header><div><p class="eyebrow">{{group.symbol}}</p><h2>{{group.name}}</h2></div><div class="system-position"><span>系统总持仓</span><b>{{number(group.system_total_quantity)}} 份</b></div></header><div class="allocation-list"><div v-for="voyage in group.ready_voyages" :key="voyage.voyage_no"><b>{{voyage.voyage_no}}</b><span>{{number(voyage.remaining_quantity)}} 份</span><span class="positive">{{percent(voyage.net_return)}}</span><i class="status ready">可返航</i></div></div><footer><div><span>当前可返航</span><strong>{{number(group.ready_quantity)}} <small>份</small></strong></div><div class="button-group"><button class="secondary" @click="reconcileGroup=group;brokerQty=group.system_total_quantity;modalError='' "><Scale :size="16"/>持仓核对</button><button class="primary" :disabled="opening" @click="openExit(group)">{{opening?'准备中…':'记录返航'}}</button></div></footer></section>

    <AppModal v-if="active" :title="`记录返航 · ${active.symbol}`" eyebrow="LANDING SETTLEMENT" variant="settlement" :prevent-close="saving" @close="closeExit">
      <form class="form-grid" @submit.prevent="submitExit">
        <p v-if="modalError" class="error-banner form-error" role="alert">{{modalError}}</p>
        <label>实际卖出份额<input v-model.number="exitForm.total_quantity" type="number" min="1" step="1" required/></label>
        <label>成交均价<input v-model="exitForm.exit_price" type="number" inputmode="decimal" min="0.001" step="0.001" required/></label>
        <label>成交时间<input v-model="exitForm.exit_time" type="datetime-local" required/></label>
        <label>费用<input v-model="exitForm.total_fee" type="number" inputmode="decimal" min="0" step="0.01" required/></label>
        <div class="allocation-editor"><h3>航次分配</h3><p>分配合计必须与实际卖出份额一致，系统不会自动 FIFO。</p><label v-for="item in exitForm.allocations" :key="item.voyage_no"><span>{{item.voyage_no}}</span><input v-model.number="item.quantity" type="number" min="1" step="1" required/></label><div :class="['allocation-total',{mismatch:!allocationMatches}]"><span>分配合计</span><b>{{number(allocationTotal)}} / {{number(exitForm.total_quantity)}} 份</b></div></div>
        <button class="primary full" :disabled="saving||!allocationMatches">{{saving?'正在保存…':'确认保存返航'}}</button>
      </form>
    </AppModal>

    <AppModal v-if="reconcileGroup" :title="`持仓核对 · ${reconcileGroup.symbol}`" eyebrow="POSITION RECONCILIATION" :prevent-close="reconciling" @close="closeReconcile">
      <div class="reconcile-box"><p v-if="modalError" class="error-banner" role="alert">{{modalError}}</p><div><span>系统</span><b>{{number(reconcileGroup.system_total_quantity)}}</b></div><label>券商当前份额<input v-model.number="brokerQty" type="number" min="0" step="1"/></label><button class="secondary full" :disabled="reconciling" @click="reconcile">{{reconciling?'核对中…':'开始核对'}}</button><div v-if="reconcileResult" :class="['reconcile-result',reconcileResult.matched?'matched':'mismatch']"><strong>{{reconcileResult.matched?'一致':'存在差异'}}</strong><span>差异 {{number(reconcileResult.difference)}} 份</span><small>系统不会自动修正账本。</small></div></div>
    </AppModal>
  </div>
</template>

<style scoped>
.returns-page{max-width:1120px}.returns-page-header{display:flex;align-items:end;justify-content:space-between;gap:24px;margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid var(--line)}.returns-page-header h1{margin:5px 0 6px;font-size:25px;letter-spacing:-.03em}.returns-page-header p:last-child{max-width:680px;margin:0;color:var(--muted-2);font-size:13px;line-height:1.6}.return-count{display:grid;justify-items:end;padding-left:18px;border-left:2px solid var(--tower-green)}.return-count span{color:var(--muted-2);font-size:9px;font-weight:700;letter-spacing:.12em}.return-count b{color:var(--tower-green);font-size:28px;font-variant-numeric:tabular-nums}@media(max-width:900px){.returns-page-header{align-items:flex-start;flex-direction:column}.return-count{justify-items:start}}
.form-error{grid-column:1/-1;margin:0}.allocation-total.mismatch{color:var(--beacon-red)}
</style>
