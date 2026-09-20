<script setup lang="ts">
import {nextTick,onBeforeUnmount,onMounted,ref,useId} from 'vue'
import {X} from 'lucide-vue-next'
import {lockBodyScroll,unlockBodyScroll} from '../utils/bodyScroll'

const props=defineProps<{title:string;eyebrow?:string;variant?:'default'|'ticket'|'settlement';preventClose?:boolean}>()
const emit=defineEmits<{close:[]}>()
const modal=ref<HTMLElement|null>(null)
const titleId=`modal-title-${useId()}`
let previousFocus:HTMLElement|null=null
function focusable(){return Array.from(modal.value?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')||[])}
function close(){if(!props.preventClose)emit('close')}
function onKeydown(event:KeyboardEvent){if(event.key==='Escape'){close();return}if(event.key!=='Tab')return;const items=focusable();if(!items.length){event.preventDefault();modal.value?.focus();return}const first=items[0],last=items[items.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}
onMounted(()=>{previousFocus=document.activeElement as HTMLElement;document.addEventListener('keydown',onKeydown);lockBodyScroll();nextTick(()=>{(modal.value?.querySelector<HTMLElement>('[autofocus]')||focusable()[0]||modal.value)?.focus()})})
onBeforeUnmount(()=>{document.removeEventListener('keydown',onKeydown);unlockBodyScroll();previousFocus?.focus()})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade" appear>
      <div class="overlay" role="presentation" @mousedown.self="close">
        <section ref="modal" :class="['modal',`modal-${variant||'default'}`]" role="dialog" aria-modal="true" :aria-labelledby="titleId" tabindex="-1">
          <header>
            <div><p v-if="eyebrow" class="section-kicker">{{eyebrow}}</p><h2 :id="titleId">{{title}}</h2></div>
            <button class="modal-close" type="button" aria-label="关闭" :disabled="preventClose" @click="close"><X :size="18"/></button>
          </header>
          <div class="modal-body"><slot/></div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-close{width:32px;height:32px;display:grid;place-items:center;border:0;border-radius:50%;background:#f3f6f8;color:#718091}.modal-close:hover{background:#eaf0f5;color:#243548}.section-kicker{margin:0 0 4px}.modal-fade-enter-active,.modal-fade-leave-active{transition:opacity .18s ease}.modal-fade-enter-active .modal,.modal-fade-leave-active .modal{transition:transform .22s ease,opacity .18s ease}.modal-fade-enter-from,.modal-fade-leave-to{opacity:0}.modal-fade-enter-from .modal,.modal-fade-leave-to .modal{opacity:0;transform:translateY(8px) scale(.99)}
.modal-ticket{width:min(840px,100%);max-height:calc(100vh - 24px);display:flex;flex-direction:column;overflow:hidden;border-top:0}.modal-ticket>header{flex:0 0 auto;padding:14px 20px;background:#183e69;border-bottom-color:#102f52;color:#fff}.modal-ticket>header .section-kicker{color:#a9bfd4}.modal-ticket>header .modal-close{background:rgba(255,255,255,.08);color:#dce8f3}.modal-ticket>header .modal-close:hover{background:rgba(255,255,255,.16);color:#fff}.modal-ticket>.modal-body{min-height:0;overflow:hidden;padding:17px 20px 18px}.modal-settlement{width:min(720px,100%);border-top:3px solid var(--tower-green)}.modal-settlement>header{background:linear-gradient(90deg,#f1faf6,#fff)}
@media(max-width:700px){.modal-ticket{max-height:calc(100vh - 12px)}.modal-ticket>.modal-body{overflow:auto}}
</style>
<style scoped>
.modal-close{width:36px;height:36px}
</style>
<style scoped>
.modal-ticket>header{padding-top:16px;padding-bottom:16px;background:var(--airline-navy)}.modal-ticket>header .section-kicker{color:var(--sky-gray)}.modal-ticket>.modal-body{padding:20px}.modal-settlement>header{background:#f6fbf8}
</style>
