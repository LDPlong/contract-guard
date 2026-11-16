import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import App from '@/App.vue'
import { reportError } from '@/lib/errorBus'
import '@/styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

/**
 * 错误边界兜不住的还有两类：组件事件里抛的异常，以及没人 catch 的 Promise。
 * 放着不管，用户看到的就是"点了没反应"，控制台之外不留痕迹。
 */
app.config.errorHandler = (err, _instance, info) => {
  reportError(info ? `界面异常（${info}）` : '界面异常', err)
}

window.addEventListener('unhandledrejection', (event) => {
  reportError('未处理的异步异常', event.reason)
})

app.mount('#app')
