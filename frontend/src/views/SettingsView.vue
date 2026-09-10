<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,reactive,ref} from 'vue'
import {onBeforeRouteLeave} from 'vue-router'
import {Bell,Coins,Gauge,Landmark,RadioTower,ReceiptText,Save,Wifi} from 'lucide-vue-next'
import {get,post,put} from '../api/client'

type Section='capital'|'return'|'market'|'fees'|'notification'
const sections=[{id:'capital',code:'CAP',label:'资金与舱位',icon:Coins},{id:'return',code:'RTN',label:'返航规则',icon:Landmark},{id:'market',code:'MKT',label:'行情源',icon:RadioTower},{id:'fees',code:'FEE',label:'交易费用',icon:ReceiptText},{id:'notification',code:'COM',label:'通知',icon:Bell}] as const
const active=ref<Section>('capital'),form=reactive<any>({}),message=ref(''),error=ref(''),saving=ref(false),testing=ref(false),snapshot=ref('')
const dirty=computed(()=>snapshot.value!==''&&JSON.stringify(form)!==snapshot.value)
async function load(){try{Object.assign(form,await get('/api/settings'));snapshot.value=JSON.stringify(form)}catch(e){error.value=(e as Error).message}}
async function save(){saving.value=true;message.value='';error.value='';try{Object.assign(form,await put('/api/settings',form));snapshot.value=JSON.stringify(form);message.value='塔台参数已保存，新的规则将在后续监控中生效。'}catch(e){error.value=(e as Error).message}finally{saving.value=false}}
async function testNotification(){testing.value=true;message.value='';error.value='';try{const result=await post<{message:string}>('/api/settings/notification/test');message.value=result.message}catch(e){error.value=(e as Error).message}finally{testing.value=false}}
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue=''}}
onMounted(()=>{load();window.addEventListener('beforeunload',beforeUnload)})
onBeforeUnmount(()=>window.removeEventListener('beforeunload',beforeUnload))
onBeforeRouteLeave(()=>!dirty.value||window.confirm('塔台参数尚未保存，确定放弃修改并离开吗？'))
</script>

