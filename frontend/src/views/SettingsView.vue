<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,reactive,ref,type Component} from 'vue'
import {onBeforeRouteLeave} from 'vue-router'
import {Bell,ChevronRight,Coins,Landmark,RadioTower,ReceiptText,Save,SlidersHorizontal,WalletCards} from 'lucide-vue-next'
import {get,post,put} from '../api/client'
import AppModal from '../components/AppModal.vue'
import OperationToast from '../components/OperationToast.vue'

type SettingKey='total_capital'|'slot_count'|'default_slot_amount'|'default_target_return'|'near_return_buffer'|'long_voyage_days'|'market_provider'|'market_poll_interval_seconds'|'market_quote_stale_seconds'|'return_price_mode'|'buy_commission_rate'|'sell_commission_rate'|'minimum_buy_commission'|'minimum_sell_commission'|'other_buy_fee_rate'|'other_sell_fee_rate'|'notification'
type SettingItem={key:SettingKey;label:string;description:string;icon:Component}

const groups:{title:string;items:SettingItem[]}[]=[
  {title:'资金与舱位',items:[
    {key:'total_capital',label:'总资金',description:'用于计算可调度资金与舱位占比',icon:WalletCards},
    {key:'slot_count',label:'舱位数量',description:'可同时管理的独立航次数量',icon:Coins},
    {key:'default_slot_amount',label:'默认单舱金额',description:'新建舱位时使用的预算金额',icon:WalletCards},
  ]},
  {title:'收益与交易',items:[
    {key:'default_target_return',label:'目标净收益率',description:'新建航次默认采用的返航目标',icon:Landmark},
    {key:'near_return_buffer',label:'近进提醒区间',description:'接近目标时提前提醒的收益差',icon:Bell},
    {key:'long_voyage_days',label:'长航程阈值',description:'超过该交易日数量后标记为长航程',icon:SlidersHorizontal},
  ]},
  {title:'交易费用',items:[
    {key:'buy_commission_rate',label:'买入佣金率',description:'计入净收益计算的买入佣金比例',icon:ReceiptText},
    {key:'sell_commission_rate',label:'卖出佣金率',description:'计入净收益计算的卖出佣金比例',icon:ReceiptText},
    {key:'minimum_buy_commission',label:'最低买入佣金',description:'单笔买入佣金的最低金额',icon:ReceiptText},
    {key:'minimum_sell_commission',label:'最低卖出佣金',description:'单笔卖出佣金的最低金额',icon:ReceiptText},
    {key:'other_buy_fee_rate',label:'其他买入费率',description:'除佣金外的买入费率',icon:ReceiptText},
    {key:'other_sell_fee_rate',label:'其他卖出费率',description:'除佣金外的卖出费率',icon:ReceiptText},
  ]},
  {title:'行情与监控',items:[
    {key:'market_provider',label:'行情服务商',description:'当前支持的 ETF 实时行情来源',icon:RadioTower},
    {key:'market_poll_interval_seconds',label:'行情轮询间隔',description:'开市期间获取新行情的频率',icon:RadioTower},
    {key:'market_quote_stale_seconds',label:'行情过期判定',description:'超过时限的行情不会触发返航信号',icon:RadioTower},
    {key:'return_price_mode',label:'返航参考价格',description:'只用于监控，最终以实际成交价为准',icon:SlidersHorizontal},
  ]},
  {title:'通知',items:[
    {key:'notification',label:'通知方式与推送',description:'配置飞书、ntfy 或本地通知',icon:Bell},
  ]},
]

