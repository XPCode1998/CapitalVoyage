<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {AlertTriangle,Plane,RadioTower,X} from 'lucide-vue-next'
import {geoGraticule10,geoNaturalEarth1,geoPath} from 'd3-geo'
import {feature,mesh} from 'topojson-client'
import world from 'world-atlas/countries-110m.json'
import type {DashboardAirport,DashboardRoute,FlightVisualState} from '../../types'
import {dateTime,number,percent} from '../../utils/format'

const props=defineProps<{airports:DashboardAirport[];routes:DashboardRoute[];selectedRouteId?:number|null}>()
const emit=defineEmits<{openManifest:[id:number];selectRoute:[id:number];hoverRoute:[id:number|null]}>()
const width=1200,height=560
const atlas=world as any
const worldLand=feature(atlas,atlas.objects.land) as any
const worldBorders=mesh(atlas,atlas.objects.countries,(a,b)=>a!==b) as any
const projection=geoNaturalEarth1().fitExtent([[20,35],[width-20,height-35]],worldLand)
const pathGenerator=geoPath(projection)
const worldLandPath=pathGenerator(worldLand)||''
const worldBordersPath=pathGenerator(worldBorders)||''
const graticulePath=pathGenerator(geoGraticule10())||''
const taizhouPoint=projection([119.929,32.46])||[880,235]
const wealth={x:taizhouPoint[0],y:taizhouPoint[1]}
const selectedId=ref<number|null>(null)
const hoveredId=ref<number|null>(null)
const activeFilter=ref<'ALL'|FlightVisualState>('ALL')

type Point={x:number;y:number}
type AirportLayout={airport:DashboardAirport;x:number;y:number;right:boolean}
type RouteLayout={route:DashboardRoute;path:string;plane:Point;angle:number;color:string;progress:number;grounded:boolean}

const colors:Record<FlightVisualState,string>={PARKED_NEGATIVE:'#d9484f',FLYING:'#4c86d9',APPROACHING:'#e9972d',ARRIVED_LOCKED:'#8068c9',READY:'#23956b',WAITING_QUOTE:'#9aa5b1'}
const filterChips=computed(()=>[
  {id:'ALL' as const,label:'全部',count:props.routes.length},
  {id:'PARKED_NEGATIVE' as const,label:'等待起飞',count:props.routes.filter(r=>r.visual_state==='PARKED_NEGATIVE').length},
  {id:'FLYING' as const,label:'巡航',count:props.routes.filter(r=>r.visual_state==='FLYING'||r.visual_state==='WAITING_QUOTE').length},
  {id:'APPROACHING' as const,label:'进近',count:props.routes.filter(r=>r.visual_state==='APPROACHING'||r.visual_state==='ARRIVED_LOCKED').length},
  {id:'READY' as const,label:'已着陆',count:props.routes.filter(r=>r.visual_state==='READY').length},
])
const filteredRoutes=computed(()=>activeFilter.value==='ALL'?props.routes:props.routes.filter(route=>{
  if(activeFilter.value==='FLYING')return route.visual_state==='FLYING'||route.visual_state==='WAITING_QUOTE'
  if(activeFilter.value==='APPROACHING')return route.visual_state==='APPROACHING'||route.visual_state==='ARRIVED_LOCKED'
  return route.visual_state===activeFilter.value
}))
const positionSets:Record<number,Point[]>={
  1:[{x:300,y:275}],
  2:[{x:240,y:150},{x:360,y:430}],
  3:[{x:180,y:115},{x:235,y:425},{x:1060,y:90}],
  4:[{x:170,y:100},{x:210,y:425},{x:1060,y:85},{x:1060,y:425}]
}
const ringPositions:Point[]=[{x:145,y:85},{x:145,y:430},{x:385,y:55},{x:385,y:475},{x:1060,y:70},{x:1060,y:430},{x:735,y:55},{x:735,y:475},{x:75,y:270},{x:1100,y:310}]

const airportLayouts=computed<AirportLayout[]>(()=>{
  const positions=positionSets[props.airports.length]||ringPositions
  return props.airports.map((airport,index)=>{
    const point=positions[index%positions.length]
    return {airport,...point,right:point.x>wealth.x}
  })
})