<template>
  <div class="page settings-page">
    <p v-if="message" class="success-banner">{{message}}</p><p v-if="error" class="error-banner">{{error}}</p>
    <section class="control-console">
      <div class="console-statusbar"><div class="tower-callsign"><RadioTower :size="15"/><b>TZX WEALTH CONTROL</b><span>财富自由塔台 · 系统控制席</span></div><div class="console-indicators"><span><i class="green"></i>账本在线</span><span><i class="blue"></i>行情链路</span><span><Wifi :size="13"/>LOCAL 127.0.0.1</span></div><strong>119.93°E / 32.46°N</strong></div>
      <aside class="settings-nav">
        <div class="settings-heading"><p class="section-kicker">TOWER CONTROL</p><h1>塔台参数</h1><span>控制资金舱位、返航与行情规则</span></div>
        <label class="mobile-section-select"><span>当前设置分类</span><select v-model="active" aria-label="选择设置分类"><option v-for="item in sections" :key="item.id" :value="item.id">{{item.label}} · {{item.code}}</option></select></label>
        <nav aria-label="设置分类"><button v-for="(item,index) in sections" :key="item.id" type="button" :class="{active:active===item.id}" :aria-pressed="active===item.id" @click="active=item.id"><span>{{String(index+1).padStart(2,'0')}}</span><component :is="item.icon" :size="16"/><b>{{item.label}}</b><small>{{item.code}}</small></button></nav>
        <div class="ledger-note"><i></i><div><b>本地账本运行中</b><span>所有设置保存在本机</span></div></div>
      </aside>

      <form class="settings-workspace" @submit.prevent="save">
        <header><div><p class="section-kicker">CONTROL PARAMETERS · {{sections.find(item=>item.id===active)?.code}}</p><h2>{{sections.find(item=>item.id===active)?.label}}</h2></div><div class="workspace-state"><Gauge :size="15"/><span v-if="dirty" class="unsaved-dot">参数待确认</span><span v-else class="synced-state">参数同步</span></div></header>

        <div v-if="active==='capital'" class="settings-fields">
          <label>总资金<div class="field-suffix"><input v-model="form.total_capital" inputmode="decimal"/><span>元</span></div><small>用于计算可调度资金与舱位占比。</small></label>
          <label>舱位数量<div class="field-suffix"><input v-model.number="form.slot_count" type="number" min="1"/><span>个</span></div><small>每个舱位可独立签发一张资金机票。</small></label>
          <label>默认单舱金额<div class="field-suffix"><input v-model="form.default_slot_amount" inputmode="decimal"/><span>元</span></div><small>新建舱位时采用的默认预算。</small></label>
        </div>
        <div v-else-if="active==='return'" class="settings-fields">
          <label>默认目标收益<input v-model="form.default_target_return" inputmode="decimal"/><small>使用小数保存，例如 0.02 表示 2%。</small></label>
          <label>近进阈值<input v-model="form.near_return_buffer" inputmode="decimal"/><small>达到目标航程约 80% 后进入近进状态。</small></label>
          <label>长航程阈值<div class="field-suffix"><input v-model.number="form.long_voyage_days" type="number" min="1"/><span>天</span></div><small>超过该交易日数量后标记为长航程。</small></label>
        </div>
        <div v-else-if="active==='market'" class="settings-fields">
          <label>行情服务商<select v-model="form.market_provider"><option value="akshare">AKShare</option></select><small>休市期间继续保留最近一次有效收盘价。</small></label>
          <label>行情轮询间隔<div class="field-suffix"><input v-model.number="form.market_poll_interval_seconds" type="number" min="5"/><span>秒</span></div><small>开市期间获取新行情的频率。</small></label>
          <label>盘中异常判定<div class="field-suffix"><input v-model.number="form.market_quote_stale_seconds" type="number" min="1"/><span>秒</span></div><small>仅用于识别服务异常，不改变航班运行状态。</small></label>
          <label>返航参考价格<select v-model="form.return_price_mode"><option value="BID1">买一价</option><option value="LAST">最新价</option></select><small>只用于监控，最终返航仍填写实际成交价。</small></label>
        </div>
        <div v-else-if="active==='fees'" class="settings-fields">
          <label>买入佣金率<input v-model="form.buy_commission_rate" inputmode="decimal"/></label><label>卖出佣金率<input v-model="form.sell_commission_rate" inputmode="decimal"/></label><label>最低买入佣金<div class="field-suffix"><input v-model="form.minimum_buy_commission" inputmode="decimal"/><span>元</span></div></label><label>最低卖出佣金<div class="field-suffix"><input v-model="form.minimum_sell_commission" inputmode="decimal"/><span>元</span></div></label><label>其他买入费率<input v-model="form.other_buy_fee_rate" inputmode="decimal"/></label><label>其他卖出费率<input v-model="form.other_sell_fee_rate" inputmode="decimal"/></label>
        </div>
        <div v-else class="settings-fields">
          <label>通知方式<select v-model="form.notification_provider"><option value="none">关闭</option><option value="console">本地控制台</option><option value="feishu">飞书</option><option value="ntfy">ntfy</option></select><small>选择飞书后，将向群自定义机器人推送告警。</small></label><label>Webhook URL<input v-model="form.notification_webhook_url" type="url" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."/><small>在飞书群中添加“自定义机器人”后复制其 Webhook 地址。</small></label><label class="notification-policy">推送规则<small>仅推送“接近返航”和“可返航”。接近返航每 5 分钟更新一次；可返航每 1 分钟更新一次。</small></label><label v-if="form.notification_provider==='feishu'" class="notification-test">连接测试<button type="button" class="secondary" :disabled="testing||dirty" @click="testNotification">{{testing?'发送中…':'发送测试消息'}}</button><small v-if="dirty">请先保存 Webhook 配置，再发送测试消息。</small><small v-else>测试成功后，行情告警将自动推送至该飞书群。</small></label>
        </div>

        <footer><span>{{dirty?'参数已修改，保存后生效':'当前参数已同步'}}</span><button class="primary" :disabled="saving||!dirty"><Save :size="15"/>{{saving?'保存中…':'保存塔台参数'}}</button></footer>
      </form>
    </section>
  </div>
</template>