const form=reactive<Record<string,any>>({})
const editor=ref<SettingKey|null>(null),message=ref(''),error=ref(''),saving=ref(false),testing=ref(false),snapshot=ref('')
const dirty=computed(()=>snapshot.value!==''&&JSON.stringify(form)!==snapshot.value)
const selected=computed(()=>groups.flatMap(group=>group.items).find(item=>item.key===editor.value))
const defaultTargetPercent=computed({get:()=>form.default_target_return==null?'':String(Number(form.default_target_return)*100),set:value=>{form.default_target_return=String(Number(value||0)/100)}})
const nearReturnPercent=computed({get:()=>form.near_return_buffer==null?'':String(Number(form.near_return_buffer)*100),set:value=>{form.near_return_buffer=String(Number(value||0)/100)}})
const money=(value:unknown)=>value==null||value===''?'未设置':`¥${Number(value).toLocaleString('zh-CN',{maximumFractionDigits:2})}`
const percent=(value:unknown)=>value==null||value===''?'未设置':`${(Number(value)*100).toFixed(2)}%`
function valueFor(key:SettingKey){
  const values:Partial<Record<SettingKey,string>>={
    total_capital:money(form.total_capital),slot_count:form.slot_count==null?'未设置':`${form.slot_count} 个`,default_slot_amount:money(form.default_slot_amount),
    default_target_return:percent(form.default_target_return),near_return_buffer:percent(form.near_return_buffer),long_voyage_days:form.long_voyage_days==null?'未设置':`${form.long_voyage_days} 个交易日`,
    market_provider:form.market_provider==='akshare'?'AKShare':form.market_provider||'未设置',market_poll_interval_seconds:form.market_poll_interval_seconds==null?'未设置':`${form.market_poll_interval_seconds} 秒`,
    market_quote_stale_seconds:form.market_quote_stale_seconds==null?'未设置':`${form.market_quote_stale_seconds} 秒`,return_price_mode:form.return_price_mode==='LAST'?'最新价':'买一价',
    buy_commission_rate:percent(form.buy_commission_rate),sell_commission_rate:percent(form.sell_commission_rate),minimum_buy_commission:money(form.minimum_buy_commission),minimum_sell_commission:money(form.minimum_sell_commission),
    other_buy_fee_rate:percent(form.other_buy_fee_rate),other_sell_fee_rate:percent(form.other_sell_fee_rate),notification:({none:'关闭',console:'本地控制台',feishu:'飞书',ntfy:'ntfy'} as Record<string,string>)[form.notification_provider]||'未设置',
  }
  return values[key]||'未设置'
}
async function load(){try{Object.assign(form,await get('/api/settings'));snapshot.value=JSON.stringify(form)}catch(e){error.value=(e as Error).message}}
async function save(){saving.value=true;message.value='';error.value='';try{Object.assign(form,await put('/api/settings',form));snapshot.value=JSON.stringify(form);message.value='设置已保存，新的规则将在后续监控中生效。';editor.value=null}catch(e){error.value=(e as Error).message}finally{saving.value=false}}
async function testNotification(){testing.value=true;message.value='';error.value='';try{const result=await post<{message:string}>('/api/settings/notification/test');message.value=result.message}catch(e){error.value=(e as Error).message}finally{testing.value=false}}
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue=''}}
onMounted(()=>{load();window.addEventListener('beforeunload',beforeUnload)})
onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload))
onBeforeRouteLeave(()=>!dirty.value||window.confirm('设置尚未保存，确定放弃修改并离开吗？'))
</script>

