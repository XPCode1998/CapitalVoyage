<script setup lang="ts">
import {ref} from 'vue'
import {LockKeyhole,PlaneTakeoff} from 'lucide-vue-next'
import {post} from '../api/client'

const emit=defineEmits<{authenticated:[username:string]}>()
const username=ref('xp'),password=ref(''),error=ref(''),saving=ref(false)
async function login(){if(saving.value)return;error.value='';if(!username.value.trim()||!password.value){error.value='请输入账号和密码';return}saving.value=true;try{const result=await post<{username:string}>('/api/auth/login',{username:username.value,password:password.value});emit('authenticated',result.username)}catch(e){error.value=(e as Error).message}finally{saving.value=false}}
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <div class="login-mark"><img src="/brand/qian-tu-mark.svg" alt="钱途"/><span><i>CAPITALVOYAGE</i><b>钱途</b></span></div>
      <div class="login-copy"><p>财富自由塔台</p><h1>欢迎返航</h1><span>登录后继续管理你的 ETF 航次与资金调度。</span></div>
      <form @submit.prevent="login">
        <p v-if="error" class="login-error">{{error}}</p>
        <label>登录账号<input v-model="username" autocomplete="username" autofocus maxlength="64"/></label>
        <label>登录密码<input v-model="password" type="password" autocomplete="current-password" maxlength="128"/></label>
        <button type="submit" :disabled="saving"><PlaneTakeoff :size="17"/>{{saving?'正在验证…':'进入财富塔台'}}</button>
      </form>
      <div class="login-security"><LockKeyhole :size="14"/><span>本地账号保护 · 登录状态仅保存在安全会话中</span></div>
    </section>
  </main>
</template>

<style scoped>
.login-page{min-height:100dvh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 0,#e6f2ff 0,transparent 42%),linear-gradient(135deg,#f5f9fd,#edf4fa)}.login-card{width:min(420px,100%);padding:34px;border:1px solid #d4e0ec;border-radius:20px;background:rgba(255,255,255,.94);box-shadow:0 24px 60px rgba(31,64,96,.16)}.login-mark{display:flex;align-items:center;gap:12px}.login-mark img{width:44px;height:44px}.login-mark span{display:grid;gap:2px}.login-mark i{color:#6d8eae;font-size:8px;font-style:normal;font-weight:750;letter-spacing:.14em}.login-mark b{color:#203c5a;font-size:21px;letter-spacing:.08em}.login-copy{margin:30px 0 22px}.login-copy p{margin:0;color:#3677bf;font-size:10px;font-weight:750;letter-spacing:.12em}.login-copy h1{margin:7px 0 6px;color:#21374f;font-size:29px;letter-spacing:-.04em}.login-copy span{color:#718397;font-size:12px}.login-card form{display:grid;gap:14px}.login-card label{display:grid;gap:7px;color:#526a82;font-size:11px;font-weight:650}.login-card input{height:43px;padding:0 12px;border:1px solid #cfdae5;border-radius:9px;background:#fff;color:#263e57}.login-card input:focus{border-color:#5b98d2;box-shadow:0 0 0 3px rgba(69,137,204,.12);outline:0}.login-card button{min-height:45px;display:flex;align-items:center;justify-content:center;gap:7px;margin-top:5px;border:0;border-radius:9px;background:#2065ae;color:#fff;font-size:13px;font-weight:700}.login-card button:disabled{opacity:.65}.login-error{margin:0;padding:9px 11px;border-radius:8px;background:#fff0f1;color:#bd3f45;font-size:11px}.login-security{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:24px;color:#8393a3;font-size:10px}
</style>