<style scoped>
.settings-page{max-width:1280px}.control-console{min-height:620px;display:grid;grid-template-columns:240px minmax(0,1fr);overflow:hidden;border:1px solid var(--line);border-radius:var(--radius-region);background:#fff;box-shadow:0 6px 22px rgba(35,52,71,.04)}.settings-nav{position:static;inset:auto;width:auto;z-index:auto;padding:25px 16px 18px;border:0;border-right:1px solid var(--line-soft);background:#f8fafc}.settings-heading{padding:0 9px 22px}.settings-heading h1{margin:5px 0 4px;font-size:20px}.settings-heading>span{color:#8794a1;font-size:9px;line-height:1.5}.mobile-section-select{display:none}.settings-nav nav{display:grid;gap:4px}.settings-nav nav button{width:100%;display:flex;align-items:center;gap:9px;padding:10px 11px;border:0;border-radius:8px;background:transparent;color:#5e6d7d;font-size:11px;text-align:left}.settings-nav nav button:hover{background:#f0f4f8}.settings-nav nav button.active{background:#eaf2fd;color:var(--flight-blue-strong);font-weight:650}.ledger-note{margin-top:auto;display:flex;align-items:center;gap:8px;padding:14px 9px 0;border-top:1px solid var(--line)}.ledger-note i{width:7px;height:7px;border-radius:50%;background:var(--tower-green);box-shadow:0 0 0 4px rgba(21,149,104,.08)}.ledger-note div{display:grid;gap:2px}.ledger-note b{font-size:9px}.ledger-note span{color:#929da8;font-size:8px}.settings-workspace{min-width:0;display:flex;flex-direction:column}.settings-workspace>header{display:flex;align-items:center;justify-content:space-between;padding:25px 28px 20px;border-bottom:1px solid var(--line-soft)}.settings-workspace h2{margin:5px 0 0;font-size:19px}.unsaved-dot{display:flex;align-items:center;gap:6px;color:var(--approach-amber);font-size:9px}.unsaved-dot::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.settings-fields{display:grid;grid-template-columns:1fr 1fr;align-content:start;gap:22px 26px;padding:30px 28px;flex:1}.settings-fields label{align-content:start}.settings-fields label>small{line-height:1.55}.settings-fields input,.settings-fields select{height:41px}.settings-workspace>footer{display:flex;align-items:center;justify-content:flex-end;gap:15px;padding:16px 28px;border-top:1px solid var(--line-soft);background:#fbfcfd}.settings-workspace>footer>span{margin-right:auto;color:#8b97a3;font-size:9px}.settings-workspace>footer button{min-width:142px}
@media(max-width:820px){.control-console{grid-template-columns:1fr}.settings-nav{border-right:0;border-bottom:1px solid var(--line-soft)}.settings-nav nav{display:flex;overflow:auto}.settings-nav nav button{width:auto;white-space:nowrap}.ledger-note{display:none}.settings-fields{grid-template-columns:1fr}}@media(max-width:520px){.settings-fields,.settings-workspace>header{padding-left:18px;padding-right:18px}.settings-workspace>footer{position:sticky;bottom:0;padding:12px 18px}.settings-workspace>footer>span{display:none}.settings-workspace>footer button{width:100%}}
</style>

<style scoped>
.console-statusbar{grid-column:1/-1;height:48px;display:flex;align-items:center;gap:20px;padding:0 18px;background:#183e69;color:#dce9f5;border-bottom:1px solid #102f52}.tower-callsign{display:flex;align-items:center;gap:8px}.tower-callsign b{font-size:9px;letter-spacing:.1em}.tower-callsign>span{color:#9eb5cb;font-size:8px}.console-indicators{display:flex;align-items:center;gap:16px;margin-left:auto}.console-indicators span{display:flex;align-items:center;gap:5px;color:#b8c9d9;font-size:8px}.console-indicators i{width:5px;height:5px;border-radius:50%;box-shadow:0 0 0 3px rgba(255,255,255,.06)}.console-indicators i.green{background:#36ce93}.console-indicators i.blue{background:#56a3ff}.console-statusbar>strong{padding-left:17px;border-left:1px solid rgba(255,255,255,.16);color:#8facbf;font-size:7px;letter-spacing:.08em}.settings-nav nav button{display:grid;grid-template-columns:22px 18px 1fr auto;gap:7px}.settings-nav nav button>span{color:#a3afbb;font-size:8px;font-variant-numeric:tabular-nums}.settings-nav nav button>b{font-size:11px;text-align:left}.settings-nav nav button>small{color:#a1acb7;font-size:7px;letter-spacing:.09em}.settings-nav nav button.active>span,.settings-nav nav button.active>small{color:#4d79ad}.workspace-state{display:flex;align-items:center;gap:7px;color:#8b98a5}.synced-state{display:flex;align-items:center;gap:5px;color:var(--tower-green);font-size:9px}.synced-state::before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}.settings-fields{counter-reset:control-item}.settings-fields>label{counter-increment:control-item;position:relative;padding:18px 16px 16px;border:1px solid #e0e7ee;border-radius:10px;background:linear-gradient(145deg,#fbfcfd,#f6f8fa);box-shadow:inset 0 1px 0 #fff}.settings-fields>label::before{content:"CTRL " counter(control-item,decimal-leading-zero);position:absolute;right:12px;top:9px;color:#a3afba;font-size:6px;font-weight:700;letter-spacing:.09em}.settings-fields>label::after{content:"";position:absolute;left:16px;right:16px;top:0;height:2px;border-radius:0 0 2px 2px;background:#afbecd}.settings-fields>label:focus-within{border-color:#aac4e2;box-shadow:0 0 0 3px #edf4fb,inset 0 1px 0 #fff}.settings-fields>label:focus-within::after{background:var(--flight-blue)}.settings-fields input,.settings-fields select{background:#fff;border-color:#d6dfe8;font-variant-numeric:tabular-nums}.settings-workspace{background:linear-gradient(#fff,#fbfcfd)}
@media(max-width:820px){.console-statusbar{height:auto;min-height:48px}.console-statusbar>strong,.tower-callsign>span{display:none}.console-indicators span:last-child{display:none}}@media(max-width:520px){.console-indicators span:nth-child(2){display:none}.settings-fields>label{padding-left:13px;padding-right:13px}}
</style>
