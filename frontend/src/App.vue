<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <h3><img src="/favicon.svg" class="logo-icon" alt="" />分刷酱</h3>
        <span class="logo-sub">超星 / 智慧树刷课助手</span>
      </div>

      <!-- 平台切换器 -->
      <div class="platform-switcher">
        <div class="switcher-label">当前刷课平台</div>
        <div class="switcher-buttons">
          <button
            type="button"
            class="platform-btn"
            :class="{ active: platform === 'chaoxing' }"
            @click="switchPlatform('chaoxing')"
          >
            <span>超星学习通</span>
            <span v-if="cxRunning" class="status-dot running" title="超星任务运行中"></span>
          </button>
          <button
            type="button"
            class="platform-btn"
            :class="{ active: platform === 'treehouse' }"
            @click="switchPlatform('treehouse')"
          >
            <span>智慧树</span>
            <span
              v-if="thRequest"
              class="status-dot waiting"
              title="等待勾选课程或视频"
            ></span>
            <span
              v-else-if="thRunning"
              class="status-dot running"
              title="智慧树任务运行中"
            ></span>
          </button>
        </div>
      </div>

      <!-- 统一三级功能菜单 -->
      <el-menu
        :default-active="activeIndex"
        class="side-menu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        @select="handleSelect"
      >
        <el-menu-item index="1">
          <el-icon><Setting /></el-icon>
          <span>账号与配置</span>
        </el-menu-item>
        <el-menu-item index="2">
          <el-icon><Reading /></el-icon>
          <span>课程与目录</span>
          <el-tag
            v-if="platform === 'treehouse' && thRequest"
            size="small"
            type="warning"
            effect="dark"
            class="menu-badge"
          >
            待选{{ thRequest.title }}
          </el-tag>
          <el-tag
            v-else-if="platform === 'chaoxing' && courses.length > 0"
            size="small"
            type="info"
            effect="plain"
            class="menu-badge"
          >
            {{ courses.length }}
          </el-tag>
        </el-menu-item>
        <el-menu-item index="3">
          <el-icon><Monitor /></el-icon>
          <span>运行面板</span>
          <el-tag
            v-if="currentPlatformRunning"
            size="small"
            type="success"
            effect="dark"
            class="menu-badge"
          >
            运行中
          </el-tag>
        </el-menu-item>
      </el-menu>

      <div class="theme-toggle">
        <el-switch
          v-model="isDark"
          inline-prompt
          :active-icon="Moon"
          :inactive-icon="Sunny"
          @change="toggleTheme"
        />
        <span class="theme-label">{{ isDark ? '夜间模式' : '日间模式' }}</span>
      </div>
    </el-aside>

    <el-container>
      <el-main class="main-content">
        <!-- ==================== 1. 账号与配置视图 ==================== -->
        <div v-show="activeIndex === '1'">
          <!-- 超星配置卡片 -->
          <el-card v-show="platform === 'chaoxing'" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="header-title-group">
                  <el-tag type="primary" effect="plain" size="small">超星学习通</el-tag>
                  <span>账号与挂机配置中心</span>
                </div>
                <el-tag :type="cxRunning ? 'success' : courses.length > 0 ? 'primary' : 'info'">
                  {{ cxRunning ? '任务进行中' : courses.length > 0 ? '已获取课程' : '等待登录' }}
                </el-tag>
              </div>
            </template>

            <el-tabs v-model="activeConfigTab">
              <!-- 基础设置 -->
              <el-tab-pane label="基础设置" name="common">
                <el-form :model="config.common" label-width="150px" class="aligned-form">
                  <el-form-item label="登录账号">
                    <el-input v-model="config.common.username" placeholder="请输入超星手机号/账号" />
                  </el-form-item>
                  <el-form-item label="登录密码">
                    <el-input
                      v-model="config.common.password"
                      type="password"
                      show-password
                      placeholder="请输入密码"
                    />
                  </el-form-item>
                  <el-form-item label="使用 Cookie 登录">
                    <el-switch v-model="config.common.use_cookies" />
                    <div class="field-hint">
                      开启后忽略账号密码，从程序目录下的 cookies.txt 读取登录状态
                    </div>
                  </el-form-item>
                  <el-form-item label="播放倍速">
                    <el-slider
                      v-model="config.common.speed"
                      :min="1"
                      :max="2"
                      :step="0.1"
                      show-input
                    />
                    <div class="field-hint">超星视频上报倍速范围 1.0x ~ 2.0x</div>
                  </el-form-item>
                  <el-form-item label="并行任务数">
                    <el-input-number v-model="config.common.jobs" :min="1" :max="10" />
                  </el-form-item>
                  <el-form-item label="未开放章节行为">
                    <el-radio-group v-model="config.common.notopen_action">
                      <el-radio value="retry">重试</el-radio>
                      <el-radio value="continue">跳过(继续)</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item label="失败重试间隔(秒)">
                    <el-input-number
                      v-model="config.common.retry_interval"
                      :min="0.1"
                      :max="60"
                      :step="0.1"
                      :precision="1"
                    />
                  </el-form-item>
                  <el-form-item label="自动签到">
                    <el-switch v-model="config.common.auto_sign" />
                    <div class="field-hint">
                      刷课前先完成各课程当前进行中的签到；位置签到仍会由服务端校验距离
                    </div>
                  </el-form-item>
                  <el-form-item label="章节检测答错重做">
                    <el-switch v-model="config.common.work_redo_enabled" />
                    <div class="field-hint">关闭时只检查并记录成绩，仅适合允许作答一次的课程</div>
                  </el-form-item>
                  <el-form-item label="最大重做次数" v-if="config.common.work_redo_enabled">
                    <el-input-number v-model="config.common.work_max_retries" :min="1" :max="10" />
                  </el-form-item>
                  <el-form-item label="自动增加学习次数">
                    <el-switch v-model="config.common.add_learning_count" />
                    <div class="field-hint">
                      刷课任务全部完成后，轮询访问章节把学习次数补到目标值
                    </div>
                  </el-form-item>
                  <el-form-item label="目标学习次数" v-if="config.common.add_learning_count">
                    <el-input-number v-model="config.common.target_count" :min="1" :max="1000" />
                  </el-form-item>
                  <el-form-item label="详细日志(TRACE)">
                    <el-switch v-model="config.common.verbose" />
                    <div class="field-hint">开启后控制台会输出更细粒度的调试信息，排查问题用</div>
                  </el-form-item>
                </el-form>
              </el-tab-pane>

              <!-- 题库配置 -->
              <el-tab-pane label="题库/AI设置" name="tiku">
                <el-form :model="config.tiku" label-width="150px" class="aligned-form">
                  <el-form-item label="启用答题">
                    <el-switch v-model="config.tiku.enabled" />
                  </el-form-item>
                  <el-alert
                    v-if="!config.tiku.enabled"
                    title="答题已关闭：章节检测会跳过，不查询题库，不随机填写答案，也不会提交答案。"
                    type="info"
                    :closable="false"
                    show-icon
                    style="margin: 0 0 18px 150px; width: calc(100% - 150px)"
                  />
                  <el-form-item label="题库引擎提供商">
                    <el-select
                      v-model="tikuProviders"
                      multiple
                      collapse-tags
                      collapse-tags-tooltip
                      placeholder="请选择引擎，可多选作为回退链"
                      style="width: 100%"
                    >
                      <el-option label="TikuYanxi (言溪)" value="TikuYanxi" />
                      <el-option label="TikuLike (LIKE)" value="TikuLike" />
                      <el-option label="TikuAdapter (自建适配器)" value="TikuAdapter" />
                      <el-option label="SiliconFlow (硅基流动)" value="SiliconFlow" />
                      <el-option label="AI (自定义大模型)" value="AI" />
                      <el-option label="TikuGo" value="TikuGo" />
                      <el-option label="TikuManual (手动打字)" value="TikuManual" />
                    </el-select>
                    <div class="field-hint">
                      按选择顺序依次查询，前面的题库没命中时自动回退到下一个
                    </div>
                  </el-form-item>

                  <el-form-item label="自动提交答卷">
                    <el-switch v-model="config.tiku.submit" />
                  </el-form-item>
                  <el-form-item label="最低题库覆盖率" v-if="config.tiku.submit">
                    <el-slider
                      v-model="config.tiku.cover_rate"
                      :min="0"
                      :max="1"
                      :step="0.05"
                      show-input
                    />
                  </el-form-item>

                  <el-form-item label="API Token" v-if="needTikuToken">
                    <el-input
                      v-model="config.tiku.tokens"
                      placeholder="言溪或LIKE的Token，多个用英文逗号分隔"
                    />
                  </el-form-item>

                  <el-form-item label="适配器地址" v-if="hasTikuProvider('TikuAdapter')">
                    <el-input v-model="config.tiku.url" placeholder="例如 http://127.0.0.1:3000" />
                  </el-form-item>

                  <template v-if="needLlmConfig">
                    <el-form-item label="大模型 API Key">
                      <el-input v-model="config.tiku.key" placeholder="例如 sk-..." />
                    </el-form-item>
                    <el-form-item label="大模型 Endpoint">
                      <el-input
                        v-model="config.tiku.endpoint"
                        placeholder="例如 https://api.siliconflow.cn/v1/chat/completions"
                      />
                    </el-form-item>
                    <el-form-item label="大模型名称">
                      <el-input
                        v-model="config.tiku.model"
                        placeholder="例如 deepseek-ai/DeepSeek-V3"
                      />
                    </el-form-item>
                  </template>

                  <el-collapse class="advanced-collapse">
                    <el-collapse-item title="高级参数 (一般保持默认即可)" name="advanced">
                      <el-form-item label="请求代理(可选)">
                        <el-input
                          v-model="config.tiku.http_proxy"
                          placeholder="例如 http://127.0.0.1:7890，直连留空"
                        />
                      </el-form-item>
                      <el-form-item label="题库查询间隔(秒)">
                        <el-input-number
                          v-model="config.tiku.delay"
                          :min="0"
                          :max="30"
                          :step="0.5"
                          :precision="1"
                        />
                      </el-form-item>
                      <el-form-item label="大模型请求间隔(秒)">
                        <el-input-number
                          v-model="config.tiku.min_interval_seconds"
                          :min="0"
                          :max="60"
                          :step="1"
                        />
                      </el-form-item>
                      <el-form-item label="JSON 模式">
                        <el-switch v-model="config.tiku.json_mode" />
                        <div class="field-hint">
                          请求附带 response_format=json_object，服务端不支持时会报错
                        </div>
                      </el-form-item>
                      <el-form-item label="extra_body">
                        <el-input
                          v-model="config.tiku.extra_body"
                          type="textarea"
                          :rows="2"
                          placeholder='例如 {"thinking": {"type": "disabled"}}'
                        />
                        <div class="field-hint">JSON 格式，会透传给大模型接口；留空使用默认值</div>
                      </el-form-item>
                      <el-form-item label="LIKE 联网搜索">
                        <el-switch v-model="config.tiku.likeapi_search" />
                      </el-form-item>
                      <el-form-item label="LIKE 视觉能力">
                        <el-switch v-model="config.tiku.likeapi_vision" />
                      </el-form-item>
                      <el-form-item label="LIKE 模型名称">
                        <el-input v-model="config.tiku.likeapi_model" placeholder="glm-4.5-air" />
                      </el-form-item>
                      <el-form-item label="GO 授权Token">
                        <el-input
                          v-model="config.tiku.go_authorization"
                          placeholder="选填，用于解除限流"
                        />
                      </el-form-item>
                      <el-form-item label="GO 请求间隔(秒)">
                        <el-input-number
                          v-model="config.tiku.go_min_interval"
                          :min="0"
                          :max="60"
                          :step="0.5"
                          :precision="1"
                        />
                      </el-form-item>
                      <el-form-item label="手动模式出题方式">
                        <el-select v-model="config.tiku.manual_mode_default" style="width: 100%">
                          <el-option label="一次性输入所有(batch)" value="batch" />
                          <el-option label="一题一输入(single)" value="single" />
                        </el-select>
                      </el-form-item>
                    </el-collapse-item>
                  </el-collapse>

                  <el-form-item>
                    <el-button
                      type="info"
                      @click="testApi"
                      :loading="testingApi"
                      :disabled="!config.tiku.enabled"
                    >
                      测试题库/API连接
                    </el-button>
                  </el-form-item>
                </el-form>
              </el-tab-pane>

              <!-- 通知配置 -->
              <el-tab-pane label="通知推送(微信/等)" name="notification">
                <el-form :model="config.notification" label-width="150px" class="aligned-form">
                  <el-form-item label="推送提供商">
                    <el-select
                      v-model="config.notification.provider"
                      placeholder="请选择"
                      style="width: 100%"
                    >
                      <el-option label="不推送" value="" />
                      <el-option label="ServerChan (Server酱)" value="ServerChan" />
                      <el-option label="Bark (iOS)" value="Bark" />
                      <el-option label="Qmsg (QQ群)" value="Qmsg" />
                      <el-option label="Telegram" value="Telegram" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="推送链接(URL)" v-if="config.notification.provider">
                    <el-input
                      v-model="config.notification.url"
                      placeholder="请填入推送平台提供的带Token URL"
                    />
                  </el-form-item>
                  <el-form-item
                    label="Telegram chat_id"
                    v-if="config.notification.provider === 'Telegram'"
                  >
                    <el-input
                      v-model="config.notification.tg_chat_id"
                      placeholder="例如 123456789，不加引号"
                    />
                  </el-form-item>
                </el-form>
              </el-tab-pane>
            </el-tabs>

            <div class="config-actions">
              <el-button type="primary" @click="saveConfig" :loading="saving">
                保存配置并登录
              </el-button>
              <el-button @click="saveCxConfigOnly" :loading="savingOnly">仅保存配置</el-button>
            </div>
          </el-card>

          <!-- 智慧树应用内登录窗口：镜像无头浏览器登录页，验证码由用户手动完成 -->
          <el-dialog
            v-model="thLoginOpen"
            title="智慧树登录 · 请完成验证码并点击登录"
            width="1000px"
            top="4vh"
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            :show-close="false"
            destroy-on-close
          >
            <div class="th-login-hint">
              账号密码已自动填入。请勾选用户协议、完成验证码后点击页面上的“登录”，成功后此窗口会自动关闭。
            </div>
            <div
              class="th-login-stage"
              tabindex="0"
              @keydown.prevent="onThLoginKey"
            >
              <img
                v-if="thLoginImage"
                ref="thLoginImg"
                :src="thLoginImage"
                class="th-login-frame"
                draggable="false"
                @mousedown.prevent="onThLoginMouse('down', $event)"
                @mousemove="onThLoginMouse('move', $event)"
                @mouseup="onThLoginMouse('up', $event)"
                @mouseleave="onThLoginMouse('up', $event)"
                @wheel.prevent="onThLoginWheel"
                @dragstart.prevent
              />
              <div v-else class="th-login-loading">正在加载登录页…</div>
            </div>
            <template #footer>
              <el-button @click="stopThTask">取消连接</el-button>
            </template>
          </el-dialog>

          <!-- 智慧树配置卡片 (完全对齐超星配置样式) -->
          <el-card v-show="platform === 'treehouse'" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="header-title-group">
                  <el-tag type="success" effect="plain" size="small">智慧树</el-tag>
                  <span>账号与挂机配置中心</span>
                </div>
                <el-tag :type="thRunning ? 'success' : thOptions.has_state ? 'primary' : 'info'">
                  {{ thRunning ? '任务进行中' : thOptions.has_state ? '已检测到登录态' : '等待连接' }}
                </el-tag>
              </div>
            </template>

            <el-tabs v-model="activeThConfigTab">
              <el-tab-pane label="基础设置" name="common">
                <el-form :model="thOptions" label-width="150px" class="aligned-form">
                  <el-form-item label="智慧树账号">
                    <el-input v-model="thOptions.username" placeholder="请输入智慧树手机号/用户名" />
                  </el-form-item>

                  <el-form-item label="智慧树密码">
                    <el-input
                      v-model="thOptions.password"
                      type="password"
                      show-password
                      placeholder="请输入智慧树密码"
                    />
                    <div class="field-hint">
                      连接时会自动填入浏览器登录页；验证码、勾选协议与点击登录需在浏览器中手动完成
                    </div>
                  </el-form-item>

                  <el-form-item label="课程中心入口">
                    <el-input
                      v-model="thOptions.url"
                      placeholder="请输入智慧树课程中心或具体课程页 URL"
                    />
                    <div class="field-hint">
                      默认进入智慧树课程中心读取全部课程，也支持直接粘贴单门课程学习地址
                    </div>
                  </el-form-item>

                  <el-form-item label="记住登录状态">
                    <el-switch v-model="thOptions.remember" />
                    <div class="field-hint">
                      开启后首次在浏览器完成登录会自动保存本地登录态文件，后续免重复扫码或输入密码
                    </div>
                  </el-form-item>

                  <el-form-item label="登录态文件路径">
                    <el-input
                      v-model="thOptions.state_path"
                      placeholder="首次登录会保存到此处 (.state/auth.json)"
                    />
                    <div class="field-hint">
                      {{
                        thOptions.has_state
                          ? '已找到本地登录态文件，连接时将自动复用登录状态（类似超星 Cookie 登录）'
                          : '尚未生成登录态文件；首次连接请保持“无头模式运行”为关闭，在浏览器中完成登录'
                      }}
                    </div>
                  </el-form-item>

                  <el-form-item label="播放倍速">
                    <el-slider
                      v-model="thOptions.speed"
                      :min="1"
                      :max="4"
                      :step="0.25"
                      show-input
                      @change="snapThSpeed"
                    />
                    <div class="field-hint">
                      支持档位：1x / 1.25x / 1.5x / 1.75x / 2x / 3x / 4x，播放时自动匹配课程菜单允许的最高档位
                    </div>
                  </el-form-item>

                  <el-form-item label="应用内登录">
                    <el-switch v-model="thOptions.embedded_login" />
                    <div class="field-hint">
                      开启后不弹出浏览器，验证码在软件内的登录窗口里完成；关闭则使用独立浏览器窗口
                    </div>
                  </el-form-item>

                  <el-form-item label="无头模式运行">
                    <el-switch v-model="thOptions.headless" />
                    <div class="field-hint">
                      开启后后台隐藏浏览器窗口运行；首次登录或需手动处理验证码时请关闭
                    </div>
                  </el-form-item>

                  <el-form-item label="网络连接方式">
                    <el-radio-group v-model="thOptions.connection_mode">
                      <el-radio value="system">跟随系统代理</el-radio>
                      <el-radio value="direct">直连(忽略代理)</el-radio>
                    </el-radio-group>
                    <div class="field-hint">
                      若开启系统代理工具导致智慧树页面加载超时，可切换为“直连”
                    </div>
                  </el-form-item>
                </el-form>
              </el-tab-pane>
            </el-tabs>

            <div class="config-actions">
              <el-button
                type="primary"
                :loading="thStarting"
                :disabled="thRunning"
                @click="startTreehouse"
              >
                保存配置并连接课程
              </el-button>
              <el-button @click="saveThConfigOnly" :loading="thSaving">仅保存配置</el-button>
            </div>
          </el-card>
        </div>

        <!-- ==================== 2. 课程与目录视图 ==================== -->
        <div v-show="activeIndex === '2'">
          <!-- 超星课程列表卡片 -->
          <el-card v-show="platform === 'chaoxing'" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="header-title-group">
                  <el-tag type="primary" effect="plain" size="small">超星学习通</el-tag>
                  <span>选择要挂机的课程</span>
                  <el-tag type="info" size="small">
                    已选 {{ selectedCourses.length }} / {{ courses.length }} 门
                  </el-tag>
                </div>
                <div class="header-actions">
                  <el-button type="success" @click="fetchCourses" :loading="loadingCourses">
                    刷新课程
                  </el-button>
                  <el-button
                    type="primary"
                    @click="startTask"
                    :disabled="selectedCourses.length === 0 || cxRunning"
                  >
                    开始刷课 ({{ selectedCourses.length }})
                  </el-button>
                </div>
              </div>
            </template>

            <div class="catalog-toolbar">
              <el-input
                v-model="cxQuery"
                placeholder="搜索课程名称 / 班级 / 教师"
                clearable
                style="width: 280px"
              />
              <div class="toolbar-actions">
                <el-button
                  size="small"
                  @click="cxSelectAllVisible"
                  :disabled="filteredCxCourses.length === 0"
                >
                  全选当前
                </el-button>
                <el-button
                  size="small"
                  @click="cxClearSelection"
                  :disabled="selectedCourses.length === 0"
                >
                  清空已选
                </el-button>
              </div>
            </div>

            <el-table
              ref="cxTableRef"
              :data="filteredCxCourses"
              row-key="courseId"
              style="width: 100%"
              max-height="calc(100vh - 240px)"
              @selection-change="handleCxSelectionChange"
              @row-click="toggleCxRow"
              v-loading="loadingCourses"
              empty-text="暂无课程数据，请先在「账号与配置」登录或点击右上角「刷新课程」"
            >
              <el-table-column type="selection" width="55" :reserve-selection="true" />
              <el-table-column prop="title" label="课程名称" min-width="240" />
              <el-table-column prop="class_name" label="班级" width="200" />
              <el-table-column prop="teacher" label="教师" width="160" />
              <el-table-column prop="courseId" label="课程 ID" width="140" />
            </el-table>
          </el-card>

          <!-- 智慧树课程与视频目录卡片 (完全对齐超星表格与交互) -->
          <el-card v-show="platform === 'treehouse'" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="header-title-group">
                  <el-tag type="success" effect="plain" size="small">智慧树</el-tag>
                  <span>{{ thCatalogHeaderTitle }}</span>
                  <el-tag v-if="thRequest?.title === '课程'" type="primary" size="small">
                    已选 {{ thSelectedRows.length }} / {{ thRequest.choices.length }} 门课程
                  </el-tag>
                  <el-tag v-else-if="thRequest?.title === '视频'" type="warning" size="small">
                    已选 {{ thSelectedRows.length }} / {{ thAllVideoRows.length }} 个视频
                  </el-tag>
                  <el-tag v-else-if="thAllVideoRows.length > 0" type="info" size="small">
                    上次扫描共 {{ thAllVideoRows.length }} 个视频
                  </el-tag>
                </div>
                <div class="header-actions">
                  <template v-if="thRequest">
                    <el-button type="danger" plain @click="cancelThSelection">取消任务</el-button>
                    <el-button
                      type="primary"
                      :disabled="thSelectedRows.length === 0"
                      @click="confirmThSelection"
                    >
                      {{
                        thRequest.title === '课程'
                          ? `扫描所选课程 (${thSelectedRows.length})`
                          : `开始刷课 (${thSelectedRows.length})`
                      }}
                    </el-button>
                  </template>
                  <template v-else>
                    <el-button
                      type="success"
                      :loading="thStarting"
                      :disabled="thRunning"
                      @click="startTreehouse"
                    >
                      {{ thRunning ? '正在连接/扫描中...' : '连接并刷新课程' }}
                    </el-button>
                    <el-button v-if="thRunning" type="danger" @click="stopThTask">
                      停止当前任务
                    </el-button>
                  </template>
                </div>
              </div>
            </template>

            <!-- 智慧树流程阶段提示 -->
            <el-alert
              v-if="thRequest"
              :title="
                thRequest.title === '课程'
                  ? '第 1 步（选课扫描）：请勾选要学习的课程，确认后程序将依次扫描各门课的视频目录（此阶段不会开始播放）。'
                  : '第 2 步（勾选视频）：课程扫描已完成！请勾选需要刷课的视频章节（支持一键「选未完成」），点击「开始刷课」建立播放队列。'
              "
              :type="thRequest.title === '课程' ? 'info' : 'success'"
              :closable="false"
              show-icon
              style="margin-bottom: 14px"
            />
            <el-alert
              v-else-if="thRunning"
              :title="`${thPhaseDisplay}：${thMessage}`"
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom: 14px"
            />

            <!-- 统一搜索与批量操作工具栏 -->
            <div class="catalog-toolbar">
              <div class="toolbar-filters">
                <el-select
                  v-if="thIsVideoMode && thGroups.length > 0"
                  v-model="thActiveCourse"
                  placeholder="全部已扫描课程"
                  clearable
                  style="width: 240px"
                >
                  <el-option label="全部已扫描课程" value="" />
                  <el-option
                    v-for="group in thGroups"
                    :key="group.key"
                    :label="`${group.course.label} (${group.videos.length})`"
                    :value="group.key"
                  />
                </el-select>
                <el-input
                  v-model="thQuery"
                  :placeholder="
                    thIsVideoMode ? '搜索视频章节名称 / 所属课程' : '搜索课程名称 / 详情'
                  "
                  clearable
                  style="width: 280px"
                />
              </div>

              <div class="toolbar-actions" v-if="thRequest">
                <el-button
                  v-if="thRequest.title === '视频'"
                  size="small"
                  type="warning"
                  plain
                  @click="thSelectUnfinished"
                  :disabled="thVisibleTableRows.length === 0"
                >
                  选未完成
                </el-button>
                <el-button
                  size="small"
                  @click="thSelectAllVisible"
                  :disabled="thVisibleTableRows.length === 0"
                >
                  全选当前
                </el-button>
                <el-button
                  size="small"
                  @click="thClearSelection"
                  :disabled="thSelectedRows.length === 0"
                >
                  清空已选
                </el-button>
              </div>
            </div>

            <!-- 智慧树课程/视频表格 -->
            <el-table
              ref="thTableRef"
              :data="thVisibleTableRows"
              row-key="key"
              style="width: 100%"
              max-height="calc(100vh - 290px)"
              @selection-change="handleThSelectionChange"
              @row-click="toggleThRow"
              empty-text="暂无智慧树课程或视频数据，请点击右上角「连接并刷新课程」"
            >
              <el-table-column
                v-if="thRequest"
                type="selection"
                width="55"
                :reserve-selection="true"
              />
              <template v-if="!thIsVideoMode">
                <el-table-column prop="label" label="课程名称" min-width="260" />
                <el-table-column prop="detail" label="课程类型 / 学期说明" min-width="200" />
              </template>
              <template v-else>
                <el-table-column prop="label" label="视频章节名称" min-width="260" />
                <el-table-column prop="courseLabel" label="所属课程" width="220" />
                <el-table-column prop="videoDetail" label="章节信息" width="180" />
                <el-table-column label="完成状态" width="120">
                  <template #default="{ row }">
                    <el-tag
                      :type="
                        row.completed === true
                          ? 'success'
                          : row.completed === false
                            ? 'warning'
                            : 'info'
                      "
                      size="small"
                    >
                      {{
                        row.completed === true
                          ? '已完成'
                          : row.completed === false
                            ? '未完成'
                            : '状态未知'
                      }}
                    </el-tag>
                  </template>
                </el-table-column>
              </template>
            </el-table>
          </el-card>
        </div>

        <!-- ==================== 3. 运行控制面板视图 ==================== -->
        <div v-show="activeIndex === '3'" class="dashboard">
          <!-- 当前进度卡片 (双平台完全统一) -->
          <el-card shadow="never" style="margin-bottom: 20px">
            <template #header>
              <div class="card-header">
                <div class="header-title-group">
                  <el-tag
                    :type="platform === 'chaoxing' ? 'primary' : 'success'"
                    effect="plain"
                    size="small"
                  >
                    {{ platform === 'chaoxing' ? '超星学习通' : '智慧树' }}
                  </el-tag>
                  <span>当前进度</span>
                  <el-tag
                    v-if="platform === 'chaoxing'"
                    :type="cxRunning ? 'success' : 'info'"
                    size="small"
                  >
                    {{ cxRunning ? '运行中' : '空闲' }}
                  </el-tag>
                  <el-tag
                    v-else
                    :type="thRequest ? 'warning' : thRunning ? 'success' : 'info'"
                    size="small"
                  >
                    {{ thPhaseDisplay }}
                  </el-tag>
                </div>

                <div class="header-actions">
                  <el-button
                    v-if="platform === 'treehouse' && thRequest"
                    type="warning"
                    @click="activeIndex = '2'"
                  >
                    前往勾选{{ thRequest.title }} ({{ thRequest.choices.length }})
                  </el-button>
                  <el-button
                    type="danger"
                    :disabled="platform === 'chaoxing' ? !cxRunning : !thRunning"
                    @click="platform === 'chaoxing' ? stopTask() : stopThTask()"
                  >
                    停止当前任务
                  </el-button>
                </div>
              </div>
            </template>

            <!-- 超星进度条区域 -->
            <template v-if="platform === 'chaoxing'">
              <div v-if="Object.keys(progressBars).length === 0" class="empty-progress">
                {{ cxRunning ? '正在读取课程章节并初始化挂机任务...' : '暂无进行中的进度条' }}
              </div>
              <div v-for="(bar, id) in progressBars" :key="id" class="progress-bar-wrapper">
                <div class="progress-label">{{ bar.desc }}</div>
                <el-progress
                  :percentage="
                    bar.total > 0 ? Math.min(100, Number(((bar.n / bar.total) * 100).toFixed(1))) : 0
                  "
                  :format="() => `${bar.n} / ${bar.total}`"
                  :status="bar.n >= bar.total && bar.total > 0 ? 'success' : ''"
                />
              </div>
            </template>

            <!-- 智慧树进度条区域 (与超星采用相同 .progress-bar-wrapper 视觉结构) -->
            <template v-else>
              <div class="th-status-banner">
                <span class="th-status-msg">{{ thMessage }}</span>
                <span v-if="thCurrentCourse" class="th-status-meta">
                  课程：{{ thCurrentCourse }}
                </span>
              </div>

              <!-- 扫描进度条 -->
              <div
                v-if="thScanTotal > 0 && thQueueTotal === 0"
                class="progress-bar-wrapper"
              >
                <div class="progress-label">
                  课程视频目录扫描进度 | {{ thCurrentCourse || '正在扫描所选课程' }}
                </div>
                <el-progress
                  :percentage="
                    Math.min(100, Number(((thScanCurrent / thScanTotal) * 100).toFixed(1)))
                  "
                  :format="() => `${thScanCurrent} / ${thScanTotal}`"
                  :status="thScanCurrent >= thScanTotal ? 'success' : ''"
                />
              </div>

              <!-- 播放队列总进度条 -->
              <div v-if="thQueueTotal > 0" class="progress-bar-wrapper">
                <div class="progress-label">
                  播放队列总进度 | 已完成 {{ thQueueCompleted }} / {{ thQueueTotal }} 个视频
                </div>
                <el-progress
                  :percentage="
                    Math.min(100, Number(((thQueueCompleted / thQueueTotal) * 100).toFixed(1)))
                  "
                  :format="() => `${thQueueCompleted} / ${thQueueTotal}`"
                  :status="thQueueCompleted >= thQueueTotal ? 'success' : ''"
                />
              </div>

              <!-- 当前视频播放进度条 -->
              <div
                v-if="thRunning || thProgress > 0 || thQueueTotal > 0"
                class="progress-bar-wrapper"
              >
                <div class="progress-label">
                  {{ thCurrentVideo ? `当前视频: ${thCurrentVideo}` : thPhaseDisplay }}
                  <span v-if="thVideoDurationSec > 0">
                    | {{ formatDuration(thVideoCurrentSec) }} /
                    {{ formatDuration(thVideoDurationSec) }} ({{ thActualRate }}x)
                  </span>
                </div>
                <el-progress
                  :percentage="thProgress"
                  :status="thProgress >= 100 ? 'success' : ''"
                />
              </div>

              <div
                v-if="!thRunning && thProgress === 0 && thQueueTotal === 0 && thScanTotal === 0"
                class="empty-progress"
              >
                暂无进行中的进度条
              </div>
            </template>
          </el-card>

          <!-- 控制台输出卡片 (双平台完全统一深色终端样式) -->
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>
                  {{ platform === 'chaoxing' ? '超星学习通 · 控制台输出' : '智慧树 · 控制台输出' }}
                </span>
                <el-button size="small" @click="clearCurrentLogs">清空日志</el-button>
              </div>
            </template>
            <div class="log-container" ref="logContainer">
              <div v-if="activeLogs.length === 0" class="log-empty">暂无控制台日志输出...</div>
              <div v-for="(log, index) in activeLogs" :key="index" class="log-item">
                <span style="color: #409eff">[{{ log.time }}]</span> {{ log.msg }}
              </div>
            </div>
          </el-card>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Moon, Sunny, Setting, Reading, Monitor } from '@element-plus/icons-vue'

