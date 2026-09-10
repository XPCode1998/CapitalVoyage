<script setup lang="ts">
import {computed,onMounted,reactive,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {ArrowLeft,Clock3,Pencil,PlaneLanding,PlaneTakeoff,RadioTower,Search,Trash2} from 'lucide-vue-next'
import {get,patch,post} from '../api/client'
import AppModal from '../components/AppModal.vue'
import FlightSidePanel from '../components/FlightSidePanel.vue'
import FlightStateBadge from '../components/FlightStateBadge.vue'
import OperationToast from '../components/OperationToast.vue'
import SlotTicket from '../components/voyage/SlotTicket.vue'
import type {Slot,Voyage} from '../types'
import {dateTime,money,number,percent,stateDescription} from '../utils/format'

const slots=ref<Slot[]>([])
const route=useRoute(),router=useRouter()
const selected=ref<Voyage|null>(null)
const creating=ref<Slot|null>(null)
const editing=ref<Voyage|null>(null)
const returning=ref<Voyage|null>(null)
const cancelling=ref<Voyage|null>(null)
const error=ref('')
const message=ref('')
const modalError=ref('')
const saving=ref(false)
const loading=ref(true)
const security=ref<{symbol:string;name:string;market:string;settlement_mode:string;last_price:string|null}|null>(null)
const securityLoading=ref(false)
let lookupTimer:number|undefined
const preview=ref<{actual_investment:string;target_price:string}|null>(null)
const form=reactive({symbol:'510300',entry_time:new Date().toISOString().slice(0,16),entry_price:'',entry_quantity:12500,entry_fee:'5',target_return_percent:'2.00'})
const editForm=reactive({entry_time:'',entry_price:'',entry_quantity:0,entry_fee:'',target_return_percent:''})
const exitForm=reactive({exit_time:'',exit_price:'',total_fee:'0'})
const returnQuote=computed(()=>{if(!returning.value)return null;const price=Number(exitForm.exit_price||0),quantity=Number(returning.value.remaining_quantity||0),fee=Number(exitForm.total_fee||0),entryUnitCost=Number(returning.value.entry_cost||0)/Math.max(Number(returning.value.entry_quantity||1),1),net=price*quantity-fee-entryUnitCost*quantity;return{gross:price*quantity,net,rate:entryUnitCost?net/(entryUnitCost*quantity):0}})

function datetimeLocal(value:string|Date=new Date()){
  const date=value instanceof Date?value:new Date(value)
  return new Date(date.getTime()-date.getTimezoneOffset()*60_000).toISOString().slice(0,16)
}

function targetDecimal(value:string){return String(Number(value||0)/100)}
async function load(){loading.value=true;error.value='';try{slots.value=await get<Slot[]>('/api/slots');const requested=Number(route.query.voyage);if(requested){selected.value=slots.value.map(item=>item.voyage).find(item=>item?.id===requested)||null;router.replace({query:{}})}}catch(e){error.value=(e as Error).message}finally{loading.value=false}}
async function lookupSecurity(){const symbol=form.symbol.trim();security.value=null;if(!/^\d{6}$/.test(symbol))return;securityLoading.value=true;try{const results=await get<Array<{symbol:string;name:string;market:string;settlement_mode:string;last_price:string|null}>>(`/api/securities/search?q=${encodeURIComponent(symbol)}`);security.value=results.find(item=>item.symbol===symbol)||null}catch{security.value=null}finally{securityLoading.value=false}}
function scheduleLookup(){if(lookupTimer)window.clearTimeout(lookupTimer);lookupTimer=window.setTimeout(lookupSecurity,320)}
async function updatePreview(){if(!form.entry_price||!form.entry_quantity)return;try{preview.value=await post('/api/voyages/preview',{entry_price:form.entry_price,entry_quantity:form.entry_quantity,entry_fee:form.entry_fee,target_return:targetDecimal(form.target_return_percent)})}catch{preview.value=null}}
function validateCreate(){if(!/^\d{6}$/.test(form.symbol))return'请输入 6 位 ETF 代码';if(Number(form.entry_price)<=0||Number(form.entry_quantity)<=0||Number(form.entry_fee)<0)return'请检查起航价格、份额和费用';if(Number(form.target_return_percent)<=0)return'目标收益率必须大于 0';const cost=Number(form.entry_price)*Number(form.entry_quantity)+Number(form.entry_fee||0);if(!Number.isFinite(cost))return'请输入有效的起航数据';if(creating.value&&cost>Number(creating.value.budget_amount))return`实际投入不能超过舱位预算 ${money(creating.value.budget_amount)}`;if(new Date(form.entry_time)>new Date())return'起航时间不能晚于当前时间';return''}
async function create(){if(!creating.value||saving.value)return;modalError.value=validateCreate();if(modalError.value)return;saving.value=true;error.value='';try{await post('/api/voyages',{slot_id:creating.value.id,symbol:form.symbol,entry_time:new Date(form.entry_time).toISOString(),entry_price:form.entry_price,entry_quantity:form.entry_quantity,entry_fee:form.entry_fee,target_return:targetDecimal(form.target_return_percent)});message.value='新航班已签发并进入财富航线';creating.value=null;await load()}catch(e){modalError.value=(e as Error).message}finally{saving.value=false}}
function openEdit(voyage:Voyage){Object.assign(editForm,{entry_time:datetimeLocal(voyage.entry_time),entry_price:voyage.entry_price,entry_quantity:voyage.entry_quantity,entry_fee:voyage.entry_fee,target_return_percent:(Number(voyage.target_return)*100).toFixed(2)});editing.value=voyage;selected.value=null;modalError.value=''}
function openReturn(voyage:Voyage){Object.assign(exitForm,{exit_time:datetimeLocal(),exit_price:voyage.monitor_price||'',total_fee:'0'});returning.value=voyage;selected.value=null;modalError.value=''}
function openCancel(voyage:Voyage){cancelling.value=voyage;selected.value=null;modalError.value=''}
function canReturn(voyage:Voyage){return new Date()>=new Date(voyage.sellable_at)}
async function saveEdit(){if(!editing.value||saving.value)return;if(Number(editForm.entry_price)<=0||Number(editForm.entry_quantity)<=0||Number(editForm.entry_fee)<0){modalError.value='请检查起航价格、份额和费用';return}if(Number(editForm.target_return_percent)<=0){modalError.value='目标收益率必须大于 0';return}saving.value=true;modalError.value='';try{const updated=await patch<Voyage>(`/api/voyages/${editing.value.id}`,{entry_time:new Date(editForm.entry_time).toISOString(),entry_price:editForm.entry_price,entry_quantity:editForm.entry_quantity,entry_fee:editForm.entry_fee,target_return:targetDecimal(editForm.target_return_percent)});message.value=`${updated.voyage_no} 已完成改签`;editing.value=null;await load()}catch(e){modalError.value=(e as Error).message}finally{saving.value=false}}
async function submitReturn(){if(!returning.value||saving.value)return;if(Number(exitForm.exit_price)<=0||Number(exitForm.total_fee)<0){modalError.value='请填写有效的成交价格和卖出费用';return}if(new Date(exitForm.exit_time)>new Date()){modalError.value='返航时间不能晚于当前时间';return}saving.value=true;modalError.value='';try{const voyage=returning.value;await post('/api/exits',{symbol:voyage.symbol,exit_time:new Date(exitForm.exit_time).toISOString(),exit_price:exitForm.exit_price,total_quantity:voyage.remaining_quantity,total_fee:exitForm.total_fee,allocations:[{voyage_id:voyage.id,quantity:voyage.remaining_quantity}]});message.value=`${voyage.voyage_no} 已返航并写入钱途记录`;returning.value=null;await load()}catch(e){modalError.value=(e as Error).message}finally{saving.value=false}}
async function cancelVoyage(){if(!cancelling.value||saving.value)return;saving.value=true;modalError.value='';try{const voyage=cancelling.value;await post(`/api/voyages/${voyage.id}/cancel`);message.value=`${voyage.voyage_no} 已取消，舱位恢复待调度`;cancelling.value=null;await load()}catch(e){modalError.value=(e as Error).message}finally{saving.value=false}}
function activateSlot(slot:Slot){if(slot.voyage)selected.value=slot.voyage;else creating.value=slot}

watch(message,value=>{if(value)window.setTimeout(()=>{if(message.value===value)message.value=''},3500)})
onMounted(()=>{load();lookupSecurity()})
</script>

<template>
  <div class="page voyages-page">
    <OperationToast :message="message||error" :type="error?'error':'success'" @close="error='';message=''"/>

    <div v-if="loading" class="loading" aria-live="polite">正在读取资金舱位…</div>

    <section v-else class="ticket-grid" aria-label="资金舱位">
      <SlotTicket v-for="slot in slots" :key="slot.id" :slot="slot" @activate="activateSlot"/>
    </section>

    <FlightSidePanel v-if="creating" title="签发新航班" eyebrow="BOARDING ISSUANCE · 调度柜台" strip-label="DISPATCH DESK" :prevent-close="saving" @close="creating=null">
      <form id="create-flight-form" class="form-grid aviation-form drawer-form" @submit.prevent="create">
        <div class="boarding-route"><div><small>DEPARTURE / 起点</small><strong>{{form.symbol||'ETF'}}</strong><span>ETF 资金机场</span></div><div class="boarding-airway"><i></i><PlaneTakeoff :size="20"/><em>QC / NEW</em></div><div><small>DESTINATION / 目的地</small><strong>WFT</strong><span>财富自由塔台</span></div><b>{{String(creating.slot_no).padStart(2,'0')}}</b></div>
        <p class="form-section-title">01 · 航班身份与起航信息</p>
        <p v-if="modalError" class="error-banner form-alert">{{modalError}}</p>
        <label>ETF 代码<div class="field-with-icon"><input v-model="form.symbol" autofocus required maxlength="6" inputmode="numeric" placeholder="510300" @input="scheduleLookup"/><Search :size="14"/></div></label>
        <label>起航日期时间<input v-model="form.entry_time" type="datetime-local" required/></label>
        <div v-if="security||securityLoading" class="security-result"><span>{{securityLoading?'正在校验 ETF…':security?.name}}</span><b v-if="security">{{security.market}} · {{security.settlement_mode}} · 最近有效价 {{security.last_price||'—'}}</b></div>
        <label>起航价格<div class="input-with-unit"><input v-model="form.entry_price" inputmode="decimal" required placeholder="4.000" @input="updatePreview"/><span>元</span></div></label>
        <label>起航份额<div class="input-with-unit"><input v-model.number="form.entry_quantity" type="number" min="1" required @input="updatePreview"/><span>份</span></div></label>
        <label>起航费用<div class="input-with-unit"><input v-model="form.entry_fee" inputmode="decimal" min="0" @input="updatePreview"/><span>元</span></div></label>
        <label>目标收益率<div class="input-with-unit"><input v-model="form.target_return_percent" inputmode="decimal" min="0.01" required @input="updatePreview"/><span>%</span></div><small>直接填写百分数，例如 2.00</small></label>
        <p class="form-section-title">02 · 舱位与返航计划</p>
        <div class="preview-box">
          <div><span>舱位预算</span><b>{{money(creating.budget_amount)}}</b></div>
          <div><span>实际投入</span><b>{{preview?money(preview.actual_investment):'—'}}</b></div>
          <div><span>返航目标</span><b>{{Number(form.target_return_percent||0).toFixed(2)}}%</b></div>
          <div><span>预计净返航线</span><b>{{preview?.target_price||'—'}}</b></div>
        </div>
      </form>
      <template #footer><div class="side-panel-actions one"><button type="submit" form="create-flight-form" class="panel-action primary" :disabled="saving"><PlaneTakeoff :size="16"/>{{saving?'正在签发…':'签发机票并起航'}}</button></div></template>
    </FlightSidePanel>

    <FlightSidePanel v-if="editing" :title="`改签 · ${editing.voyage_no}`" eyebrow="FLIGHT RESCHEDULE · 签派变更" strip-label="RESCHEDULE DESK" :prevent-close="saving" @close="editing=null;modalError=''">
      <form id="edit-flight-form" class="form-grid aviation-form drawer-form" @submit.prevent="saveEdit">
        <div class="boarding-route"><div><small>DEPARTURE / 起点</small><strong>{{editing.symbol}}</strong><span>{{editing.name}}</span></div><div class="boarding-airway"><i></i><PlaneTakeoff :size="20"/><em>{{editing.voyage_no}}</em></div><div><small>DESTINATION / 目的地</small><strong>WFT</strong><span>财富自由塔台</span></div><b>R</b></div>
        <p class="form-section-title">航班资料变更</p>
        <p v-if="modalError" class="error-banner form-alert">{{modalError}}</p>
        <label>ETF 代码<input :value="editing.symbol" disabled/></label>
        <label>起航日期时间<input v-model="editForm.entry_time" type="datetime-local" required/></label>
        <label>起航价格<input v-model="editForm.entry_price" inputmode="decimal" required/></label>
        <label>起航份额<input v-model.number="editForm.entry_quantity" type="number" min="1" required/></label>
        <label>起航费用<input v-model="editForm.entry_fee" inputmode="decimal" min="0" required/></label>
        <label>目标收益率<div class="input-with-unit"><input v-model="editForm.target_return_percent" inputmode="decimal" required/><span>%</span></div><small>改签起航时间后，可卖时间会按结算规则自动重算。</small></label>
      </form>
      <template #footer><div class="side-panel-actions two"><button type="button" class="panel-action secondary" @click="editing=null"><ArrowLeft :size="15"/>返回</button><button type="submit" form="edit-flight-form" class="panel-action primary" :disabled="saving"><Pencil :size="15"/>{{saving?'保存中…':'确认改签'}}</button></div></template>
    </FlightSidePanel>

    <FlightSidePanel v-if="returning" :title="`返航 · ${returning.voyage_no}`" eyebrow="LANDING SETTLEMENT · 到港结算" strip-label="LANDING DESK" :subtitle="`${returning.name} · ${returning.symbol}`" :prevent-close="saving" @close="returning=null;modalError=''">
      <form id="return-flight-form" class="form-grid return-form drawer-form" @submit.prevent="submitReturn">
        <div class="boarding-route return-route"><div><small>DEPARTURE / 起点</small><strong>{{returning.symbol}}</strong><span>{{returning.name}}</span></div><div class="boarding-airway"><i></i><PlaneLanding :size="20"/><em>{{returning.voyage_no}}</em></div><div><small>ARRIVAL / 到港</small><strong>WFT</strong><span>财富自由塔台</span></div></div>
        <p v-if="modalError" class="error-banner form-alert">{{modalError}}</p>
        <div class="return-summary"><div><span>ETF</span><b>{{returning.name}} · {{returning.symbol}}</b></div><div><span>本次返航份额</span><b>{{number(returning.remaining_quantity)}} 份</b></div><div><span>参考监控价</span><b>{{returning.monitor_price||'—'}}</b></div></div>
        <label>最终卖出价格<div class="input-with-unit"><input v-model="exitForm.exit_price" autofocus inputmode="decimal" required placeholder="实际成交价格"/><span>元</span></div></label>
        <label>返航时间<input v-model="exitForm.exit_time" type="datetime-local" required/></label>
        <label>卖出费用<div class="input-with-unit"><input v-model="exitForm.total_fee" inputmode="decimal" min="0" required/><span>元</span></div></label>
        <div v-if="returnQuote" class="settlement-preview"><div><span>预计成交总额</span><b>{{money(returnQuote.gross)}}</b></div><div><span>预计净收益</span><b :class="returnQuote.net>=0?'positive':'negative'">{{money(returnQuote.net)}}</b></div><div><span>预计实际收益率</span><b :class="returnQuote.rate>=0?'positive':'negative'">{{percent(returnQuote.rate)}}</b></div></div>
        <p class="return-note"><b>到港后不可撤回</b> · 将返航全部剩余份额，释放舱位，并把实际成交结果写入钱途记录。</p>
      </form>
      <template #footer><div class="side-panel-actions two"><button type="button" class="panel-action secondary" @click="returning=null"><ArrowLeft :size="15"/>返回</button><button type="submit" form="return-flight-form" class="panel-action return" :disabled="saving"><PlaneLanding :size="16"/>{{saving?'正在归档…':'确认返航并归档'}}</button></div></template>
    </FlightSidePanel>

    <AppModal v-if="cancelling" :title="`取消航班 · ${cancelling.voyage_no}`" eyebrow="VOID FLIGHT" :prevent-close="saving" @close="cancelling=null;modalError=''">
      <div class="cancel-confirm">
        <p v-if="modalError" class="error-banner">{{modalError}}</p>
        <strong>确认取消这趟航班？</strong>
        <p>取消后航班会从调度中心移除，舱位恢复待调度。该操作不会生成钱途记录。</p>
        <div class="modal-actions"><button class="secondary" @click="cancelling=null">返回</button><button class="confirm-cancel" :disabled="saving" @click="cancelVoyage">{{saving?'取消中…':'确认取消'}}</button></div>
      </div>
    </AppModal>

    <FlightSidePanel v-if="selected" :title="selected.voyage_no" eyebrow="FLIGHT MANIFEST · 航班运行签派单" :subtitle="`${selected.name} · ${selected.symbol}`" @close="selected=null">
        <template #status><FlightStateBadge :state="selected.runtime_state"/></template>
        <div class="manifest-route"><div><small>DEP</small><strong>{{selected.symbol}}</strong><span>ETF 资金机场</span></div><div class="manifest-airway"><i></i><PlaneTakeoff :size="19"/><em>WEALTH ROUTE</em></div><div><small>ARR</small><strong>WFT</strong><span>财富自由塔台</span></div></div>
        <div class="detail-return">
          <span>当前净收益</span>
          <b :class="{positive:Number(selected.net_return||0)>=0}">{{selected.net_return===null?'—':percent(selected.net_return)}}</b>
          <small>{{stateDescription(selected.runtime_state)}}</small>
        </div>
        <h3 class="manifest-section"><span>OPERATION DATA</span>起航与返航条件</h3>
        <dl class="detail-list">
          <div><dt>目标</dt><dd>{{percent(selected.target_return)}}</dd></div>
          <div><dt>在航份额</dt><dd>{{number(selected.remaining_quantity)}}</dd></div>
          <div><dt>起航价</dt><dd>{{selected.entry_price}}</dd></div>
          <div><dt>监控价</dt><dd>{{selected.monitor_price||'—'}}</dd></div>
          <div><dt>价格截至</dt><dd>{{selected.quote_time?dateTime(selected.quote_time):'等待首个有效价格'}}</dd></div>
          <div><dt>起航时间</dt><dd>{{dateTime(selected.entry_time)}}</dd></div>
          <div><dt>可卖时间</dt><dd>{{dateTime(selected.sellable_at)}}</dd></div>
        </dl>
        <template #footer><p v-if="!canReturn(selected)" class="panel-hint"><Clock3 :size="13"/>{{dateTime(selected.sellable_at)}} 后可返航</p><div class="side-panel-actions three"><button type="button" class="panel-action secondary" @click="openEdit(selected)"><Pencil :size="15"/>改签</button><button type="button" class="panel-action danger" @click="openCancel(selected)"><Trash2 :size="15"/>取消</button><button type="button" class="panel-action return" :disabled="!canReturn(selected)" :title="canReturn(selected)?'填写实际卖出价格并返航':`${dateTime(selected.sellable_at)} 后可返航`" @click="openReturn(selected)"><PlaneLanding :size="16"/>返航</button></div><div class="dispatch-footer"><RadioTower :size="13"/><span>TZX WEALTH CONTROL</span><i></i><b>SLOT {{String(selected.slot_id).padStart(2,'0')}}</b></div></template>
    </FlightSidePanel>
  </div>
</template>

<style scoped>
.voyages-page{max-width:1680px}.ticket-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:18px 16px}
.form-alert{grid-column:1/-1;margin-bottom:0}.modal-actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:9px;margin-top:5px}.modal-actions button,.voyage-actions button{border:0;border-radius:8px;padding:10px 16px;display:inline-flex;align-items:center;justify-content:center;gap:6px;font-size:12px;font-weight:650}.return-summary{grid-column:1/-1;display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:8px;padding:14px;background:#f6f8fa;border-radius:10px}.return-summary div{display:grid;gap:4px}.return-summary span{font-size:9px;color:#89949f}.return-summary b{font-size:12px}.return-note{grid-column:1/-1;margin:0;padding:11px 13px;border-radius:8px;background:#f1f8f5;color:#527266;font-size:10px;line-height:1.6}.return-button,.action-return{background:#168b62;color:#fff}.return-button:hover,.action-return:hover{background:#117451}.confirm-cancel{background:#fff0f0;color:#bd3f45}.cancel-confirm>strong{font-size:16px}.cancel-confirm>p:not(.error-banner){color:#74808c;font-size:12px;line-height:1.7}.cancel-confirm .modal-actions{margin-top:22px}.voyage-actions{display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:8px;margin-top:28px}.voyage-actions button{padding:11px 10px}.action-edit{background:#eef4fc;color:#2866b7}.action-cancel{background:#fff1f1;color:#bd3f45}.voyage-actions button:disabled{background:#f1f3f5;color:#a2aab3;cursor:not-allowed}.success-banner{margin-bottom:14px}
@media(max-width:1439px){.ticket-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}}
@media(max-width:1199px){.ticket-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:899px){.ticket-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:767px){.ticket-grid{grid-template-columns:1fr;gap:13px}.return-summary{grid-template-columns:1fr}.voyage-actions{grid-template-columns:1fr 1fr}.action-return{grid-column:1/-1}}
.settlement-preview{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,1fr);gap:1px;padding:1px;overflow:hidden;border:1px solid #e1ebe6;border-radius:10px;background:#e1ebe6}.settlement-preview>div{display:grid;gap:5px;padding:12px;background:#f6fbf8}.settlement-preview span{color:#85938d;font-size:9px}.settlement-preview b{font-size:13px}.negative{color:var(--beacon-red)!important}.manifest-title{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-top:8px}.manifest-title h2{margin:0}.manifest-title .drawer-name{margin:4px 0 0}.detail-return small{display:block;max-width:250px;margin-top:7px;color:#84909c;font-size:9px;line-height:1.5}.manifest-section{margin:0 0 2px;color:#687687;font-size:10px;font-weight:650}.return-lock{display:flex;justify-content:flex-end;align-items:center;gap:5px;margin:8px 2px 0;color:#8a96a2;font-size:9px}@media(max-width:620px){.settlement-preview{grid-template-columns:1fr}}
.boarding-route{position:relative;grid-column:1/-1;display:grid;grid-template-columns:1fr 1.25fr 1fr;align-items:center;min-height:116px;margin:-4px -2px 2px;padding:20px 28px;border:1px solid #dce6f0;border-radius:12px;background:linear-gradient(120deg,#f5f9ff,#fff 52%,#f3faf7);overflow:hidden}.boarding-route::before,.boarding-route::after{content:"";position:absolute;top:50%;width:18px;height:36px;border:1px solid #dce6f0;border-radius:20px;background:#fff;transform:translateY(-50%)}.boarding-route::before{left:-10px}.boarding-route::after{right:-10px}.boarding-route>div:not(.boarding-airway){display:grid;gap:2px}.boarding-route>div:nth-child(3){text-align:right}.boarding-route small{color:#8292a3;font-size:7px;letter-spacing:.12em}.boarding-route strong{font-size:25px;letter-spacing:.04em}.boarding-route span{color:#6f7e8e;font-size:9px}.boarding-route>b{position:absolute;right:12px;top:8px;color:#d5dfeb;font-size:28px}.boarding-airway{position:relative;display:grid;place-items:center;color:var(--flight-blue)}.boarding-airway i{position:absolute;left:5px;right:5px;border-top:1px dashed #9eb9dc}.boarding-airway svg{position:relative;padding:5px;box-sizing:content-box;border-radius:50%;background:#fff;transform:rotate(8deg)}.boarding-airway em{position:absolute;top:28px;color:#8498ae;font-size:7px;font-style:normal;letter-spacing:.12em}.form-section-title{grid-column:1/-1;margin:3px 0 -4px;padding-bottom:8px;border-bottom:1px solid #e8eef4;color:#617387;font-size:9px;font-weight:700;letter-spacing:.08em}.aviation-form label{position:relative;padding-left:13px}.aviation-form label::before{content:"";position:absolute;left:0;top:2px;bottom:2px;width:2px;border-radius:2px;background:#dce6f2}.aviation-form label:focus-within::before{background:var(--flight-blue)}
.dispatch-stripe{height:43px;display:flex;align-items:center;justify-content:space-between;margin:-38px -32px 27px;padding:0 32px;background:#183e69;color:#d7e5f3}.dispatch-stripe span{font-size:7px;letter-spacing:.13em}.dispatch-stripe b{font-size:8px;letter-spacing:.1em}.manifest-route{display:grid;grid-template-columns:1fr 1.2fr 1fr;align-items:center;margin:22px 0 16px;padding:15px 0;border-top:1px solid #e7edf3;border-bottom:1px solid #e7edf3}.manifest-route>div:not(.manifest-airway){display:grid;gap:2px}.manifest-route>div:last-child{text-align:right}.manifest-route small{color:#91a0ae;font-size:7px}.manifest-route strong{font-size:19px;letter-spacing:.03em}.manifest-route span{color:#788695;font-size:8px}.manifest-airway{position:relative;display:grid;place-items:center;color:var(--flight-blue)}.manifest-airway i{position:absolute;left:4px;right:4px;border-top:1px dashed #9fb7d2}.manifest-airway svg{position:relative;padding:4px;box-sizing:content-box;border-radius:50%;background:#fff;transform:rotate(7deg)}.manifest-airway em{position:absolute;top:25px;color:#95a2af;font-size:6px;font-style:normal;letter-spacing:.08em}.manifest-section{display:flex;align-items:center;justify-content:space-between;margin-top:22px;padding-bottom:8px;border-bottom:1px solid #e7edf3}.manifest-section span{color:#a0abb6;font-size:7px;letter-spacing:.12em}.detail-list div{position:relative}.detail-list div::before{content:"";position:absolute;left:0;bottom:-1px;width:34px;border-bottom:1px solid #a7bdd5}.dispatch-footer{display:flex;align-items:center;gap:7px;margin-top:24px;padding-top:12px;border-top:1px dashed #ccd7e2;color:#8795a3;font-size:7px;letter-spacing:.1em}.dispatch-footer i{flex:1;border-top:1px dotted #ccd7e2}.dispatch-footer b{color:#617387}.drawer-close{color:#dfe9f3;top:8px;right:16px;z-index:2}.drawer-close:hover{color:#fff}.detail-return{margin-top:16px;border-left:3px solid var(--tower-green);border-radius:4px 12px 12px 4px;background:linear-gradient(100deg,#f4f9f7,#f7f9fb)}
.drawer{width:min(500px,94vw);height:100vh;display:flex;flex-direction:column;overflow:hidden;padding:38px 30px 18px}.dispatch-stripe{flex:0 0 42px;margin:-38px -30px 18px;padding:0 66px 0 30px}.drawer>.eyebrow{flex:0 0 auto}.manifest-title{flex:0 0 auto;margin-top:5px}.manifest-title h2{font-size:27px}.manifest-title .drawer-name{margin-top:2px;font-size:12px}.manifest-route{flex:0 0 auto;margin:13px 0 10px;padding:10px 0}.manifest-route strong{font-size:18px}.manifest-route span{font-size:7.5px}.manifest-airway em{top:23px}.detail-return{flex:0 0 auto;display:grid;grid-template-columns:1fr auto;align-items:center;min-height:78px;margin:9px 0 13px;padding:14px 17px}.detail-return>span:first-child{grid-column:1}.detail-return b{grid-column:1;margin-top:2px;font-size:25px}.detail-return small{grid-column:2;grid-row:1/3;max-width:160px;margin:0;padding-left:14px;border-left:1px solid #dfe8e3;line-height:1.45}.manifest-section{flex:0 0 auto;margin:0;padding:0 0 7px}.detail-list{flex:0 0 auto;display:grid;grid-template-columns:1fr 1fr;gap:0 18px;margin:0}.detail-list div{display:grid;grid-template-columns:1fr auto;align-items:center;min-height:45px;padding:8px 1px}.detail-list dt{font-size:10px}.detail-list dd{font-size:11px}.detail-list div::before{width:24px}.voyage-actions{flex:0 0 auto;margin-top:auto;padding-top:14px;border-top:1px dashed #ccd7e2}.voyage-actions button{min-height:38px;padding:8px}.return-lock{flex:0 0 auto;margin-top:6px}.dispatch-footer{flex:0 0 auto;margin-top:10px;padding-top:9px}.drawer-close{top:6px}.drawer .eyebrow{font-size:8px}.drawer .eyebrow,.dispatch-stripe span,.dispatch-stripe b,.dispatch-footer{white-space:nowrap}
.aviation-form{grid-template-columns:repeat(3,minmax(0,1fr));gap:11px 14px}.aviation-form .boarding-route{min-height:88px;margin:0;padding:13px 25px}.aviation-form .boarding-route strong{font-size:21px}.aviation-form .boarding-route>b{font-size:23px}.aviation-form .boarding-airway em{top:25px}.aviation-form .form-section-title{margin:0;padding-bottom:6px}.aviation-form label{gap:5px;font-size:10px}.aviation-form input,.aviation-form select{height:36px;padding:8px 10px;font-size:11px}.aviation-form label small{font-size:8px}.aviation-form .preview-box{padding:10px 12px}.aviation-form .preview-box span{font-size:8px}.aviation-form .preview-box b{font-size:12px}.aviation-form>.full{min-height:38px;margin-top:0}.aviation-form .modal-actions{margin-top:0}.aviation-form .form-alert{margin:0}
.drawer-form{height:100%;grid-template-columns:repeat(2,minmax(0,1fr));align-content:start}.drawer-form .boarding-route,.drawer-form .form-section-title,.drawer-form .preview-box,.drawer-form>.full,.drawer-form .form-alert,.drawer-form .modal-actions{grid-column:1/-1}.drawer-form .preview-box{grid-template-columns:repeat(2,1fr)}.drawer-form .modal-actions{margin-top:auto}.drawer-form>.full{margin-top:5px}
@media(max-width:620px){.boarding-route{grid-template-columns:1fr .75fr 1fr;padding:16px}.boarding-route strong{font-size:19px}.dispatch-stripe{margin-left:-32px;margin-right:-32px}.manifest-route strong{font-size:16px}}
@media(max-height:690px) and (min-width:621px){.drawer{padding-bottom:12px}.dispatch-stripe{margin-bottom:11px}.manifest-route{margin:8px 0 7px;padding:7px 0}.detail-return{min-height:66px;margin:6px 0 9px;padding:10px 14px}.detail-return b{font-size:22px}.detail-list div{min-height:39px;padding:5px 1px}.voyage-actions{padding-top:9px}.dispatch-footer{margin-top:7px;padding-top:6px}}
@media(max-width:620px){.drawer{width:100vw;padding-left:20px;padding-right:20px}.dispatch-stripe{margin-left:-20px;margin-right:-20px;padding-left:20px}.detail-return small{max-width:125px}.detail-list{gap:0 12px}.manifest-route span{display:none}}
@media(max-width:700px){.aviation-form{grid-template-columns:1fr 1fr}.aviation-form .boarding-route{grid-template-columns:1fr .65fr 1fr}.aviation-form label:nth-of-type(3){grid-column:1/-1}}@media(max-width:480px){.aviation-form{grid-template-columns:1fr}.aviation-form label:nth-of-type(3){grid-column:auto}.aviation-form .preview-box{grid-template-columns:1fr 1fr}}
</style>
<style scoped>
.field-with-icon,.input-with-unit{position:relative}.field-with-icon svg{position:absolute;right:11px;top:50%;color:#8090a0;transform:translateY(-50%)}.field-with-icon input{padding-right:34px}.input-with-unit span{position:absolute;right:10px;top:50%;color:#8793a0;font-size:9px;transform:translateY(-50%)}.input-with-unit input{padding-right:31px}.security-result{grid-column:1/-1;display:flex;justify-content:space-between;gap:12px;margin-top:-5px;padding:9px 11px;border:1px solid #dce7f2;border-radius:8px;background:#f6faff;color:#51677e;font-size:9px}.security-result b{color:#71869a;font-weight:550}.return-form{align-content:start}.return-form .return-summary,.return-form .settlement-preview,.return-form .return-note,.return-form .return-route{grid-column:1/-1}.return-note b{color:#226b51}.return-route{margin-bottom:5px}@media(max-height:720px){.boarding-route{min-height:74px!important}.detail-return{min-height:62px;padding:9px 14px}.detail-list div{min-height:38px;padding:5px 1px}.manifest-route{margin:6px 0}.return-summary{padding:9px}.settlement-preview>div{padding:9px}}
</style>
