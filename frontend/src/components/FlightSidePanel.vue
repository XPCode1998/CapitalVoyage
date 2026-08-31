<script setup lang="ts">
import {nextTick,onBeforeUnmount,onMounted,ref} from 'vue'
import {X} from 'lucide-vue-next'
import {lockBodyScroll,unlockBodyScroll} from '../utils/bodyScroll'

withDefaults(defineProps<{title:string;eyebrow:string;subtitle?:string;stripLabel?:string}>(),{subtitle:'',stripLabel:'DISPATCH RELEASE'})
const emit=defineEmits<{close:[]}>()
const panel=ref<HTMLElement|null>(null)
let previousFocus:HTMLElement|null=null
function focusable(){return Array.from(panel.value?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')||[])}
function onKeydown(event:KeyboardEvent){if(event.key==='Escape'){emit('close');return}if(event.key!=='Tab')return;const items=focusable();if(!items.length)return;const first=items[0],last=items[items.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
onMounted(()=>{previousFocus=document.activeElement as HTMLElement;document.addEventListener('keydown',onKeydown);lockBodyScroll();nextTick(()=>{(panel.value?.querySelector<HTMLElement>('[autofocus]')||focusable()[0])?.focus()})})
onBeforeUnmount(()=>{document.removeEventListener('keydown',onKeydown);unlockBodyScroll();previousFocus?.focus()})
</script>

<template>
  <Teleport to="body">
    <Transition name="flight-panel" appear>
      <div class="flight-side-overlay" role="presentation" @mousedown.self="$emit('close')">
        <aside ref="panel" class="flight-side-panel" role="dialog" aria-modal="true" :aria-label="title">
          <div class="flight-side-strip"><span>CAPITALVOYAGE · FLIGHT OPERATIONS</span><b>{{stripLabel}}</b><button type="button" aria-label="关闭" @click="$emit('close')"><X :size="18"/></button></div>
          <header class="flight-side-heading">
            <p>{{eyebrow}}</p>
            <div><section><h2>{{title}}</h2><span v-if="subtitle">{{subtitle}}</span></section><slot name="status"/></div>
          </header>
          <div class="flight-side-body"><slot/></div>
          <footer v-if="$slots.footer" class="flight-side-footer"><slot name="footer"/></footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.flight-side-overlay{position:fixed;inset:0;z-index:30;display:flex;justify-content:flex-start;align-items:stretch;background:rgba(23,32,43,.32)}.flight-side-panel{position:relative;inset:auto;width:min(500px,94vw);height:100svh;display:flex;flex-direction:column;padding:0;border:0;border-right:1px solid #dce4ec;background:#fff;box-shadow:18px 0 48px rgba(21,37,57,.15);overflow:hidden}.flight-side-strip{position:relative;flex:0 0 42px;display:flex;align-items:center;justify-content:space-between;padding:0 66px 0 30px;background:#183e69;color:#d7e5f3}.flight-side-strip span{font-size:7px;letter-spacing:.13em}.flight-side-strip b{font-size:8px;letter-spacing:.1em}.flight-side-strip button{position:absolute;right:16px;top:6px;width:32px;height:32px;display:grid;place-items:center;border:0;border-radius:50%;background:transparent;color:#dfe9f3}.flight-side-strip button:hover{background:rgba(255,255,255,.1);color:#fff}.flight-side-heading{flex:0 0 auto;padding:19px 30px 12px;background:#fff}.flight-side-heading>p{margin:0 0 6px;color:#8795a4;font-size:8px;font-weight:700;letter-spacing:.13em}.flight-side-heading>div{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.flight-side-heading section{min-width:0}.flight-side-heading h2{margin:0;color:#172333;font-size:27px;line-height:1.12;letter-spacing:-.025em}.flight-side-heading section>span{display:block;margin-top:4px;color:#7d8997;font-size:12px}.flight-side-body{min-height:0;display:flex;flex:1;flex-direction:column;padding:0 30px 18px;overflow:hidden}.flight-panel-enter-active,.flight-panel-leave-active{transition:background-color .2s ease}.flight-panel-enter-active .flight-side-panel,.flight-panel-leave-active .flight-side-panel{transition:transform .28s cubic-bezier(.22,.72,.2,1),opacity .2s ease}.flight-panel-enter-from,.flight-panel-leave-to{background:rgba(23,32,43,0)}.flight-panel-enter-from .flight-side-panel,.flight-panel-leave-to .flight-side-panel{opacity:.75;transform:translateX(-100%)}
@media(max-width:620px){.flight-side-panel{width:100vw}.flight-side-strip{padding-left:20px}.flight-side-heading{padding-left:20px;padding-right:20px}.flight-side-body{padding-left:20px;padding-right:20px}}
</style>
<style scoped>
.flight-side-overlay{background:rgba(23,40,62,.32)}.flight-side-panel{border-right-color:var(--line);box-shadow:18px 0 48px rgba(17,40,72,.12)}.flight-side-strip{flex-basis:48px;background:var(--airline-navy)}.flight-side-strip span,.flight-side-strip b{font-size:9px}.flight-side-heading{padding-top:24px;padding-bottom:16px}.flight-side-heading>p{color:var(--muted-2);font-size:10px}.flight-side-heading h2{color:var(--ink);font-size:28px}.flight-side-heading section>span{color:var(--ink-2);font-size:13px}
</style>

<style scoped>
.flight-side-footer{flex:0 0 auto;padding:13px 30px 15px;border-top:1px solid #dfe6ed;background:linear-gradient(180deg,#fbfcfd,#f6f8fa)}.flight-side-footer :deep(.side-panel-actions){display:grid;gap:8px;width:100%}.flight-side-footer :deep(.side-panel-actions.two){grid-template-columns:1fr 1.6fr}.flight-side-footer :deep(.side-panel-actions.three){grid-template-columns:1fr 1fr 1.35fr}.flight-side-footer :deep(.panel-action){min-height:40px;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:9px 13px;border:1px solid transparent;border-radius:8px;font-size:11px;font-weight:680;white-space:nowrap}.flight-side-footer :deep(.panel-action.secondary){border-color:#dbe3eb;background:#fff;color:#4f5f70}.flight-side-footer :deep(.panel-action.secondary:hover){border-color:#b9c9da;background:#f7fafd;color:#244e7f}.flight-side-footer :deep(.panel-action.danger){border-color:#efd5d7;background:#fff7f7;color:#bd454d}.flight-side-footer :deep(.panel-action.danger:hover){border-color:#e8b9bd;background:#fff0f1}.flight-side-footer :deep(.panel-action.primary){background:#1f62c4;color:#fff;box-shadow:0 4px 11px rgba(31,98,196,.16)}.flight-side-footer :deep(.panel-action.primary:hover){background:#194f9d}.flight-side-footer :deep(.panel-action.return){background:var(--tower-green);color:#fff;box-shadow:0 4px 11px rgba(21,149,104,.16)}.flight-side-footer :deep(.panel-action.return:hover){background:#117b57}.flight-side-footer :deep(.panel-action:disabled){border-color:#e2e7ec;background:#eef1f4;color:#9aa5b0;box-shadow:none}.flight-side-footer :deep(.panel-hint){display:flex;align-items:center;justify-content:flex-end;gap:5px;margin:0 2px 8px;color:#8794a1;font-size:9px}.flight-side-body :deep(input),.flight-side-body :deep(select){height:36px;border-color:#d8e1ea;border-radius:8px;background:#fff}.flight-side-body :deep(input:focus),.flight-side-body :deep(select:focus){border-color:#6d9bd4;box-shadow:0 0 0 3px #edf4fc}.flight-side-body :deep(.form-section-title){color:#617387}
@media(max-width:620px){.flight-side-footer{padding-left:20px;padding-right:20px}}
.flight-side-footer :deep(.side-panel-actions.one){grid-template-columns:1fr}
</style>
<style scoped>
.flight-side-body{overflow-y:auto!important;scrollbar-width:none}.flight-side-body::-webkit-scrollbar{display:none}
@media(max-height:720px){.flight-side-strip{flex-basis:35px}.flight-side-heading{padding-top:12px;padding-bottom:8px}.flight-side-heading h2{font-size:23px}.flight-side-body{padding-bottom:10px}}
</style>