type LogEntry = { time: string; msg: string }
type ThChoice = { key: string; label: string; detail?: string }
type ThRequest = { request_id: string; title: string; multiple?: boolean; choices: ThChoice[] }
type ThVideoItem = {
  key: string
  label: string
  detail?: string
  signature?: string
  completed?: boolean | null
}
type ThGroup = {
  key: string
  course: ThChoice
  videos: ThVideoItem[]
}
type ThTableRow = {
  key: string
  label: string
  detail: string
  courseGroupKey?: string
  courseLabel?: string
  videoDetail?: string
  completed?: boolean | null
}

const TH_PHASE_LABELS: Record<string, string> = {
  starting: '正在启动浏览器',
  waiting_page: '等待页面渲染',
  waiting_login: '等待浏览器登录/验证码',
  choosing_course: '等待选择课程',
  loading_resources: '正在扫描课程目录',
  choosing_video: '等待勾选视频',
  loading_video: '正在加载播放器',
  playing: '视频播放中',
  complete: '播放完成',
  cancelled: '已停止',
  error: '运行失败'
}

const TH_VALID_RATES = [1, 1.25, 1.5, 1.75, 2, 3, 4]

// 主题切换（启动时 main.ts 已从 localStorage 恢复）
const isDark = ref(document.documentElement.classList.contains('dark'))
const toggleTheme = (val: string | number | boolean) => {
  const dark = Boolean(val)
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem('theme', dark ? 'dark' : 'light')
}

