<script setup lang="ts">
import {CheckCircle2,AlertCircle,X} from 'lucide-vue-next'
withDefaults(defineProps<{message:string;type?:'success'|'error'}>(),{type:'success'})
defineEmits<{close:[]}>()
</script>
<template><Transition name="operation-toast" appear><div v-if="message" :class="['operation-toast',type]" :role="type==='error'?'alert':'status'" :aria-live="type==='error'?'assertive':'polite'"><CheckCircle2 v-if="type==='success'" :size="17"/><AlertCircle v-else :size="17"/><span>{{message}}</span><button type="button" aria-label="关闭提示" @click="$emit('close')"><X :size="14"/></button></div></Transition></template>
<style scoped>
.operation-toast{position:fixed;z-index:80;top:18px;right:22px;min-width:280px;max-width:min(440px,calc(100vw - 32px));display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;padding:12px 13px;border:1px solid;border-radius:11px;background:rgba(255,255,255,.96);box-shadow:0 16px 40px rgba(31,48,68,.16);backdrop-filter:blur(18px) saturate(140%);font-size:12px;line-height:1.45;font-weight:650}.operation-toast.success{border-color:#cce4d8;color:#147b57}.operation-toast.error{border-color:#efced0;color:#b83f46}.operation-toast button{width:32px;height:32px;display:grid;place-items:center;border:0;border-radius:50%;background:transparent;color:currentColor}.operation-toast button:hover{background:rgba(79,96,113,.08)}.operation-toast-enter-active,.operation-toast-leave-active{transition:.22s ease}.operation-toast-enter-from,.operation-toast-leave-to{opacity:0;transform:translateY(-8px)}@media(max-width:620px){.operation-toast{top:12px;right:16px;left:16px;min-width:0;max-width:none}}
</style>
