<script setup lang="ts">
import {Circle,Plane,PlaneLanding} from 'lucide-vue-next'
import {computed} from 'vue'
import {stateClass,stateLabel} from '../utils/format'

const props=defineProps<{state:string;compact?:boolean}>()
const kind=computed(()=>stateClass(props.state))
const icon=computed(()=>kind.value==='ready'?PlaneLanding:kind.value==='waiting'?Circle:Plane)
</script>

<template>
  <span :class="['flight-state-badge',kind,{compact}]">
    <component :is="icon" :size="compact?9:11" :fill="kind==='waiting'?'currentColor':'none'"/>
    {{stateLabel(state)}}
  </span>
</template>