const routeLayouts=computed<RouteLayout[]>(()=>{
  const airportBySymbol=new Map(airportLayouts.value.map(item=>[item.airport.symbol,item]))
  const totals=new Map<string,number>()
  const seen=new Map<string,number>()
  filteredRoutes.value.forEach(route=>totals.set(route.symbol,(totals.get(route.symbol)||0)+1))
  return filteredRoutes.value.map((route,index)=>{
    const airport=airportBySymbol.get(route.symbol)!
    const lane=seen.get(route.symbol)||0
    seen.set(route.symbol,lane+1)
    const laneCount=totals.get(route.symbol)||1
    const laneOffset=(lane-(laneCount-1)/2)*13
    const vx=wealth.x-airport.x,vy=wealth.y-airport.y
    const length=Math.hypot(vx,vy)||1
    const ux=vx/length,uy=vy/length
    const px=-uy,py=ux
    const start={x:airport.x+ux*40+px*laneOffset,y:airport.y+uy*40+py*laneOffset}
    const end={x:wealth.x-ux*78+px*laneOffset*.25,y:wealth.y-uy*78+py*laneOffset*.25}
    const bend=(index%2===0?-1:1)*(32+Math.abs(laneOffset)*.8)
    const control={x:(start.x+end.x)/2+px*bend,y:(start.y+end.y)/2+py*bend}
    const path=`M ${start.x} ${start.y} Q ${control.x} ${control.y} ${end.x} ${end.y}`
    const progress=Math.min(Math.max(Number(route.progress)||0,0),1)
    const grounded=route.visual_state==='PARKED_NEGATIVE'
    // A ready voyage has reached the terminal rather than remaining mid-route.
    const t=grounded ? 0 : route.visual_state === 'READY' ? 1 : progress
    const omt=1-t
    const plane={x:omt*omt*start.x+2*omt*t*control.x+t*t*end.x,y:omt*omt*start.y+2*omt*t*control.y+t*t*end.y}
    const dx=2*omt*(control.x-start.x)+2*t*(end.x-control.x)
    const dy=2*omt*(control.y-start.y)+2*t*(end.y-control.y)
    return {route,path,plane,angle:Math.atan2(dy,dx)*180/Math.PI,color:colors[route.visual_state],progress,grounded}
  })
})

const selectedRoute=computed(()=>props.routes.find(route=>route.id===selectedId.value)||null)
const hoveredLayout=computed(()=>routeLayouts.value.find(layout=>layout.route.id===hoveredId.value)||null)
watch(()=>props.routes,()=>{if(selectedId.value&&!selectedRoute.value)selectedId.value=null})
watch(()=>props.selectedRouteId,id=>{if(id!==undefined)selectedId.value=id})
function selectRoute(id:number){selectedId.value=id;emit('selectRoute',id)}
function hoverRoute(id:number|null){hoveredId.value=id;emit('hoverRoute',id)}

function visualLabel(state:FlightVisualState){return {PARKED_NEGATIVE:'等待起飞',FLYING:'巡航',APPROACHING:'近进',ARRIVED_LOCKED:'着陆待解锁',READY:'着陆',WAITING_QUOTE:'巡航'}[state]}
function airportName(name:string){const match=name.match(/^(.{1,10}?ETF)/i);return match?.[1]||name.slice(0,12)}
</script>