<template>
  <div class="page settings-page">
    <OperationToast :message="message||error" :type="error?'error':'success'" @close="message='';error=''"/>
    <header class="settings-page-header">
      <div><p class="section-kicker">SETTINGS · 设置</p><h1>设置</h1><p>管理资金、返航规则、行情与通知。点击任一项目即可修改。</p></div>
      <div class="settings-sync" :class="{dirty}"><i></i>{{dirty?'有未保存的修改':'设置已同步'}}</div>
    </header>

    <main class="settings-groups" aria-label="设置项目">
      <section v-for="group in groups" :key="group.title" class="settings-group">
        <h2>{{group.title}}</h2>
        <div class="settings-list">
          <button v-for="item in group.items" :key="item.key" type="button" class="setting-row" @click="editor=item.key">
            <span class="setting-icon"><component :is="item.icon" :size="18"/></span>
            <span class="setting-copy"><b>{{item.label}}</b><small>{{item.description}}</small></span>
            <span class="setting-value">{{valueFor(item.key)}}</span>
            <ChevronRight class="setting-arrow" :size="18"/>
          </button>
        </div>
      </section>
    </main>

    <footer v-if="dirty" class="settings-savebar"><span>设置已修改，保存后会应用到后续监控。</span><button class="primary" :disabled="saving" @click="save"><Save :size="16"/>{{saving?'保存中…':'保存所有修改'}}</button></footer>

    <AppModal v-if="editor&&selected" :title="selected.label" :eyebrow="selected.description" @close="editor=null">
      <form class="setting-editor" @submit.prevent="save">
        <template v-if="editor==='total_capital'"><label>总资金<div class="field-suffix"><input v-model="form.total_capital" autofocus inputmode="decimal"/><span>元</span></div><small>用于计算可调度资金与舱位占比。</small></label></template>
        <template v-else-if="editor==='slot_count'"><label>舱位数量<div class="field-suffix"><input v-model.number="form.slot_count" autofocus type="number" min="1" max="100"/><span>个</span></div><small>每个舱位可独立记录一段航次。</small></label></template>
        <template v-else-if="editor==='default_slot_amount'"><label>默认单舱金额<div class="field-suffix"><input v-model="form.default_slot_amount" autofocus inputmode="decimal"/><span>元</span></div><small>新建舱位时采用的默认预算。</small></label></template>
        <template v-else-if="editor==='default_target_return'"><label>默认目标收益率<div class="field-suffix"><input v-model="defaultTargetPercent" autofocus type="number" inputmode="decimal" min="0.01" step="0.01"/><span>%</span></div><small>直接填写百分数，例如 2 表示 2%。</small></label></template>
        <template v-else-if="editor==='near_return_buffer'"><label>近进提醒区间<div class="field-suffix"><input v-model="nearReturnPercent" autofocus type="number" inputmode="decimal" min="0.01" step="0.01"/><span>%</span></div><small>距离目标收益进入该区间时标记为“接近返航”。</small></label></template>
        <template v-else-if="editor==='long_voyage_days'"><label>长航程阈值<div class="field-suffix"><input v-model.number="form.long_voyage_days" autofocus type="number" min="1"/><span>天</span></div><small>超过该交易日数量后标记为长航程。</small></label></template>
        <template v-else-if="editor==='market_provider'"><label>行情服务商<select v-model="form.market_provider" autofocus><option value="akshare">AKShare</option></select><small>当前版本仅支持 AKShare ETF 行情。</small></label></template>
        <template v-else-if="editor==='market_poll_interval_seconds'"><label>行情轮询间隔<div class="field-suffix"><input v-model.number="form.market_poll_interval_seconds" autofocus type="number" min="5"/><span>秒</span></div><small>开市期间获取新行情的频率。</small></label></template>
        <template v-else-if="editor==='market_quote_stale_seconds'"><label>行情过期判定<div class="field-suffix"><input v-model.number="form.market_quote_stale_seconds" autofocus type="number" min="1"/><span>秒</span></div><small>超过此时限的行情不会触发新的返航信号。</small></label></template>
        <template v-else-if="editor==='return_price_mode'"><label>返航参考价格<select v-model="form.return_price_mode" autofocus><option value="BID1">买一价</option><option value="LAST">最新价</option></select><small>只用于监控，最终返航仍以实际成交价为准。</small></label></template>
        <template v-else-if="editor==='buy_commission_rate'||editor==='sell_commission_rate'||editor==='other_buy_fee_rate'||editor==='other_sell_fee_rate'"><label>费率<div class="field-suffix"><input v-model="form[editor]" autofocus inputmode="decimal"/><span>比例</span></div><small>例如 0.0003 表示万分之三。</small></label></template>
        <template v-else-if="editor==='minimum_buy_commission'||editor==='minimum_sell_commission'"><label>最低佣金<div class="field-suffix"><input v-model="form[editor]" autofocus inputmode="decimal"/><span>元</span></div><small>单笔交易佣金不足该金额时按最低佣金计。</small></label></template>
        <template v-else-if="editor==='notification'"><label>通知方式<select v-model="form.notification_provider" autofocus><option value="none">关闭</option><option value="console">本地控制台</option><option value="feishu">飞书</option><option value="ntfy">ntfy</option></select><small>仅在交易时段推送接近返航和可返航提醒。</small></label><label v-if="form.notification_provider!=='none'">Webhook URL<input v-model="form.notification_webhook_url" type="url" placeholder="https://..."/><small>飞书请填写群自定义机器人的 Webhook 地址；ntfy 请填写主题 URL。</small></label><button v-if="form.notification_provider==='feishu'" type="button" class="secondary test-button" :disabled="testing||dirty" @click="testNotification">{{testing?'发送中…':'发送飞书测试消息'}}</button><p v-if="form.notification_provider==='feishu'&&dirty" class="editor-tip">请先保存 Webhook 配置，再发送测试消息。</p></template>
        <div class="modal-actions"><button type="button" class="secondary" @click="editor=null">取消</button><button class="primary" :disabled="saving||!dirty"><Save :size="15"/>{{saving?'保存中…':'保存修改'}}</button></div>
      </form>
    </AppModal>
  </div>
