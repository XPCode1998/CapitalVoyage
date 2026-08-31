<script setup lang="ts">
import {BookOpenText,PlaneTakeoff,Radar,Settings} from 'lucide-vue-next'
const nav=[['/','01','态势预览','OVERVIEW',Radar],['/voyages','02','调度中心','DISPATCH',PlaneTakeoff],['/history','03','钱途记录','LOGBOOK',BookOpenText]] as const
</script>

<template>
  <div class="shell">
    <aside>
      <div class="brand"><img class="brand-mark" src="/brand/qian-tu-mark.svg" alt="钱途 Logo"/><div><strong>钱途</strong><span>CapitalVoyage</span></div></div>
      <nav><RouterLink v-for="[path,index,label,en,Icon] in nav" :key="path" :to="path" :class="{returning:path==='/voyages'&&$route.path==='/returns'}"><component :is="Icon" :size="21"/><span class="nav-copy"><i>{{index}}</i><b>{{label}}</b><small>{{en}}</small></span></RouterLink></nav>
      <RouterLink class="side-settings" to="/settings"><Settings :size="20"/><span><b>设置</b><small>SYSTEM SETTINGS</small></span></RouterLink>
    </aside>
    <main>
      <RouterView/>
    </main>
  </div>
</template>
