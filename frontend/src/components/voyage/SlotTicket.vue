<script setup lang="ts">
import {ChevronRight,Plane,Plus} from 'lucide-vue-next'
import FlightStateBadge from '../FlightStateBadge.vue'
import type {Slot} from '../../types'
import {money,number,percent,stateClass} from '../../utils/format'

const props=defineProps<{slot:Slot}>()
const emit=defineEmits<{activate:[slot:Slot]}>()

function activate(){emit('activate',props.slot)}
</script>

<template>
  <article
    :class="['slot-ticket',slot.voyage?stateClass(slot.voyage.runtime_state):'available']"
    role="button"
    tabindex="0"
    :aria-label="slot.voyage?`查看航次 ${slot.voyage.voyage_no}`:`在舱位 ${slot.slot_no} 新建航次`"
    @click="activate"
    @keydown.enter.prevent="activate"
    @keydown.space.prevent="activate"
  >
    <div class="ticket-main">
      <header class="ticket-header">
        <div class="ticket-number"><strong>{{String(slot.slot_no).padStart(2,'0')}}</strong><small>VOYAGE</small></div>
        <FlightStateBadge v-if="slot.voyage" :state="slot.voyage.runtime_state" compact/>
        <span v-else class="ticket-status available">待调度</span>
      </header>

      <template v-if="slot.voyage">
        <div class="ticket-voyage">
          <div class="voyage-title"><h3>{{slot.voyage.voyage_no}}</h3><ChevronRight :size="17"/></div>
          <div class="security">
            <span>{{slot.voyage.name===slot.voyage.symbol?'ETF 代码':'ETF'}}</span>
            <b>{{slot.voyage.name===slot.voyage.symbol?slot.voyage.symbol:slot.voyage.name}}</b>
            <small v-if="slot.voyage.name!==slot.voyage.symbol">{{slot.voyage.symbol}}</small>
          </div>
          <div class="voyage-snapshot single"><div><span>当前净收益</span><b :class="{positive:Number(slot.voyage.net_return||0)>0,negative:Number(slot.voyage.net_return||0)<0}">{{slot.voyage.net_return===null?'—':percent(slot.voyage.net_return)}}</b></div></div>
          <div class="remaining"><span>剩余份额</span><strong>{{number(slot.voyage.remaining_quantity)}} <small>份</small></strong></div>
        </div>
      </template>

      <div v-else class="ticket-available">
        <span><Plus :size="17"/>新建航次</span>
        <small>签发一张新的资金机票</small>
      </div>

      <footer class="ticket-footer">
        <div><span>{{slot.voyage?'舱位预算':'预算'}}</span><b>{{money(slot.budget_amount)}}</b></div>
        <div v-if="slot.voyage"><span>起航价</span><b>¥{{slot.voyage.entry_price}}</b></div>
      </footer>
    </div>

    <div class="ticket-stub" aria-hidden="true">
      <small>BOARDING</small>
      <span class="stub-plane"><Plane :size="17"/></span>
      <i class="barcode"></i>
    </div>
  </article>
</template>

