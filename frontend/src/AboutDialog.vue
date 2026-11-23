<template>
  <el-dialog v-model="open" title="关于分刷酱 · Ace" width="640px" align-center append-to-body class="about-dialog">
    <div class="about-brand">
      <img src="/favicon.svg" alt="分刷酱 Logo" />
      <div><span class="eyebrow">ACE / COURSE WORKSPACE</span><h2>分刷酱 <em class="about-english-name">Ace</em> <span>0.2.0</span></h2><p>课程任务，一处管理。</p></div>
    </div>
    <div class="developer-card">
      <div class="developer-heading"><span class="developer-avatar">P</span><div><span class="eyebrow">DESIGNED & BUILT BY</span><h3>praxpur <span>开发者</span></h3></div></div>
      <p>济南大学 · 计算机科学与技术</p>
      <p class="developer-bio">探索全栈开发、机器学习与深度学习，关注姿态识别与开源实践。</p>
      <div class="developer-links">
        <a href="https://github.com/praxpur" @click.prevent="$emit('external', 'https://github.com/praxpur')">GitHub 主页 <span>↗</span></a>
        <a href="https://praxpur.figma.site" @click.prevent="$emit('external', 'https://praxpur.figma.site')">个人网站 <span>↗</span></a>
        <a href="mailto:fnme370679@gmail.com" @click.prevent="$emit('external', 'mailto:fnme370679@gmail.com')">联系开发者 <span>↗</span></a>
      </div>
      <div class="developer-email">fnme370679@gmail.com</div>
    </div>
    <div class="about-project">
      <div><h3>一起让它更好用</h3><p>查看源码、反馈问题，或为项目点亮一颗星。</p></div>
      <a href="https://github.com/praxpur/Ace" @click.prevent="$emit('external', 'https://github.com/praxpur/Ace')">项目仓库 ↗</a>
    </div>
    <div class="about-tray-note">后台运行：关闭或最小化窗口后，任务会在系统托盘继续运行。双击托盘图标恢复，右键菜单可退出。</div>
    <div class="about-credits"><span>开源与致谢</span><p>基于 chaoxing-gui 与 Treehouse-Course 整合，感谢上游作者与开源社区。整体遵循 GPL-3.0，智慧树部分保留 MIT 许可。</p><a href="https://github.com/Samueli924/chaoxing" @click.prevent="$emit('external', 'https://github.com/Samueli924/chaoxing')">超星上游</a><span class="credit-divider">/</span><a href="https://github.com/praxpur/Treehouse-Course" @click.prevent="$emit('external', 'https://github.com/praxpur/Treehouse-Course')">Treehouse-Course</a></div>
  </el-dialog>
</template>

<script setup lang="ts">
const open = defineModel<boolean>({ default: false })
defineEmits<{ external: [url: string] }>()
</script>