<template>
  <section class="flight-monitor">
    <header class="monitor-header">
      <div><h2>财富航线 <small><i></i>实时</small></h2><p>资金航次实时运行态势</p></div>
      <div class="legend" aria-label="航班状态筛选">
        <button v-for="chip in filterChips" :key="chip.id" type="button" :class="{active:activeFilter===chip.id}" :aria-pressed="activeFilter===chip.id" @click="activeFilter=chip.id"><i :class="chip.id==='ALL'?'all':chip.id.toLowerCase()"></i>{{chip.label}} <b>{{chip.count}}</b></button>
      </div>
    </header>

    <div v-if="!routes.length" class="empty network-empty"><Plane :size="28"/><b>目前没有在航航班</b><span>新建航次后，这里会生成通往财富自由塔台的航线。</span></div>

    <div v-else class="network-wrap">
      <div class="airspace-stamp"><span>TZX CONTROL</span><b>资金航线态势 <small>WEALTH AIRSPACE · SECTOR 01</small></b></div>
      <div class="map-scale"><i></i><span>CAPITAL ROUTE MONITOR</span><i></i></div>
      <svg class="network" :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="ETF 机场汇聚财富自由塔台的实时航线图">
        <defs>
          <radialGradient id="hub-glow"><stop offset="0" stop-color="#dff5ea" stop-opacity=".8"/><stop offset="1" stop-color="#dff5ea" stop-opacity="0"/></radialGradient>
          <filter id="map-shadow" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#37526f" flood-opacity=".12"/></filter>
        </defs>
        <rect width="1200" height="560" rx="15" fill="#f8fbfe"/>
        <path class="geo-grid" :d="graticulePath" aria-hidden="true"/>
        <path class="world-land" :d="worldLandPath" aria-hidden="true"/>
        <path class="country-borders" :d="worldBordersPath" aria-hidden="true"/>
        <g class="airway-nodes" aria-hidden="true"><circle cx="285" cy="205" r="2"/><circle cx="475" cy="125" r="2"/><circle cx="532" cy="350" r="2"/><circle cx="685" cy="92" r="2"/><circle cx="950" cy="270" r="2"/><circle cx="1010" cy="175" r="2"/></g>

        <g v-for="layout in routeLayouts" :key="layout.route.id" class="route-group" :class="{muted:selectedId!==null&&selectedId!==layout.route.id}">
          <path :d="layout.path" class="route-base"/>
          <path v-if="!layout.grounded&&layout.progress>0" :d="layout.path" pathLength="100" class="route-progress" :class="{waiting:layout.route.visual_state==='WAITING_QUOTE'}" :stroke="layout.color" :stroke-dasharray="`${layout.progress*100} 100`"/>
          <g class="plane-node" :class="{grounded:layout.grounded,selected:selectedId===layout.route.id,muted:hoveredId!==null&&hoveredId!==layout.route.id}" :transform="`translate(${layout.plane.x} ${layout.plane.y}) rotate(${layout.angle+45}) scale(1.42)`" role="button" tabindex="0" :aria-pressed="selectedId===layout.route.id" @click.stop="selectRoute(layout.route.id)" @mouseenter="hoverRoute(layout.route.id)" @mouseleave="hoverRoute(null)" @focus="hoverRoute(layout.route.id)" @blur="hoverRoute(null)" @keydown.enter.prevent="selectRoute(layout.route.id)" @keydown.space.prevent="selectRoute(layout.route.id)">
            <circle r="17" fill="transparent"/>
            <path transform="translate(-12 -12)" d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" :fill="layout.grounded?'#7f8a96':layout.color"/>
            <title>{{layout.route.voyage_no}} · {{layout.route.name}} · {{visualLabel(layout.route.visual_state)}}</title>
          </g>
        </g>

        <g v-for="layout in airportLayouts" :key="layout.airport.symbol" class="airport-node" :transform="`translate(${layout.x} ${layout.y})`">
          <circle v-if="layout.airport.alarm" class="alarm-ring" r="17"/>
          <circle r="14" :class="layout.airport.status==='WAITING'?'beacon waiting':'beacon'"/>
          <circle v-if="layout.airport.alarm" r="4" class="alarm-core"/>
          <g class="tower" transform="translate(-11 -11) scale(.92)"><path d="M18.2 12.27 20 6H4l1.8 6.27a1 1 0 0 0 .95.73h10.5a1 1 0 0 0 .96-.73Z"/><path d="M8 13v9M16 22v-9M9 6l1 7M15 6l-1 7M12 6V2M13 2h-2"/></g>
          <text :x="layout.right?32:-32" y="-6" :text-anchor="layout.right?'start':'end'" class="airport-name">{{airportName(layout.airport.name)}}<title>{{layout.airport.name}}</title></text>
          <text :x="layout.right?32:-32" y="14" :text-anchor="layout.right?'start':'end'" class="airport-meta">{{layout.airport.symbol}} · {{layout.airport.flight_count}} 架</text>
        </g>

        <g class="wealth-terminal" :transform="`translate(${wealth.x} ${wealth.y})`">
          <circle r="84" fill="url(#hub-glow)"/>
          <circle r="64" class="terminal-ring outer"/>
          <circle r="47" class="terminal-ring middle"/>
          <circle r="30" fill="rgba(255,255,255,.92)" stroke="#65aa89" stroke-width="1.4" filter="url(#map-shadow)"/>
          <g class="hub-dollar" transform="translate(-14 -14) scale(1.16)"><line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></g>
          <text text-anchor="middle" y="49" class="wealth-name">财富自由塔台</text>
        </g>
      </svg>
      <div v-if="hoveredLayout" class="flight-tooltip" :style="{left:`${hoveredLayout.plane.x/width*100}%`,top:`${hoveredLayout.plane.y/height*100}%`}"><b>{{hoveredLayout.route.voyage_no}}</b><span>{{hoveredLayout.route.name}}</span><small>{{visualLabel(hoveredLayout.route.visual_state)}} · {{hoveredLayout.route.net_return===null?'收益待更新':percent(hoveredLayout.route.net_return)}}</small></div>

      <Transition name="flight-glass">
        <div v-if="selectedRoute" class="flight-popover" role="region" aria-label="航班具体信息">
          <button class="glass-close" aria-label="关闭航次详情" @click="selectedId=null"><X :size="17"/></button>
          <div class="selected-flight-strip">
            <section class="strip-identity"><span class="selected-icon"><RadioTower :size="25"/></span><div><small>选中航次 <em>SELECTED FLIGHT</em></small><strong>{{selectedRoute.voyage_no}}</strong><p>{{selectedRoute.name}}｜{{selectedRoute.symbol}}</p></div></section>
            <section class="strip-metric"><small>当前收益 <em>CURRENT YIELD</em></small><strong :class="Number(selectedRoute.net_return||0)<0?'negative':'positive'">{{selectedRoute.net_return===null?'—':percent(selectedRoute.net_return)}}</strong></section>
            <section class="strip-metric"><small>在航份额 <em>IN-FLIGHT SHARES</em></small><strong>{{number(selectedRoute.remaining_quantity)}}</strong></section>
            <section class="strip-route"><small>航线进度 <em>ROUTE PROGRESS</em></small><div class="route-track"><i :style="{width:`${Math.max(Number(selectedRoute.progress_percent),8)}%`,background:colors[selectedRoute.visual_state]}"></i><span class="route-stop departure">起飞<em>{{dateTime(selectedRoute.entry_time)}}</em></span><span class="route-stop cruise">巡航<em>进行中</em></span><span class="route-stop approach">进近<em>{{Math.round(Number(selectedRoute.progress_percent))}}%</em></span><span class="route-stop landing" :class="{active:selectedRoute.visual_state==='READY'}">着陆<em>{{selectedRoute.visual_state==='READY'?'已完成':'待达成'}}</em></span></div></section>
            <section class="strip-status"><small>状态 <em>STATUS</em></small><b :style="{color:colors[selectedRoute.visual_state],background:`${colors[selectedRoute.visual_state]}16`}"><RadioTower :size="22"/>{{visualLabel(selectedRoute.visual_state)}}<span>{{selectedRoute.visual_state==='READY'?'LANDED':'IN FLIGHT'}}</span></b></section>
          </div>
        </div>
      </Transition>
    </div>

    <div v-if="routes.length" class="mobile-flight-list">
      <article v-for="airport in airports" :key="airport.symbol" :class="{alarm:airport.alarm,waiting:airport.status==='WAITING'}">
        <header><span class="mobile-airport-icon"><RadioTower :size="16"/></span><div><b>{{airport.name}}</b><small>{{airport.symbol}} · {{airport.flight_count}} 架航班</small></div><AlertTriangle v-if="airport.alarm" :size="17"/></header>
        <button v-for="route in routes.filter(item=>item.symbol===airport.symbol)" :key="route.id" @click="selectedId=route.id"><span><Plane :size="15"/>{{route.voyage_no}}</span><i><em :style="{width:`${Number(route.progress_percent)}%`,background:colors[route.visual_state]}"></em></i><strong :style="{color:colors[route.visual_state]}">{{route.visual_state==='PARKED_NEGATIVE'?percent(route.net_return):`${Math.round(Number(route.progress_percent))}%`}}</strong><small>{{visualLabel(route.visual_state)}}</small></button>
      </article>
    </div>
  </section>
