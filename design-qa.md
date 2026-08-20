# 预鉴平台最终设计验收

- 验收日期：2026-07-10
- 最终结果：`passed`

## 对比资产

| 类型 | 文件 |
| --- | --- |
| source | `design/selected-reference.png` |
| implementation | `design/platform-preview.png` |
| comparison | `design/qa-comparison.jpg` |

## 验收视口

- 主研判页：`1440 × 1024`
- 次级页面：`1600 × 1000`

## 已修复项

- 预测值统一为 15/30/60 分钟 `38 / 51 / 47 cm`。
- 预测图补充浅蓝不确定性区间，tooltip 保持显示主预测值。
- 预测图与 DEM 图关闭入场动画，确保首屏与自动截图稳定。
- DEM “最大 22 cm”标记改为数据索引 6，并经像素测量确认位于绘图区水平中心。
- 全站字号完成可读性校准，正文、表格、按钮和状态信息不再使用过小字号。
- favicon 显式指向现有 `/assets/city-basemap.png`，消除 `/favicon.ico` 404。
- BrowserRouter 启用 `v7_startTransition` 与 `v7_relativeSplatPath` future flags，消除 React Router v7 提示。

## 浏览器交互回归

- 原始证据弹窗可打开，证据快照与结构化数据正常展示。
- 人工复核表单可填写，指派队列可切换，随后取消可正常关闭且不改变事件状态。
- 发布确认弹窗可打开，发布渠道可查看，随后取消可正常关闭且不触发发布。
- 七个路由均可访问，主研判、全域态势、预警事件、推演沙盘、路况养护、设备运维、审计存证无横向溢出。
- 模拟器可切换场景预设、注入低质量帧、将影响面积设置为 `320`、运行得到 `56%` 结果，并可恢复预设状态。

## Playwright 验收结果

| 检查项 | 结果 |
| --- | --- |
| Console Errors | `0` |
| Console Warnings | `0` |
| imagesOk | `true` |
| fonts | `loaded` |

## Issue #3 深圳实景与认证增强终验

### 新增预览资产

| 场景 | 文件 |
| --- | --- |
| 登录页 | design/login-preview.png |
| 福田红色预警 | design/shenzhen-overview-red.png |
| 南山黄色预警 | design/shenzhen-overview-yellow.png |

### 浏览器验收结果

- 错误密码会显示“用户名或密码错误”；正确账号可进入平台，退出后回到 /login。
- 地区选择包含全部辖区和深圳十个区/新区；福田、南山、盐田切换后地图、详情与真实公开实景同步变化。
- 福田为 critical 红色全页光晕，南山为 medium 黄色全页光晕，盐田为 none；无匹配筛选会同步清空详情与光晕。
- OpenStreetMap 署名可见；瓦片与场景图片加载完成；页面横向溢出为 0。
- “查看事件详情”可携带深圳点位上下文进入 /events。
- 隔离 Playwright 会话：Console Errors 0，Console Warnings 0。
## 结论

最终设计、交互、响应式布局与浏览器运行状态均通过验收。

`passed`
