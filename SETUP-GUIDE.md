# LeadFlow AI — 完整安装指南

写给非技术人员的保姆级安装教程。跟着做就行。

---

## 你需要准备什么

| 东西 | 说明 | 大概花多久 |
|------|------|-----------|
| 一台电脑 | Mac / Windows / Linux 均可 | — |
| Chrome 浏览器 | 用来操控 Facebook 找客户 | 已有就跳过 |
| Facebook 账号 | 在 Chrome 中登录好 | 已有就跳过 |
| Kimi API Key | AI 分析客户用的（免费额度够用） | 5 分钟 |

---

## 第一步：安装 Docker Desktop

Docker 是一个「虚拟环境」工具，让你不用手动装数据库等复杂软件。

1. 打开 https://www.docker.com/products/docker-desktop/
2. 下载对应你系统的版本（Mac / Windows）
3. 安装，打开，等它启动完成（任务栏出现鲸鱼图标就好了）

> Windows 用户：安装时如果提示需要 WSL2，按提示安装即可。

---

## 第二步：安装 Node.js

Node.js 是运行浏览器控制工具用的。

1. 打开 https://nodejs.org/
2. 下载 **LTS 版本**（左边那个绿色按钮）
3. 安装，一路 Next 即可

验证：打开终端（Mac 叫 Terminal，Windows 叫 PowerShell），输入：
```
node --version
```
看到 `v18.x.x` 或更高就对了。

---

## 第三步：获取 Kimi API Key

### 什么是 API Key？

API Key 就是一个「通行证」，让 LeadFlow 能调用 Kimi AI 来分析客户。
Kimi 是月之暗面做的 AI（类似 ChatGPT），注册就有免费额度。

### 怎么获取？

1. 打开 https://platform.moonshot.cn/
2. 注册账号（用手机号就行）
3. 登录后，进入「API 管理」或「API Keys」页面
4. 点击「创建新的 API Key」
5. 复制生成的 Key（长这样：`sk-xxxxxxxxxxxxxxxx`）

> 保存好这个 Key，后面要用。不要分享给别人。
>
> 免费额度通常够测试使用。如果用完了，充值很便宜。
>
> 如果你有 Anthropic（Claude）的 API Key，也可以用，但 Kimi 对中文更友好。

---

## 第四步：下载项目并启动

打开终端，依次输入以下命令：

```bash
# 1. 下载项目代码
git clone --recurse-submodules https://github.com/JOZUJIOJIO/fb-lead-gen.git

# 2. 进入项目文件夹
cd fb-lead-gen

# 3. 创建配置文件
cp backend/.env.example backend/.env
```

### 编辑配置文件

用任意文本编辑器打开 `backend/.env` 文件，找到这几行并修改：

```
# 把 sk-xxx 替换成你刚才获取的 Kimi API Key
KIMI_API_KEY=sk-你的真实Key粘贴在这里

# 把这行改成一个随机字符串（随便打一串字母数字就行）
SECRET_KEY=随便打一串比如abc123def456ghi789
```

其他的不用改。保存文件。

> Mac 上可以用 `nano backend/.env` 编辑，改完按 Ctrl+X → Y → Enter 保存。
> Windows 上可以用记事本打开这个文件。

### 启动！

```bash
docker compose up -d
```

第一次启动会下载和构建，大约需要 3-5 分钟。之后每次启动只需几秒。

看到类似这样的输出就成功了：
```
✔ Container fb-lead-gen-postgres-1      Started
✔ Container fb-lead-gen-redis-1         Started
✔ Container fb-lead-gen-backend-1       Started
✔ Container fb-lead-gen-celery_worker-1 Started
✔ Container fb-lead-gen-frontend-1      Started
```

打开浏览器访问 **http://localhost:3000**，看到登录页面就说明 Web 应用已经跑起来了！

默认账号：
- 邮箱：`admin@leadflow.com`
- 密码：`admin123456`