// 顶层平台与三级菜单状态
const platform = ref<'chaoxing' | 'treehouse'>('chaoxing')
const activeIndex = ref('1')
const activeConfigTab = ref('common')
const activeThConfigTab = ref('common')

const switchPlatform = (target: 'chaoxing' | 'treehouse') => {
  platform.value = target
  scrollLogsToBottom()
}

// ==================== 超星状态 ====================
const saving = ref(false)
const savingOnly = ref(false)
const testingApi = ref(false)
const loadingCourses = ref(false)
const cxRunning = ref(false)

const config = ref({
  common: {
    username: '',
    password: '',
    speed: 1.0,
    jobs: 4,
    notopen_action: 'retry',
    retry_interval: 1.0,
    auto_sign: false,
    work_redo_enabled: false,
    work_max_retries: 3,
    add_learning_count: false,
    target_count: 100,
    use_cookies: false,
    verbose: false
  },
  tiku: {
    enabled: false,
    provider: 'TikuYanxi',
    submit: false,
    cover_rate: 0.9,
    tokens: '',
    key: '',
    endpoint: '',
    model: '',
    http_proxy: '',
    delay: 1.0,
    json_mode: false,
    extra_body: '{"thinking": {"type": "disabled"}}',
    likeapi_search: false,
    likeapi_vision: true,
    likeapi_model: 'glm-4.5-air',
    likeapi_retry: true,
    likeapi_retry_times: 3,
    go_authorization: '',
    go_min_interval: 1.0,
    go_retry_times: 3,
    go_retry_backoff: 1.2,
    min_interval_seconds: 3,
    manual_mode_default: 'batch',
    manual_mode_separator: ';',
    url: ''
  },
  notification: {
    provider: '',
    url: '',
    tg_chat_id: ''
  }
})

