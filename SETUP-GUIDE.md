# LeadFlow AI — 完整安装指南

写给非技术人员的保姆级安装教程。跟着做就行。

---

## 总共只需要 3 步

| 步骤 | 做什么 | 花多久 |
|------|--------|--------|
| 1 | 安装 Docker Desktop + Node.js | 10 分钟（一次性） |
| 2 | 注册 Kimi AI 获取密钥 | 5 分钟（一次性） |
| 3 | 复制粘贴 3 行命令 | 5 分钟 |

---

## 第一步：安装两个软件（一次性，以后不用再装）

### 1A. 安装 Docker Desktop

Docker 是一个「虚拟环境」工具，让你不用手动装数据库等复杂软件。

1. 打开这个网址：https://www.docker.com/products/docker-desktop/
2. 点「Download」下载对应你系统的版本（Mac / Windows）
3. 双击安装包，一路下一步安装
4. 打开 Docker Desktop，等它启动完成（任务栏/菜单栏出现鲸鱼图标就好了）

> Windows 用户：安装时如果提示需要 WSL2，按提示安装即可。

### 1B. 安装 Node.js

Node.js 是运行浏览器控制工具需要的。

1. 打开这个网址：https://nodejs.org/
2. 点左边那个绿色的 **LTS** 按钮下载
3. 双击安装包，一路下一步安装

### 验证（可选）

打开终端（Mac 叫 Terminal，Windows 叫 PowerShell），输入：

```
docker --version
node --version
```

两行都有版本号输出就对了。

---

## 第二步：注册 Kimi AI 获取密钥

### 什么是密钥（API Key）？

就是一个「通行证」，让系统能调用 AI 来帮你分析客户。
Kimi 是国产 AI（月之暗面出品），注册就送免费额度，不用花钱。

### 怎么获取？

1. 打开这个网址：https://platform.moonshot.cn/
2. 点「注册」，用手机号注册一个账号
3. 登录后，在左侧菜单找到 **「API Key 管理」**
4. 点 **「新建」**
5. 点 **「复制」**

你会得到一个长这样的字符串：

```
sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**先别关这个页面，等一下要用。**

---

## 第三步：复制粘贴 3 行命令

打开终端（Mac 叫 Terminal，Windows 叫 PowerShell），把下面 3 行复制粘贴进去：

```bash
git clone --recurse-submodules https://github.com/JOZUJIOJIO/fb-lead-gen.git
cd fb-lead-gen
bash one-click-setup.sh
```

然后脚本会自动引导你，整个过程长这样：

```
╔═════════════════════════════════════════╗
║                                         ║
║   LeadFlow AI — 智能外贸获客平台       ║
║                                         ║
║   跟着提示一步步来，5 分钟搞定安装     ║
║                                         ║
╚═════════════════════════════════════════╝

准备好了吗？按回车开始...            ← 按回车

━━━━━ [1/4] 检查环境依赖 ━━━━━
  ✅ Docker 已安装并运行
  ✅ Node.js v18.x.x
  ✅ Python 3.x.x

━━━━━ [2/4] 配置系统 ━━━━━
  请把 Key 粘贴到这里，然后按回车:    ← 粘贴你的 sk-xxx，回车

  ✅ Key 格式正确
  ✅ 配置已保存

━━━━━ [3/4] 启动系统 ━━━━━
  正在启动 5 个服务（首次需要 3-5 分钟）...
  ✅ 后端 API 已就绪
  ✅ 前端已就绪

━━━━━ [4/4] 安装浏览器控制工具 ━━━━━
  ✅ OpenCLI 安装完成
  ✅ Python 依赖安装完成

╔═════════════════════════════════════════╗
║                                         ║
║        安装完成！系统已在运行           ║
║                                         ║
╚═════════════════════════════════════════╝
```

**你唯一需要做的就是粘贴那个 API Key，其他全自动。**

安装完成后浏览器会自动打开 http://localhost:3000，用以下账号登录：

- 邮箱：`admin@leadflow.com`
- 密码：`admin123456`

---

## 第四步：安装 Chrome 扩展（一次性）

这个扩展让系统能操控你的 Chrome 浏览器去 Facebook 找客户。

### 为什么需要这个？

你的 Chrome 已经登录了 Facebook 对吧？这个扩展让系统能借用你的浏览器去搜索客户，就像你自己在操作一样。它不会偷你的密码。

### 怎么装？

1. 打开 Chrome 浏览器

2. 在地址栏输入下面这行，回车：
   ```
   chrome://extensions/
   ```

3. 把右上角的 **「开发者模式」** 开关打开（向右拨）

4. 点左上角的 **「加载已解压的扩展程序」** 按钮

5. 在弹出的文件选择器中，找到你刚才下载的项目文件夹，打开里面的：
   ```
   fb-lead-gen → opencli-vendor → extension
   ```
   选中 `extension` 这个文件夹，点「选择」

6. 扩展列表里出现 **「OpenCLI Browser Bridge」** 就安装成功了

> 这个只需要装一次，以后都不用管了。

---

## 第五步：在 Chrome 里登录 Facebook

1. 在 Chrome 中打开 https://www.facebook.com/
2. 确认你已经登录了（能看到动态消息，不是登录页面）
3. 保持 Chrome 开着

---

## 全部完成！开始使用

打开 http://localhost:3000 登录后，你可以：

- **搜索客户** — 输入「LED lighting importer Southeast Asia」等关键词
- **AI 分析** — 自动评估每个客户的购买意向
- **发送私信** — 给高质量客户发个性化打招呼消息
- **自动对话** — AI 在 10 轮对话内引导客户加 WhatsApp

---

## 日常操作速查

| 操作 | 命令 |
|------|------|
| 开机后启动系统 | `cd fb-lead-gen && docker compose up -d` |
| 关机前停止系统 | `docker compose down` |
| 看日志排查问题 | `docker compose logs -f` |
| 重启系统 | `docker compose restart` |
| 更新代码后重新构建 | `docker compose down && docker compose up -d --build` |

> 启动后系统就在后台运行了，关掉终端也没关系。

---

## 常见问题

### Docker 启动时报错说端口被占用？
关掉占用端口的程序，或者重启电脑后再试。

### 打开 localhost:3000 白屏？
前端可能还在构建，等 30 秒再刷新。或者看日志：`docker compose logs frontend`

### Facebook 搜索没结果？
1. 确认 Chrome 已登录 Facebook
2. 确认 OpenCLI 扩展已安装（`chrome://extensions/` 里能看到）
3. 终端运行 `opencli doctor` 检查连接状态

### 第一次构建很慢？
正常，第一次需要下载镜像和构建代码，大约 3-5 分钟。之后每次启动只需几秒。

### 想换电脑用？
在新电脑上重新跑一遍第一步到第四步就行。数据保存在 Docker 里，不会丢。