---

## 第五步：安装浏览器控制工具

这一步让系统能控制你的 Chrome 去 Facebook 自动找客户。

```bash
bash install-agent.sh
```

这个脚本会自动安装 OpenCLI 和相关依赖。

---

## 第六步：安装 Chrome 扩展（Browser Bridge）

### 这个扩展是什么？

Browser Bridge 是一个 Chrome 浏览器扩展（插件），它的作用是**让 LeadFlow 系统能和你的 Chrome 浏览器通信**。

具体来说：
- 你在 Chrome 里已经登录了 Facebook 对吧？
- 这个扩展让 LeadFlow 可以通过你已经登录的 Chrome 去 Facebook 搜索客户
- **它不会偷你的密码**，只是在你的浏览器里执行搜索和数据提取操作
- 跟那些广告拦截器、翻译插件一样，是一个普通的 Chrome 扩展

### 怎么安装？

1. 打开 Chrome 浏览器
2. 地址栏输入 `chrome://extensions/` 回车
3. 右上角打开 **「开发者模式」** 开关
4. 点击左上角 **「加载已解压的扩展程序」** 按钮
5. 在弹出的文件选择器中，找到项目文件夹里的：
   ```
   fb-lead-gen/opencli-vendor/extension/
   ```
   选择这个 `extension` 文件夹，点确定
6. 看到扩展列表里出现 **「OpenCLI Browser Bridge」** 就安装成功了

> 这个扩展安装一次就行，以后不用再装。

### 验证安装

打开终端输入：
```bash
opencli doctor
```

看到类似这样的输出就说明一切正常：
```
✔ Daemon: running
✔ Extension: connected
```

---

## 第七步：确保 Chrome 已登录 Facebook

1. 在 Chrome 中打开 https://www.facebook.com/
2. 确认你已经登录（能看到动态信息流，不是登录页面）
3. 保持 Chrome 开着不要关

这样 LeadFlow 就能通过你的 Chrome 去 Facebook 找客户了。

---

## 完成！开始使用

打开 **http://localhost:3000**，登录后你可以：

1. **搜索客户** — 输入关键词（如「LED lighting importer」），系统会操控 Chrome 去 Facebook 搜索
2. **AI 分析** — 自动用 AI 评估每个客户的购买意向
3. **发送私信** — 给高质量客户自动发送个性化打招呼消息
4. **跟进对话** — AI 自动进行多轮对话，引导客户加 WhatsApp

---

## 日常操作

### 每天开机后

```bash
# 进入项目文件夹
cd fb-lead-gen

# 启动系统
docker compose up -d

# 打开 Chrome，确认 Facebook 已登录
```

然后打开 http://localhost:3000 就能用了。

### 关机前

```bash
docker compose down
```

### 出了问题？

```bash
# 看后端日志
docker compose logs backend

# 看前端日志
docker compose logs frontend

# 重启所有服务
docker compose restart

# 彻底重建（如果更新了代码）
docker compose down && docker compose up -d --build
```

---

## 常见问题

### Q: Docker 启动报错端口被占用？
A: 说明 5432 或 6379 端口被其他程序占了。关掉占用的程序，或者在 `docker-compose.yml` 里改端口映射。

### Q: 打开 localhost:3000 白屏？
A: 前端可能还在构建，等 30 秒再刷新。或者看日志：`docker compose logs frontend`

### Q: Facebook 搜索没结果？
A: 确认 Chrome 已登录 Facebook，并且 OpenCLI 扩展已安装。运行 `opencli doctor` 检查。

### Q: API Key 报错？
A: 确认 `backend/.env` 里的 `KIMI_API_KEY=sk-xxx` 是你真实的 Key，没有多余的空格或引号。

### Q: 每次都要手动输命令吗？
A: `docker compose up -d` 之后服务就在后台运行了，关掉终端也没关系。除非你重启电脑或手动 `docker compose down`，否则一直在跑。