const tikuProviders = computed<string[]>({
  get: () =>
    String(config.value.tiku.provider || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
  set: (val) => {
    config.value.tiku.provider = val.join(',')
  }
})

const hasTikuProvider = (name: string) => tikuProviders.value.includes(name)
const needTikuToken = computed(() => hasTikuProvider('TikuYanxi') || hasTikuProvider('TikuLike'))
const needLlmConfig = computed(() => hasTikuProvider('SiliconFlow') || hasTikuProvider('AI'))

const courses = ref<any[]>([])
const selectedCourses = ref<any[]>([])
const cxQuery = ref('')
const cxTableRef = ref<any>(null)
const logs = ref<LogEntry[]>([])
const progressBars = ref<Record<string, { desc: string; n: number; total: number }>>({})

const filteredCxCourses = computed(() => {
  const q = cxQuery.value.trim().toLowerCase()
  if (!q) return courses.value
  return courses.value.filter((c) =>
    `${c.title || ''} ${c.class_name || ''} ${c.teacher || ''} ${c.courseId || ''}`
      .toLowerCase()
      .includes(q)
  )
})

// ==================== 智慧树状态 ====================
const thOptions = ref({
  url: '',
  state_path: '',
  remember: true,
  headless: false,
  connection_mode: 'system',
  speed: 1.0,
  username: '',
  password: '',
  embedded_login: true,
  has_state: false
})
const thLoginOpen = ref(false)
const thLoginImage = ref('')
const thLoginImg = ref<HTMLImageElement | null>(null)
let thLoginSeq = 0
let thLoginSize = { width: 1280, height: 720 }
let thLoginPressed = false
let thLoginLastMove = 0
let thLoginTimer: any = null

const thLoginPoint = (e: MouseEvent) => {
  const img = thLoginImg.value
  if (!img) return { x: 0, y: 0 }
  const rect = img.getBoundingClientRect()
  return {
    x: ((e.clientX - rect.left) / rect.width) * thLoginSize.width,
    y: ((e.clientY - rect.top) / rect.height) * thLoginSize.height
  }
}

const onThLoginMouse = (type: 'down' | 'move' | 'up', e: MouseEvent) => {
  if (type === 'down') thLoginPressed = true
  if (type === 'up') {
    if (!thLoginPressed) return
    thLoginPressed = false
  }
  if (type === 'move') {
    if (!thLoginPressed) return
    const now = performance.now()
    if (now - thLoginLastMove < 25) return
    thLoginLastMove = now
  }
  pyApi('treehouse_login_input', { type, ...thLoginPoint(e) })
}

const onThLoginWheel = (e: WheelEvent) => {
  pyApi('treehouse_login_input', { type: 'wheel', ...thLoginPoint(e), dy: e.deltaY })
}

const onThLoginKey = (e: KeyboardEvent) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return
  if (e.key.length === 1) pyApi('treehouse_login_input', { type: 'text', text: e.key })
  else pyApi('treehouse_login_input', { type: 'key', key: e.key })
}