</template>

<style scoped>
.settings-page{max-width:820px;padding-bottom:104px}.settings-page-header{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:26px}.settings-page-header h1{margin:5px 0 6px;font-size:28px;letter-spacing:-.04em}.settings-page-header p:last-child{margin:0;color:var(--muted-2);font-size:13px}.settings-sync{display:flex;align-items:center;gap:7px;flex:none;color:var(--tower-green);font-size:12px}.settings-sync i{width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 0 4px color-mix(in srgb,currentColor 12%,transparent)}.settings-sync.dirty{color:var(--approach-amber)}.settings-groups{display:grid;gap:24px}.settings-group h2{margin:0 0 8px 4px;color:var(--muted-2);font-size:12px;font-weight:650}.settings-list{overflow:hidden;border:1px solid var(--line);border-radius:14px;background:#fff;box-shadow:var(--shadow-ticket)}.setting-row{width:100%;min-height:72px;display:grid;grid-template-columns:38px minmax(0,1fr) auto 18px;align-items:center;gap:12px;padding:12px 14px;border:0;border-bottom:1px solid var(--line-soft);background:#fff;text-align:left}.setting-row:last-child{border-bottom:0}.setting-row:hover{background:#f8fafc}.setting-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:10px;color:var(--flight-blue);background:var(--flight-blue-soft)}.setting-copy{min-width:0;display:grid;gap:3px}.setting-copy b{color:var(--ink);font-size:14px;font-weight:650}.setting-copy small{overflow:hidden;color:var(--muted-2);font-size:11px;line-height:1.35;text-overflow:ellipsis;white-space:nowrap}.setting-value{max-width:176px;overflow:hidden;color:#617286;font-size:13px;text-align:right;text-overflow:ellipsis;white-space:nowrap}.setting-arrow{color:#a9b5c1}.settings-savebar{position:fixed;z-index:20;bottom:20px;left:50%;width:min(650px,calc(100% - 32px));display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 14px 12px 18px;border:1px solid #d6e1ed;border-radius:14px;background:rgba(255,255,255,.96);box-shadow:0 12px 32px rgba(33,52,73,.16);transform:translateX(-50%);backdrop-filter:blur(12px)}.settings-savebar span{color:#617286;font-size:12px}.setting-editor{display:grid;gap:16px}.setting-editor>label{display:grid;gap:7px}.setting-editor small{color:var(--muted-2);font-size:12px;line-height:1.55}.test-button{justify-self:start}.editor-tip{margin:0;color:var(--approach-amber);font-size:12px}.modal-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:6px;padding-top:16px;border-top:1px solid var(--line-soft)}
@media(max-width:900px){.settings-page-header{align-items:flex-start;flex-direction:column;gap:10px}.settings-page-header h1{font-size:25px}.settings-page-header p:last-child{font-size:12px}.settings-sync{font-size:11px}.settings-groups{gap:20px}.settings-group h2{margin-left:2px}.settings-savebar{bottom:calc(74px + env(safe-area-inset-bottom));width:calc(100% - 28px)}.settings-savebar span{display:none}.settings-savebar button{width:100%;min-height:46px}.setting-row{min-height:68px;padding:11px 12px;gap:10px}.setting-value{max-width:115px;font-size:12px}.setting-copy small{white-space:normal}.modal-actions{display:grid;grid-template-columns:1fr 1.2fr}.modal-actions button{min-height:46px}}
@media(max-width:390px){.setting-row{grid-template-columns:35px minmax(0,1fr) auto 15px;gap:8px}.setting-icon{width:32px;height:32px}.setting-copy small{display:none}.setting-value{max-width:98px}.settings-page-header p:last-child{display:none}}
</style>
