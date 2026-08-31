import {createRouter,createWebHistory} from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import VoyagesView from '../views/VoyagesView.vue'
import ReturnsView from '../views/ReturnsView.vue'
import HistoryView from '../views/HistoryView.vue'
import SettingsView from '../views/SettingsView.vue'

const router=createRouter({history:createWebHistory(),routes:[
  {path:'/',component:DashboardView,meta:{title:'态势预览'}},{path:'/voyages',component:VoyagesView,meta:{title:'调度中心'}},{path:'/returns',component:ReturnsView,meta:{title:'调度中心 · 航班返航'}},{path:'/history',component:HistoryView,meta:{title:'钱途记录'}},{path:'/settings',component:SettingsView,meta:{title:'设置'}}
]})

router.afterEach(to=>{document.title=`${String(to.meta.title||'钱途')} · 钱途 CapitalVoyage`})

export default router