const pollThLoginFrame = async () => {
  if (!thLoginOpen.value) return
  const res = await pyApi('treehouse_login_frame', thLoginSeq)
  if (res && res.success && res.image) {
    thLoginSeq = res.seq
    thLoginSize = { width: res.width, height: res.height }
    thLoginImage.value = `data:image/jpeg;base64,${res.image}`
  }
}

const startThLoginView = () => {
  thLoginSeq = 0
  thLoginImage.value = ''
  thLoginOpen.value = true
  if (!thLoginTimer) thLoginTimer = setInterval(pollThLoginFrame, 150)
}

const stopThLoginView = () => {
  thLoginOpen.value = false
  thLoginPressed = false
  if (thLoginTimer) {
    clearInterval(thLoginTimer)
    thLoginTimer = null
  }
}
const thStarting = ref(false)
const thSaving = ref(false)
const thRunning = ref(false)
const thRequest = ref<ThRequest | null>(null)
const thGroups = ref<ThGroup[]>([])
const thCachedCourses = ref<ThChoice[]>([])
const thActiveCourse = ref('')
const thQuery = ref('')
const thSelectedRows = ref<any[]>([])
const thTableRef = ref<any>(null)

const thPhase = ref('尚未开始')
const thMessage = ref('连接账号后，按步骤选择课程与视频章节。')
const thCurrentCourse = ref('')
const thCurrentVideo = ref('')
const thProgress = ref(0)
const thVideoCurrentSec = ref(0)
const thVideoDurationSec = ref(0)
const thActualRate = ref(1.0)
const thScanCurrent = ref(0)
const thScanTotal = ref(0)
const thQueueCompleted = ref(0)
const thQueueTotal = ref(0)
const thLogs = ref<LogEntry[]>([])