</template>

<style scoped>
.flight-monitor{padding:0;overflow:hidden;margin-bottom:12px}.monitor-header{padding:15px 19px 12px;display:flex;justify-content:space-between;align-items:center;gap:20px}.monitor-header h2{font-size:18px;margin:0 0 3px}.monitor-header p{font-size:11px;color:#89939e;margin:0}.legend{display:flex;align-items:center;gap:14px;flex-wrap:wrap;justify-content:flex-end;color:#65717e;font-size:10px}.legend span{display:flex;align-items:center;gap:5px}.legend span>i{width:7px;height:7px;border-radius:50%}.legend .ground{background:#9aa5b1}.legend .arrived{background:#23956b}.legend .blue{color:#4c86d9}.legend .amber{color:#e9972d}.legend small{display:flex;align-items:center;gap:5px;color:#a06a6d}.legend small i{width:6px;height:6px;border-radius:50%;background:#d9484f;box-shadow:0 0 0 4px rgba(217,72,79,.1)}.network-wrap{position:relative;margin:0 10px 10px}.network{display:block;width:100%;height:auto;max-height:520px}.geo-grid path{fill:none;stroke:#a9bfd5;stroke-width:1;opacity:.12}.world-map{fill:#9fbad2;stroke:#7fa1bf;stroke-width:1.2;opacity:.055}.route-group,.airport-node{transition:opacity .2s}.route-base{fill:none;stroke:#aebbc8;stroke-width:1.25;stroke-dasharray:4 7;opacity:.48}.route-progress{fill:none;stroke-width:2.1;stroke-linecap:round;opacity:.72}.route-progress.stale{stroke-dasharray:3 7;opacity:.55}.plane-node{cursor:pointer;outline:none}.plane-node:hover circle,.plane-node:focus circle{stroke-width:2.4}.plane-node.grounded circle{stroke-dasharray:2 3}.flight-label rect{fill:rgba(255,255,255,.92);stroke:#e2e8ee}.flight-label text{fill:#64717e;font-size:9.5px;font-weight:700}.flight-label.negative rect{stroke:#efc5c7;fill:#fff8f8}.flight-label.negative text{fill:#c43c43}.airport-node{cursor:pointer;outline:none}.airport-hover{fill:rgba(255,255,255,0);stroke:transparent;transition:.2s}.airport-node:hover .airport-hover,.airport-node.selected .airport-hover{fill:rgba(255,255,255,.84);stroke:#dfe7ef;filter:drop-shadow(0 5px 9px rgba(40,62,83,.09))}.beacon{fill:#e8f0fb;stroke:#4c86d9;stroke-width:1.4}.beacon.stale{fill:#f0f2f4;stroke:#9aa5b1}.tower{fill:none;stroke:#647b91;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}.airport-name{fill:#273747;font-size:11.5px;font-weight:750}.airport-meta{fill:#8a96a2;font-size:9.5px}.airport-alert{fill:#c83e45;font-size:9px;font-weight:700}.alarm-ring{fill:none;stroke:#d9484f;stroke-width:1.2;animation:alarm-pulse 1.8s ease-out infinite}.alarm-core{fill:#d9484f}.terminal-ring{fill:none;stroke:#6eb492}.terminal-ring.outer{stroke-width:1;stroke-dasharray:3 7;opacity:.27}.terminal-ring.middle{stroke-width:1.2;opacity:.35}.wealth-name{fill:#17372a;font-size:12.5px;font-weight:800}.wealth-en{fill:#7d958a;font-size:8px;font-weight:700;letter-spacing:.16em}.wealth-target{fill:#23956b;font-size:9px;font-weight:800}.muted{opacity:.14}.flight-popover{position:absolute;right:14px;top:14px;width:230px;background:rgba(255,255,255,.97);border:1px solid #dfe6ed;border-radius:13px;padding:15px;box-shadow:0 15px 38px rgba(35,55,75,.16);z-index:3}.flight-popover>button{position:absolute;right:9px;top:9px;border:0;background:transparent;color:#85909b}.flight-popover>p{margin:0;color:#8b96a1;font-size:9px;font-weight:700;letter-spacing:.1em}.flight-popover h3{margin:5px 24px 5px 0;font-size:14px}.flight-popover h3 small{font-weight:400;color:#8b96a1}.popover-return{font-size:23px;font-weight:800;margin:8px 0}.popover-return.negative{color:#d9484f}.flight-popover dl{margin:0}.flight-popover dl div{display:flex;justify-content:space-between;padding:5px 0;border-top:1px solid #edf0f3;font-size:9.5px}.flight-popover dt{color:#87919c}.flight-popover dd{margin:0;font-weight:700}.network-empty{display:grid;gap:7px;place-items:center}.network-empty svg{color:#7d91a5}.network-empty b{color:#465361}.network-empty span{font-size:10px}.mobile-flight-list{display:none}@keyframes alarm-pulse{0%{r:11px;opacity:.8}100%{r:23px;opacity:0}}@media(prefers-reduced-motion:reduce){.alarm-ring{animation:none}}@media(max-width:900px){.monitor-header{align-items:flex-start;display:grid}.legend{justify-content:flex-start}.network-wrap{height:0;margin:0}.network{display:none}.mobile-flight-list{display:grid;gap:9px;padding:0 10px 10px}.mobile-flight-list article{border:1px solid #dfe6ed;border-radius:11px;overflow:hidden;background:#fff}.mobile-flight-list article.alarm{border-color:#f0b9bc}.mobile-flight-list article.stale{opacity:.72}.mobile-flight-list article>header{display:flex;align-items:center;gap:8px;padding:10px;background:#f7f9fb}.mobile-flight-list header div{display:grid;gap:2px;flex:1}.mobile-flight-list header b{font-size:12px}.mobile-flight-list header small{font-size:9px;color:#86919c}.mobile-flight-list article.alarm>header{color:#bf343a;background:#fff3f3}.mobile-airport-icon{width:27px;height:27px;display:grid;place-items:center;border-radius:50%;background:#eaf1fd;color:#2869d8}.mobile-flight-list button{border:0;border-top:1px solid #edf0f3;background:#fff;width:100%;padding:9px 11px;display:grid;grid-template-columns:105px 1fr 45px;align-items:center;gap:8px;text-align:left}.mobile-flight-list button span{display:flex;align-items:center;gap:5px;font-size:10px;font-weight:700}.mobile-flight-list button i{height:4px;background:#edf0f3;border-radius:4px;overflow:hidden}.mobile-flight-list button em{display:block;height:100%;border-radius:4px}.mobile-flight-list button strong{text-align:right;font-size:10px}.mobile-flight-list button small{grid-column:1/-1;color:#8a949e;font-size:9px}.flight-popover{position:fixed;inset:auto 16px 16px;width:auto;z-index:40}}
</style>
<style scoped>
@media(min-width:901px){
  .flight-monitor{border-color:#d8e2ec;box-shadow:0 10px 32px rgba(40,62,85,.045)}
  .monitor-header{right:22px;top:18px}.legend{gap:19px;font-size:12px;font-weight:550}.legend span{gap:7px}.legend span>i{width:8px;height:8px}.legend small{gap:7px;font-size:11px}.legend small i{width:7px;height:7px}
  .network-wrap{overflow:hidden;border-radius:14px}.network{width:100%;height:100%}
  .airspace-stamp{position:absolute;left:22px;top:18px;z-index:2;display:grid;gap:3px;padding-left:11px;border-left:2px solid #5d88ba;color:#6e8298;pointer-events:none}.airspace-stamp span{font-size:9px;font-weight:800;letter-spacing:.16em}.airspace-stamp b{font-size:11px;font-weight:650;letter-spacing:.04em}
  .map-scale{position:absolute;left:50%;bottom:15px;z-index:2;display:flex;align-items:center;gap:9px;color:#8a9baa;font-size:9px;font-weight:650;letter-spacing:.12em;transform:translateX(-50%);pointer-events:none}.map-scale i{width:44px;border-top:1px solid #a8bacb}.map-scale i:last-child{width:12px}
  .airport-name{font-size:14px;font-weight:720}.airport-meta{font-size:11.5px}.wealth-name{font-size:14px;font-weight:750}.route-base{stroke-width:1.55}.route-progress{stroke-width:2.8}.tower{stroke-width:1.6}
  .glass-main small,.glass-details dt{font-size:10px}.glass-etf b{font-size:14px}.glass-etf span{font-size:10px}.glass-return strong{font-size:20px}.glass-progress b,.glass-state b{font-size:13px}.glass-details dd{font-size:12px}.glass-manifest{padding:8px 11px;font-size:10px}
}
@media(max-width:900px){.airspace-stamp,.map-scale{display:none}.monitor-header h2{font-size:18px}.monitor-header p{font-size:12px}.legend{font-size:11px}.mobile-flight-list header b{font-size:14px}.mobile-flight-list header small{font-size:11px}.mobile-flight-list button{min-height:49px}.mobile-flight-list button span,.mobile-flight-list button strong{font-size:12px}.mobile-flight-list button small{font-size:10px}}
</style>
<style scoped>
.glass-manifest{position:relative;z-index:2;float:right;display:inline-flex;align-items:center;gap:5px;margin-top:8px;padding:6px 9px;border:0;border-radius:7px;background:rgba(35,96,179,.08);color:#245fae;font-size:9px;font-weight:700}.glass-manifest:hover{background:rgba(35,96,179,.14)}
</style>

<style scoped>
.flight-monitor{background:#f8fbfe;border:1px solid #dfe7ef;border-radius:14px;margin-bottom:10px;box-shadow:0 8px 30px rgba(49,70,92,.035)}
.monitor-header{padding:14px 18px 10px;background:linear-gradient(180deg,rgba(255,255,255,.72),rgba(248,251,254,.15))}
.monitor-header h2{font-size:16px;font-weight:650}
.monitor-header h2 small{display:inline-flex;align-items:center;gap:5px;margin-left:9px;color:#4f8f72;font-size:9px;font-weight:600;vertical-align:middle}
.monitor-header h2 small i{width:5px;height:5px;border-radius:50%;background:#2aa172;box-shadow:0 0 0 4px rgba(42,161,114,.09)}
.network-wrap{margin:0}
.network{max-height:560px}
.geo-grid path{stroke:#b3c5d7;opacity:.2}
.world-map{fill:#dfe7ef;stroke:#cbd8e4;stroke-width:1;opacity:.58}
.airway-nodes{fill:#b2c2d1;opacity:.42}
.route-base{stroke:#aab8c6;stroke-width:1.35;opacity:.52}
.route-progress{stroke-width:2.25;opacity:.78}
.airport-name{font-size:11.5px;font-weight:650}
.airport-meta{font-size:9.5px;letter-spacing:.03em}
.wealth-name{font-size:12px;font-weight:700}
@media(max-width:900px){.flight-monitor{background:#fff}.monitor-header{background:#fff}.network-wrap{height:0}}
</style>

<style scoped>
@media(min-width:901px){.flight-monitor{position:relative}.monitor-header{position:absolute;right:16px;top:13px;z-index:2;padding:0;background:transparent}.monitor-header>div:first-child{display:none}.legend{gap:16px}.network-wrap{height:100%;margin:0}.network{height:100%;max-height:none}}
</style>

<style scoped>
.geo-grid{fill:none;stroke:#b7c8d9;stroke-width:.7;opacity:.26}.world-land{fill:#e5ebf2;stroke:#d3dee8;stroke-width:.75;opacity:.86}.country-borders{fill:none;stroke:#d4dee8;stroke-width:.5;opacity:.72}.hub-dollar{fill:none;stroke:#23956b;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}.plane-node path{filter:drop-shadow(0 2px 2px rgba(42,64,86,.16))}.airport-name{paint-order:stroke;stroke:#f8fbfe;stroke-width:3px;stroke-linejoin:round}.airport-meta{paint-order:stroke;stroke:#f8fbfe;stroke-width:2.5px;stroke-linejoin:round}
</style>

<style scoped>
.plane-node{transition:transform .9s cubic-bezier(.22,.72,.2,1)}
.airport-node{cursor:default}
.route-progress.waiting{stroke-dasharray:3 7;opacity:.55}.beacon.waiting{fill:#f0f2f4;stroke:#9aa5b1}.mobile-flight-list article.waiting{opacity:.78}
</style>

<style scoped>
.plane-node.selected path{filter:drop-shadow(0 0 5px rgba(47,114,223,.55))}.flight-popover{position:absolute;inset:auto 22px 18px;width:auto;padding:15px 20px 13px;border:1px solid rgba(255,255,255,.72);border-radius:19px;background:linear-gradient(135deg,rgba(255,255,255,.78),rgba(239,247,255,.58) 48%,rgba(255,255,255,.7));box-shadow:0 18px 50px rgba(41,67,94,.18),inset 0 1px 0 rgba(255,255,255,.9),inset 0 -1px 0 rgba(190,208,224,.3);backdrop-filter:blur(24px) saturate(145%);-webkit-backdrop-filter:blur(24px) saturate(145%);overflow:hidden;z-index:4}.flight-popover::before{content:"";position:absolute;inset:-70% 48% 38% -8%;background:radial-gradient(circle,rgba(255,255,255,.92),rgba(196,224,250,.16) 47%,transparent 70%);pointer-events:none}.flight-popover::after{content:"";position:absolute;inset:1px;border-radius:18px;border:1px solid rgba(255,255,255,.38);pointer-events:none}.glass-close{position:absolute;right:12px;top:9px;z-index:3;width:29px;height:29px;display:grid;place-items:center;border:0;border-radius:50%;background:rgba(255,255,255,.38);color:#718092;transition:.2s}.glass-close:hover{background:rgba(255,255,255,.8);color:#314357}.glass-main,.glass-details{position:relative;z-index:1}.glass-main{display:grid;grid-template-columns:1.05fr 1.45fr .85fr 1.05fr .72fr;align-items:center;min-height:58px;padding-right:25px}.glass-main>section{min-width:0;padding:0 18px;border-right:1px solid rgba(153,174,194,.25)}.glass-main>section:first-child{padding-left:0}.glass-main>section:last-child{border-right:0}.glass-identity{display:grid;justify-items:start;gap:5px}.glass-identity span{padding:4px 8px;border-radius:999px;background:rgba(255,255,255,.55);font-size:9px;font-weight:700}.glass-identity strong{font-size:20px;letter-spacing:-.025em;color:#17283a}.glass-etf,.glass-return,.glass-progress,.glass-state{display:grid;gap:4px}.glass-main small,.glass-details dt{font-size:8.5px;color:#83909d}.glass-etf b{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.glass-etf span{font-size:8.5px;color:#7f8b97}.glass-return strong{font-size:17px}.glass-progress b,.glass-state b{font-size:11px}.glass-progress i{display:block;width:100%;height:4px;border-radius:999px;background:rgba(151,169,187,.2);overflow:hidden}.glass-progress em{display:block;height:100%;border-radius:inherit}.glass-details{display:grid;grid-template-columns:repeat(5,1fr);margin:10px 0 0;padding:10px 0 0;border-top:1px solid rgba(153,174,194,.22)}.glass-details div{padding:0 18px;border-right:1px solid rgba(153,174,194,.2)}.glass-details div:first-child{padding-left:0}.glass-details div:last-child{border-right:0}.glass-details dt{margin-bottom:4px}.glass-details dd{margin:0;font-size:10.5px;font-weight:700;color:#334454;white-space:nowrap}.flight-glass-enter-active,.flight-glass-leave-active{transition:opacity .24s ease,transform .3s cubic-bezier(.2,.75,.25,1)}.flight-glass-enter-from,.flight-glass-leave-to{opacity:0;transform:translateY(18px) scale(.985)}
@media(max-width:1200px) and (min-width:901px){.flight-popover{left:14px;right:14px;bottom:14px;padding-left:15px;padding-right:15px}.glass-main{grid-template-columns:.9fr 1.2fr .8fr 1fr}.glass-state{display:none}.glass-main>section{padding:0 12px}.glass-details div{padding:0 12px}}
@media(max-width:900px){.flight-popover{position:fixed;inset:auto 14px 14px;padding:16px;max-height:72vh;overflow:auto}.glass-main{grid-template-columns:1fr 1fr;padding-right:18px;gap:14px}.glass-main>section{padding:0;border:0}.glass-state{display:none}.glass-details{grid-template-columns:1fr 1fr;gap:12px}.glass-details div,.glass-details div:first-child{padding:0;border:0}.glass-details div:last-child{grid-column:1/-1}}
</style>
<style scoped>
/* Keep the entire geographic canvas visible at every desktop aspect ratio. */
@media(min-width:901px){.network-wrap{display:grid;place-items:center;background:#f8fbfe}.network{width:100%;height:100%;object-fit:contain}.airspace-stamp,.map-scale{z-index:3}}
</style>
<style scoped>
.legend{gap:6px}.legend button{display:inline-flex;align-items:center;gap:5px;min-height:27px;padding:0 8px;border:1px solid transparent;border-radius:999px;background:rgba(255,255,255,.54);color:#637181;font:inherit;white-space:nowrap}.legend button:hover{background:#fff;border-color:#d8e3ec}.legend button.active{background:#fff;border-color:#adc8df;color:#245d96;box-shadow:0 3px 10px rgba(50,91,126,.1)}.legend button i{width:7px;height:7px;border-radius:50%;background:#94a2b0}.legend button i.parked_negative{background:#d9484f}.legend button i.flying{background:#4c86d9}.legend button i.approaching{background:#e9972d}.legend button i.ready{background:#23956b}.legend button b{font-size:10px;font-variant-numeric:tabular-nums}.route-group.muted{opacity:.19}.flight-tooltip{position:absolute;z-index:5;min-width:156px;padding:9px 11px;border:1px solid rgba(210,225,235,.92);border-radius:10px;background:rgba(255,255,255,.94);box-shadow:0 10px 25px rgba(36,61,83,.14);transform:translate(13px,calc(-100% - 13px));pointer-events:none;backdrop-filter:blur(12px)}.flight-tooltip b,.flight-tooltip span,.flight-tooltip small{display:block}.flight-tooltip b{color:#243649;font-size:12px}.flight-tooltip span{max-width:190px;margin-top:2px;overflow:hidden;color:#526578;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.flight-tooltip small{margin-top:5px;color:#269469;font-size:10px;font-weight:650}.airspace-stamp b{display:grid;gap:2px;font-size:12px}.airspace-stamp b small{color:#7d91a3;font-size:8px;font-weight:650;letter-spacing:.1em}@media(max-width:1100px) and (min-width:901px){.legend button{padding:0 6px;font-size:10px}.legend button:nth-child(2){display:none}}@media(max-width:900px){.legend button{font-size:11px}.flight-tooltip{display:none}}
</style>
<style scoped>
.flight-popover{border-color:var(--sky-gray-soft);border-radius:16px;background:rgba(255,255,255,.97);box-shadow:var(--shadow-float);backdrop-filter:none;-webkit-backdrop-filter:none}.flight-popover::before,.flight-popover::after{display:none}.glass-close{background:#f3f6f9}.glass-main>section,.glass-details div{border-color:var(--line)}.glass-identity strong{color:var(--airline-navy)}
</style>
<style scoped>
/* Selected-flight operational strip. */
.flight-popover{left:18px;right:18px;bottom:18px;width:auto;padding:16px 22px 14px;border-radius:14px}.selected-flight-strip{display:grid;grid-template-columns:1.25fr .72fr .72fr minmax(300px,1.65fr) .78fr;align-items:stretch}.selected-flight-strip>section{min-width:0;padding:0 20px;border-right:1px solid var(--line)}.selected-flight-strip>section:first-child{padding-left:0}.selected-flight-strip>section:last-child{padding-right:0;border:0}.selected-flight-strip small{display:block;color:var(--muted-2);font-size:10px;font-weight:700;letter-spacing:.04em}.selected-flight-strip small em{margin-left:5px;color:#8ca0b7;font-size:8px;font-style:normal;letter-spacing:.08em}.strip-identity{display:flex;align-items:center;gap:12px}.selected-icon{width:49px;height:49px;display:grid;flex:0 0 auto;place-items:center;border:1px solid #79c9a1;border-radius:50%;color:var(--tower-green);background:#f3fbf7}.strip-identity strong{display:block;margin:5px 0 3px;color:var(--airline-navy);font-size:25px;line-height:1;letter-spacing:-.03em}.strip-identity p{margin:0;overflow:hidden;color:#63758a;font-size:12px;font-weight:600;text-overflow:ellipsis;white-space:nowrap}.strip-metric{display:grid;align-content:start;gap:12px}.strip-metric strong{color:#20344b;font-size:23px;font-variant-numeric:tabular-nums;letter-spacing:-.035em}.strip-route{padding-right:24px!important}.route-track{position:relative;height:57px;margin-top:11px}.route-track::before{content:"";position:absolute;top:17px;left:0;right:0;border-top:2px solid #b8c7d9}.route-track>i{position:absolute;top:17px;left:0;height:2px}.route-plane{position:absolute;top:8px;left:0;display:grid;place-items:center;color:var(--flight-blue);transform:translateX(-2px)}.route-stop{position:absolute;top:10px;display:grid;gap:14px;justify-items:center;color:#64778b;font-size:11px;font-weight:700}.route-stop::before{content:"";width:10px;height:10px;border:2px solid #fff;border-radius:50%;background:#7899bd;box-shadow:0 0 0 1px #7899bd}.route-stop em{color:#8192a4;font-size:10px;font-style:normal;font-weight:500;white-space:nowrap}.route-stop.departure{left:0}.route-stop.cruise{left:36%}.route-stop.approach{left:65%}.route-stop.landing{right:0}.route-stop.landing::before{background:var(--tower-green);box-shadow:0 0 0 1px #6ebd94}.route-stop.landing.active::before{box-shadow:0 0 0 3px rgba(30,158,99,.18)}.strip-status{display:grid;align-content:start;gap:10px}.strip-status>b{display:grid;grid-template-columns:24px 1fr;align-items:center;gap:5px;padding:10px;border-radius:10px;font-size:15px}.strip-status>b span{grid-column:2;font-size:8px;font-weight:700;letter-spacing:.08em}@media(max-width:1250px) and (min-width:901px){.flight-popover{padding:15px}.selected-flight-strip{grid-template-columns:1.1fr .72fr .65fr 1.45fr .8fr}.selected-flight-strip>section{padding:0 12px}.strip-identity strong{font-size:20px}.strip-metric strong{font-size:18px}.selected-icon{width:42px;height:42px}.route-stop em{display:none}}@media(max-width:900px){.flight-popover{left:14px;right:14px;bottom:14px;padding:16px}.selected-flight-strip{grid-template-columns:1fr 1fr;gap:16px}.selected-flight-strip>section{padding:0;border:0}.strip-route{grid-column:1/-1;padding:0!important}.strip-status{display:none}.strip-identity{grid-column:1/-1}.route-stop em{display:block}}
</style>
<style scoped>
@media(min-width:901px){.airport-name{font-size:14px}.airport-meta{font-size:11.5px}.wealth-name{font-size:14px}.legend{font-size:12px}.glass-main small,.glass-details dt{font-size:10px}.glass-etf b{font-size:14px}.glass-etf span{font-size:10px}.glass-return strong{font-size:20px}.glass-progress b,.glass-state b{font-size:13px}.glass-details dd{font-size:12px}}
</style>
