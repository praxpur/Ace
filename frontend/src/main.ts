import { createApp } from 'vue'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import './theme'
import './style.css'

// Element Plus 组件/样式由 unplugin 按需引入（见 vite.config.ts）
const app = createApp(App)
app.mount('#app')
