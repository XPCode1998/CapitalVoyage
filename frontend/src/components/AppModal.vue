<script setup lang="ts">
import {onBeforeUnmount,onMounted} from 'vue'
import {X} from 'lucide-vue-next'
import {lockBodyScroll,unlockBodyScroll} from '../utils/bodyScroll'

defineProps<{title:string;eyebrow?:string;variant?:'default'|'ticket'|'settlement'}>()
const emit=defineEmits<{close:[]}>()
function onKeydown(event:KeyboardEvent){if(event.key==='Escape')emit('close')}
onMounted(()=>{document.addEventListener('keydown',onKeydown);lockBodyScroll()})
onBeforeUnmount(()=>{document.removeEventListener('keydown',onKeydown);unlockBodyScroll()})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade" appear>
      <div class="overlay" role="presentation" @mousedown.self="$emit('close')">
        <section :class="['modal',`modal-${variant||'default'}`]" role="dialog" aria-modal="true" :aria-label="title">
          <header>
            <div><p v-if="eyebrow" class="section-kicker">{{eyebrow}}</p><h2>{{title}}</h2></div>
            <button class="modal-close" type="button" aria-label="关闭" @click="$emit('close')"><X :size="18"/></button>
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
.modal-ticket>header{padding-top:16px;padding-bottom:16px;background:var(--airline-navy)}.modal-ticket>header .section-kicker{color:var(--sky-gray)}.modal-ticket>.modal-body{padding:20px}.modal-settlement>header{background:#f6fbf8}
</style>