<style scoped>
.slot-ticket{--ticket-page:#f4f6f8;position:relative;display:grid;grid-template-columns:minmax(0,78%) minmax(52px,22%);min-width:0;height:330px;background:#fff;border:1px solid #dfe5ec;border-radius:13px;box-shadow:0 5px 16px rgba(35,52,71,.055);cursor:pointer;overflow:visible;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease,background .18s ease}.slot-ticket::before,.slot-ticket::after{content:"";position:absolute;top:50%;z-index:3;width:15px;height:30px;background:var(--ticket-page);border:1px solid #dfe5ec;transform:translateY(-50%)}.slot-ticket::before{left:-1px;border-left:0;border-radius:0 18px 18px 0}.slot-ticket::after{right:-1px;border-right:0;border-radius:18px 0 0 18px}.slot-ticket:hover,.slot-ticket:focus-visible{transform:translateY(-2px);border-color:#cbd5e1;box-shadow:0 9px 24px rgba(35,52,71,.09);outline:0}.slot-ticket.danger{border-top:2px solid #dc5b62}.slot-ticket.available{background:#fdfefe;border-style:solid;box-shadow:0 3px 12px rgba(35,52,71,.04)}.ticket-main{min-width:0;display:flex;flex-direction:column;padding:17px 14px 14px}.ticket-header{display:grid;gap:9px;justify-items:start}.ticket-number{display:flex;align-items:center;gap:10px}.ticket-number strong{color:#536477;font-size:25px;line-height:1;font-weight:680;letter-spacing:-.035em}.slot-ticket:not(.available) .ticket-number strong{color:#2465be}.ticket-number small,.ticket-stub>small{color:#91a0ae;font-size:8px;letter-spacing:.09em}.ticket-status{height:23px;display:inline-flex;align-items:center;padding:0 9px;border-radius:999px;font-size:9px;font-weight:650}.ticket-status.available{background:#f0f2f4;color:#707b87}.ticket-status.flight{background:#edf4ff;color:#2e6dc6}.ticket-status.near{background:#fff4df;color:#b86b0c}.ticket-status.ready{background:#eaf7f1;color:#16855b}.ticket-status.danger{background:#fff0f1;color:#c1444b}.ticket-voyage{display:flex;flex:1;flex-direction:column;padding-top:14px;min-height:0}.voyage-title{display:flex;justify-content:space-between;align-items:center;gap:8px}.voyage-title h3{font-size:19px;line-height:1.1;margin:0;letter-spacing:-.025em}.voyage-title svg{color:#82909e}.security{display:grid;margin-top:15px;gap:2px}.security span,.voyage-snapshot span,.remaining>span,.ticket-footer span{color:#8b98a5;font-size:8px}.security b{font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.security small{color:#667788;font-size:10px}.voyage-snapshot{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px}.voyage-snapshot>div{display:grid;gap:3px;min-width:0}.voyage-snapshot b{font-size:10px;white-space:nowrap}.voyage-snapshot b.flight{color:#2f72df}.voyage-snapshot b.near{color:#b86b0c}.voyage-snapshot b.ready{color:#16855b}.voyage-snapshot b.danger,.negative{color:#c1444b}.remaining{display:grid;gap:2px;margin-top:auto}.remaining strong{font-size:17px;letter-spacing:-.02em}.remaining strong small{font-size:9px;color:#778593;font-weight:500}.ticket-available{display:grid;place-content:center;justify-items:center;gap:8px;flex:1;color:#54708e;text-align:center}.ticket-available>span{display:flex;align-items:center;gap:5px;font-size:12px;font-weight:600}.ticket-available>small{color:#a0aab4;font-size:8px}.ticket-footer{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding-top:11px;margin-top:11px;border-top:1px dashed #d9e1e9}.ticket-footer>div{display:grid;gap:3px;min-width:0}.ticket-footer b{font-size:10px;white-space:nowrap}.ticket-stub{position:relative;display:flex;align-items:center;flex-direction:column;padding:18px 8px 14px;border-left:1px dashed #d9e1e9}.stub-plane{margin:auto;color:#9aabba;transform:rotate(35deg)}.barcode{width:42px;height:22px;opacity:.58;background:repeating-linear-gradient(90deg,#64748b 0 1px,transparent 1px 3px,#64748b 3px 5px,transparent 5px 7px)}.positive{color:#16855b!important}
@media(max-width:1439px){.slot-ticket{height:315px}.ticket-main{padding-left:13px;padding-right:12px}.ticket-stub{padding-left:6px;padding-right:6px}}
@media(max-width:767px){.slot-ticket{height:310px;grid-template-columns:minmax(0,80%) minmax(58px,20%)}}
.ticket-status.waiting{background:#f0f2f4;color:#707b87}.voyage-snapshot b.waiting{color:#707b87}
.voyage-snapshot.single{grid-template-columns:1fr}.slot-ticket.waiting::marker{display:none}.slot-ticket.waiting .ticket-main::before{content:"";position:absolute;right:12px;top:14px;width:6px;height:6px;border-radius:50%;background:var(--beacon-red);box-shadow:0 0 0 4px rgba(217,75,84,.1)}.ticket-main{position:relative}
</style>
<style scoped>
.voyage-title h3{font-size:22px;font-variant-numeric:tabular-nums}.ticket-number strong,.remaining strong,.ticket-footer b{font-variant-numeric:tabular-nums}.slot-ticket{border-color:transparent;box-shadow:var(--shadow-ticket)}.slot-ticket::before,.slot-ticket::after{border-color:transparent}.slot-ticket:hover,.slot-ticket:focus-visible{border-color:transparent;box-shadow:var(--shadow-float)}
</style>
<style scoped>
.slot-ticket{height:270px;border-color:var(--line);box-shadow:var(--shadow-ticket)}.slot-ticket::before,.slot-ticket::after{border-color:var(--line);background:var(--canvas-bg)}.slot-ticket:hover,.slot-ticket:focus-visible{border-color:#c6d2de;box-shadow:0 10px 28px rgba(35,52,71,.1)}.ticket-main{padding:16px 14px 13px}.ticket-header{gap:7px}.ticket-number strong{font-size:23px}.ticket-number small,.ticket-stub>small,.security span,.voyage-snapshot span,.remaining>span,.ticket-footer span{font-size:10px}.ticket-status{font-size:10px}.ticket-voyage{padding-top:10px}.voyage-title h3{font-size:19px}.security{margin-top:10px}.security b{font-size:12px}.security small{font-size:11px}.voyage-snapshot{margin-top:10px}.voyage-snapshot b,.ticket-footer b{font-size:12px}.remaining strong{font-size:18px}.ticket-available>span{font-size:13px}.ticket-available>small{font-size:10px}.ticket-footer{padding-top:9px;margin-top:9px}@media(max-width:767px){.slot-ticket{height:auto;min-height:240px}}
</style>