const thPhaseDisplay = computed(() => TH_PHASE_LABELS[thPhase.value] || thPhase.value || '就绪')

const snapThSpeed = (val: number | number[]) => {
  const num = Array.isArray(val) ? val[0] : val
  const nearest = TH_VALID_RATES.reduce((prev, curr) =>
    Math.abs(curr - num) < Math.abs(prev - num) ? curr : prev
  )
  thOptions.value.speed = nearest
}

// 智慧树课程/视频列表统一行数据构建
const thCourseRows = computed<ThTableRow[]>(() => {
  const source = thRequest.value?.title === '课程' ? thRequest.value.choices : thCachedCourses.value
  return source.map((item) => ({
    key: item.key,
    label: item.label,
    detail: item.detail || '智慧树课程'
  }))
})

const thAllVideoRows = computed<ThTableRow[]>(() => {
  const rows: ThTableRow[] = []
  for (const group of thGroups.value) {
    const courseLabel = group.course?.label || '当前课程'
    for (const video of group.videos || []) {
      const videoDetail = video.detail || group.course?.detail || '-'
      rows.push({
        key: video.key,
        label: video.label,
        detail: videoDetail,
        courseGroupKey: group.key,
        courseLabel,
        videoDetail,
        completed: video.completed ?? null
      })
    }
  }
  return rows
})

const thIsVideoMode = computed(() => {
  if (thRequest.value?.title === '课程') return false
  if (thRequest.value?.title === '视频') return true
  return thAllVideoRows.value.length > 0
})

const thCatalogHeaderTitle = computed(() => {
  if (thRequest.value?.title === '课程') return '第 1 步：选择要扫描的课程'
  if (thRequest.value?.title === '视频') return '第 2 步：勾选要播放的视频章节'
  if (thIsVideoMode.value) return '上次扫描的视频章节目录'
  return '选择要挂机的课程与视频'
})

const thVisibleTableRows = computed<ThTableRow[]>(() => {
  const q = thQuery.value.trim().toLowerCase()
  if (!thIsVideoMode.value) {
    return q
      ? thCourseRows.value.filter((r) => `${r.label} ${r.detail}`.toLowerCase().includes(q))
      : thCourseRows.value
  }
  let items = thAllVideoRows.value
  if (thActiveCourse.value) {
    items = items.filter((r) => r.courseGroupKey === thActiveCourse.value)
  }
  if (q) {
    items = items.filter((r) =>
      `${r.label} ${r.courseLabel || ''} ${r.videoDetail || ''}`.toLowerCase().includes(q)
    )
  }
  return items
})

// ==================== 共用控制台与导航计算属性 ====================
const logContainer = ref<HTMLElement | null>(null)
const currentPlatformRunning = computed(() =>
  platform.value === 'chaoxing' ? cxRunning.value : thRunning.value
)
const activeLogs = computed(() => (platform.value === 'chaoxing' ? logs.value : thLogs.value))

const formatNowTime = () => {
  const now = new Date()
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
}

const formatDuration = (sec: number) => {
  const s = Math.max(0, Math.floor(Number(sec) || 0))
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m.toString().padStart(2, '0')}:${rem.toString().padStart(2, '0')}`
}

const scrollLogsToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

const appendCxLog = (msg: string) => {
  logs.value.push({ time: formatNowTime(), msg })
  if (logs.value.length > 1000) logs.value.shift()
  if (platform.value === 'chaoxing') scrollLogsToBottom()
}

const appendThLog = (msg: string) => {
  thLogs.value.push({ time: formatNowTime(), msg })
  if (thLogs.value.length > 1000) thLogs.value.shift()
  if (platform.value === 'treehouse') scrollLogsToBottom()
}

const clearCurrentLogs = () => {
  if (platform.value === 'chaoxing') {
    logs.value = []
  } else {
    thLogs.value = []
  }
}

// 切换菜单
const handleSelect = (key: string) => {
  activeIndex.value = key
  if (key === '2' && platform.value === 'chaoxing' && courses.value.length === 0) {
    fetchCourses()
  }
  if (key === '3') {
    scrollLogsToBottom()
  }
}

// ==================== 超星表格选择与操作 ====================
const handleCxSelectionChange = (val: any[]) => {
  selectedCourses.value = val
}

const toggleCxRow = (row: any) => {
  cxTableRef.value?.toggleRowSelection(row)
}

const cxSelectAllVisible = () => {
  if (!cxTableRef.value) return
  filteredCxCourses.value.forEach((row) => {
    cxTableRef.value.toggleRowSelection(row, true)
  })
}

const cxClearSelection = () => {
  cxTableRef.value?.clearSelection()
}

// ==================== 智慧树表格选择与操作 ====================
const handleThSelectionChange = (val: any[]) => {
  thSelectedRows.value = val
}

const toggleThRow = (row: any) => {
  if (!thRequest.value) return
  thTableRef.value?.toggleRowSelection(row)
}

const thSelectAllVisible = () => {
  if (!thTableRef.value || !thRequest.value) return
  thVisibleTableRows.value.forEach((row) => {
    thTableRef.value.toggleRowSelection(row, true)
  })
}

const thSelectUnfinished = () => {
  if (!thTableRef.value || thRequest.value?.title !== '视频') return
  thVisibleTableRows.value.forEach((row: any) => {
    if (row.completed === false) {
      thTableRef.value.toggleRowSelection(row, true)
    }
  })
}

const thClearSelection = () => {
  thTableRef.value?.clearSelection()
}

// ==================== PyWebView 桥接调用 ====================
const pyApi = async (method: string, ...args: any[]) => {
  if (window.pywebview && window.pywebview.api) {
    return await window.pywebview.api[method](...args)
  } else {
    console.warn(`[Mock] Calling ${method}`, args)
    return { success: false, msg: 'PyWebView 未就绪，正在测试模式运行' }
  }
}

window.updateProgress = (id: string, desc: string, n: number, total: number) => {
  progressBars.value[id] = { desc, n, total }
}

window.addLog = (msg: string) => {
  appendCxLog(msg)
}

// ==================== 超星业务逻辑 ====================
const loadConfig = async () => {
  const res = await pyApi('get_config')
  if (res && res.success && res.data) {
    const mergeObj = (target: any, source: any) => {
      for (const key of Object.keys(source)) {
        if (source[key] instanceof Object && key in target) {
          Object.assign(source[key], mergeObj(target[key], source[key]))
        }
      }
      return Object.assign(target || {}, source)
    }
    config.value = mergeObj(config.value, res.data)
  }
}

const saveCxConfigOnly = async () => {
  savingOnly.value = true
  const res = await pyApi('save_config_only', JSON.stringify(config.value))
  savingOnly.value = false
  if (res && res.success) {
    ElMessage.success('超星配置已保存')
  } else {
    ElMessage.error(res?.msg || '保存配置失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  const res = await pyApi('save_config_and_login', JSON.stringify(config.value))
  saving.value = false
  if (res.success) {
    ElMessage.success('配置已保存并登录成功！')
    activeIndex.value = '2'
    fetchCourses()
  } else {
    ElMessage.error(res.msg || '登录失败，请检查账号密码')
  }
}

const testApi = async () => {
  testingApi.value = true
  const res = await pyApi('test_api_connection', JSON.stringify(config.value))
  testingApi.value = false
  if (res.success) {
    ElMessage.success(res.msg)
  } else {
    ElMessage.error(res.msg)
  }
}

const fetchCourses = async () => {
  loadingCourses.value = true
  const res = await pyApi('get_courses')
  loadingCourses.value = false
  if (res.success) {
    courses.value = res.data
    cxTableRef.value?.clearSelection()
    ElMessage.success(`成功获取 ${courses.value.length} 门超星课程`)
  } else {
    ElMessage.error(res.msg || '获取课程失败，请先登录')
  }
}

const startTask = async () => {
  if (selectedCourses.value.length === 0) return
  const courseIds = selectedCourses.value.map((c) => c.courseId)
  activeIndex.value = '3'
  appendCxLog(`准备开始执行 ${courseIds.length} 门超星课程任务...`)
  const res = await pyApi('start_tasks', JSON.stringify(courseIds))
  if (res.success) {
    cxRunning.value = true
  } else {
    ElMessage.error(res.msg || '启动任务失败')
  }
}

const stopTask = async () => {
  const res = await pyApi('stop_tasks')
  if (res.success) {
    appendCxLog('已发送停止指令...')
  }
}

// ==================== 智慧树业务逻辑 ====================
const loadTreehouseDefaults = async () => {
  const res = await pyApi('treehouse_defaults')
  if (res && res.success && res.data) {
    Object.assign(thOptions.value, res.data)
  }
}

const saveThConfigOnly = async () => {
  thSaving.value = true
  snapThSpeed(thOptions.value.speed)
  const res = await pyApi('treehouse_save_config', thOptions.value)
  thSaving.value = false
  if (res && res.success) {
    if (res.data) Object.assign(thOptions.value, res.data)
    ElMessage.success('智慧树配置已保存')
  } else {
    ElMessage.error(res?.msg || '保存智慧树配置失败')
  }
}

const startTreehouse = async () => {
  thStarting.value = true
  snapThSpeed(thOptions.value.speed)
  try {
    const res = await pyApi('treehouse_start', thOptions.value)
    if (!res || !res.success) {
      ElMessage.error(res?.msg || '启动智慧树连接失败')
      return
    }
    if (res.data) Object.assign(thOptions.value, res.data)
    thRunning.value = true
    thRequest.value = null
    thGroups.value = []
    thSelectedRows.value = []
    thTableRef.value?.clearSelection()
    thProgress.value = 0
    thVideoCurrentSec.value = 0
    thVideoDurationSec.value = 0
    thScanCurrent.value = 0
    thScanTotal.value = 0
    thQueueCompleted.value = 0
    thQueueTotal.value = 0
    thCurrentCourse.value = ''
    thCurrentVideo.value = ''
    thPhase.value = 'starting'
    thMessage.value = '浏览器正在启动，首次使用请在浏览器中完成登录。'
    appendThLog('已保存智慧树配置并启动浏览器连接任务...')
    platform.value = 'treehouse'
    activeIndex.value = '3'
  } finally {
    thStarting.value = false
  }
}

const confirmThSelection = async () => {
  if (!thRequest.value || thSelectedRows.value.length === 0) return
  const keys = thSelectedRows.value.map((r) => r.key)
  const isCourseStep = thRequest.value.title === '课程'
  const res = await pyApi('treehouse_select', thRequest.value.request_id, keys)
  if (!res || !res.success) {
    ElMessage.error(res?.msg || '提交选择失败')
    return
  }
  thRequest.value = null
  thSelectedRows.value = []
  thQuery.value = ''
  thTableRef.value?.clearSelection()
  if (isCourseStep) {
    thPhase.value = 'loading_resources'
    thMessage.value = `正在依次扫描所选 ${keys.length} 门课程的视频章节...`
    ElMessage.info(`开始扫描 ${keys.length} 门课程的视频章节`)
  } else {
    thPhase.value = 'loading_video'
    thMessage.value = `已确认 ${keys.length} 个视频，正在启动自动播放队列...`
    ElMessage.success(`已开始播放所选的 ${keys.length} 个视频`)
  }
  activeIndex.value = '3'
}

const cancelThSelection = async () => {
  const reqId = thRequest.value?.request_id || ''
  await pyApi('treehouse_cancel_selection', reqId)
  thRequest.value = null
  thSelectedRows.value = []
  thTableRef.value?.clearSelection()
  thMessage.value = '已取消选择并停止当前任务。'
  appendThLog('用户取消了目录选择，正在停止任务...')
}

const stopThTask = async () => {
  await pyApi('treehouse_stop')
  thRequest.value = null
  thMessage.value = '正在停止智慧树任务…'
  appendThLog('已发送停止智慧树任务指令...')
}

// ==================== 轮询同步双平台状态 ====================
const pollUpdates = async () => {
  // 1. 超星状态轮询
  try {
    const res = await pyApi('get_ui_updates')
    if (res && res.success) {
      if (typeof res.running === 'boolean') {
        cxRunning.value = res.running
      }
      if (res.logs && res.logs.length > 0) {
        res.logs.forEach((msg: string) => appendCxLog(msg))
      }
      if (res.progress) {
        progressBars.value = res.progress
      }
    }
  } catch {
    // 忽略轮询异常
  }

  // 2. 智慧树状态轮询
  try {
    const thRes = await pyApi('treehouse_updates')
    if (thRes && thRes.success) {
      thRunning.value = Boolean(thRes.running)
      for (const event of thRes.events || []) {
        const data = event.data || {}
        if (event.kind === 'phase') {
          thPhase.value = data.phase
          thMessage.value = data.message
        } else if (event.kind === 'log') {
          appendThLog(data.message)
        } else if (event.kind === 'login_open') {
          startThLoginView()
        } else if (event.kind === 'login_done') {
          stopThLoginView()
        } else if (event.kind === 'session_saved') {
          thOptions.value.state_path = data.path
          thOptions.value.has_state = true
        } else if (event.kind === 'selected') {
          if (data.category === '课程') {
            thCurrentCourse.value = data.choice?.label || ''
          } else if (data.category === '视频') {
            thCurrentVideo.value = data.choice?.label || ''
          }
        } else if (event.kind === 'scan_progress') {
          thScanCurrent.value = Number(data.current) || 0
          thScanTotal.value = Number(data.total) || 0
          thCurrentCourse.value = data.course?.label || thCurrentCourse.value
          thMessage.value = data.message || thMessage.value
        } else if (event.kind === 'catalog_ready') {
          thGroups.value = data.groups || []
          thActiveCourse.value = ''
        } else if (event.kind === 'selection_request') {
          if (data.title === '课程') {
            thCachedCourses.value = data.choices || []
          }
          thRequest.value = data
          thSelectedRows.value = []
          thQuery.value = ''
          thActiveCourse.value = ''
          nextTick(() => {
            thTableRef.value?.clearSelection()
          })
          platform.value = 'treehouse'
          activeIndex.value = '2'
          ElMessage.info(
            data.title === '课程'
              ? '智慧树课程列表已就绪，请勾选要扫描的课程'
              : '智慧树视频扫描完成，请勾选要播放的视频'
          )
        } else if (event.kind === 'queue') {
          thQueueCompleted.value = Number(data.completed) || 0
          thQueueTotal.value = Number(data.total) || 0
          thProgress.value = 0
        } else if (event.kind === 'progress') {
          thProgress.value = Math.max(0, Math.min(100, Number((Number(data.percent) || 0).toFixed(1))))
          thVideoCurrentSec.value = Number(data.current) || 0
          thVideoDurationSec.value = Number(data.duration) || 0
          if (data.playback_rate) {
            thActualRate.value = Number(data.playback_rate) || thOptions.value.speed
          }
        } else if (event.kind === 'finished') {
          stopThLoginView()
          thRunning.value = false
          thRequest.value = null
          thPhase.value = data.status
          thMessage.value = data.message
          if (data.status === 'complete') {
            thProgress.value = 100
            ElMessage.success(data.message || '智慧树播放队列已完成')
          } else if (data.status === 'error') {
            ElMessage.error(data.message || '智慧树运行出现异常')
          }
        }
      }
    }
  } catch {
    // 忽略轮询异常
  }
}

let pollTimer: any = null

onMounted(() => {
  const initAll = () => {
    loadConfig()
    loadTreehouseDefaults()
    if (!pollTimer) pollTimer = setInterval(pollUpdates, 500)
  }
  window.addEventListener('pywebviewready', initAll)
  if (!window.pywebview) {
    setTimeout(initAll, 600)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style>
.th-login-hint {
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.th-login-stage {
  outline: none;
  display: flex;
  justify-content: center;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
  min-height: 300px;
}
.th-login-frame {
  width: 100%;
  display: block;
  cursor: pointer;
  user-select: none;
}
.th-login-loading {
  align-self: center;
  color: var(--el-text-color-secondary);
}

html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100vh;
  width: 100%;
  max-width: 100%;
  text-align: left;
  border: none;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    sans-serif;
}

body {
  background-color: var(--el-bg-color-page);
  color: var(--el-text-color-primary);
  transition: background-color 0.3s ease;
}

.layout-container {
  height: 100vh;
}

.aside {
  background-color: #304156;
  color: white;
  display: flex;
  flex-direction: column;
  user-select: none;
}

.logo {
  padding: 14px 12px 12px;
  text-align: center;
  border-bottom: 1px solid #1f2d3d;
}

.logo-icon {
  width: 24px;
  height: 24px;
  margin-right: 8px;
  vertical-align: -5px;
}

.logo h3 {
  margin: 0;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}

.logo-sub {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #909399;
}

/* 平台切换器 */
.platform-switcher {
  padding: 12px 12px 10px;
  border-bottom: 1px solid #1f2d3d;
}

.switcher-label {
  font-size: 11px;
  color: #889aa4;
  margin-bottom: 8px;
  padding-left: 2px;
}

.switcher-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  background-color: #263445;
  padding: 4px;
  border-radius: 6px;
}

.platform-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: none;
  border-radius: 4px;
  padding: 7px 6px;
  font-size: 12px;
  font-weight: 500;
  color: #bfcbd9;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.platform-btn:hover {
  color: #ffffff;
}

.platform-btn.active {
  background-color: #409eff;
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(64, 158, 255, 0.35);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.running {
  background-color: #67c23a;
  box-shadow: 0 0 6px #67c23a;
}

.status-dot.waiting {
  background-color: #e6a23c;
  box-shadow: 0 0 6px #e6a23c;
}

.side-menu {
  border-right: none;
  flex: 1;
}

.menu-badge {
  margin-left: auto;
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 0;
  border-top: 1px solid #1f2d3d;
}

.theme-label {
  color: #bfcbd9;
  font-size: 13px;
}

.main-content {
  padding: 20px;
  overflow-y: auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.header-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.aligned-form {
  max-width: 640px;
}

.config-actions {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  gap: 12px;
}

.catalog-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}

.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dashboard {
  display: flex;
  flex-direction: column;
}

.th-status-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 6px;
  background-color: var(--el-fill-color-light);
  font-size: 13px;
}

.th-status-msg {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.th-status-meta {
  color: var(--el-text-color-secondary);
}

.empty-progress {
  color: var(--el-text-color-secondary);
  text-align: center;
  padding: 16px 0;
  font-size: 13px;
}

.progress-bar-wrapper {
  margin-bottom: 15px;
}

.progress-label {
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--el-text-color-regular);
}

.log-container {
  height: calc(100vh - 380px);
  min-height: 220px;
  overflow-y: auto;
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.5;
}

.log-empty {
  color: #777;
  font-style: italic;
}

.log-item {
  margin-bottom: 4px;
  word-break: break-all;
}

.field-hint {
  width: 100%;
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.advanced-collapse {
  margin: 8px 0 18px 150px;
  width: calc(100% - 150px);
  border-top: none;
}
</style>
