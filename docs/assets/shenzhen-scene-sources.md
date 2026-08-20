# 深圳辖区实景素材与地图来源

本清单对应 `public/assets/shenzhen-scenes/`。十张图片均来自 Wikimedia Commons 的实拍、自有作品文件页，不使用生成式图片或新闻转载图片。

坐标采用 Commons 文件页的 `Camera location`，为 WGS84，经纬度顺序为 `lat, lng`。本地展示图均未裁切；仅在保持原始长宽比的前提下缩小，坪山文件另按真实 MIME 类型保存为 PNG。

## 十区/新区实景

| 辖区 | 场景与坐标 | 本地文件 | 作者与许可 | Commons 原页 | 本地处理 |
| --- | --- | --- | --- | --- | --- |
| 福田区 | 深圳市民中心；22.548893, 114.053467 | `futian-civic-center.jpg` | Dinkun Chen；CC BY-SA 4.0 | [CIVIC CENTER, SHENZHEN (9).jpg](https://commons.wikimedia.org/wiki/File%3ACIVIC_CENTER%2C_SHENZHEN_%289%29.jpg) | 未裁切，等比缩小至 1920×798 |
| 罗湖区 | 深圳站广场；22.534750, 114.113875 | `luohu-railway-station.jpg` | N509FZ；CC BY-SA 4.0 | [Shenzhen Railway Station (20160811120449).jpg](https://commons.wikimedia.org/wiki/File%3AShenzhen_Railway_Station_%2820160811120449%29.jpg) | 未裁切，等比缩小至 1920×1230 |
| 南山区 | 深圳湾公园；22.523103, 113.994411 | `nanshan-bay-park.jpg` | GangZhao；CC BY-SA 4.0 | [Shenzhen Bay Park.jpg](https://commons.wikimedia.org/wiki/File%3AShenzhen_Bay_Park.jpg) | 未裁切，等比缩小至 1920×1440 |
| 盐田区 | 盐田海鲜街滨水步道；22.586017, 114.271298 | `yantian-waterfront.jpg` | MACAHWM Bewizo Hom；CC0 1.0 | [Yantian Seafood Street waterfront](https://commons.wikimedia.org/wiki/File%3ASZ_%E6%B7%B1%E5%9C%B3_Shenzhen_%E9%B9%BD%E7%94%B0%E5%8D%80_Yantian_%E6%B5%B7%E9%AE%AE%E8%A1%97_Seafood_Street_promenade_waterfront_map_sign_May_2025_R12S.jpg) | 未裁切，等比缩小至 1280×960 |
| 宝安区 | 宝源路城市道路；22.558595, 113.875155 | `baoan-baoyuan-road.jpg` | ZHONG 82035 WANGZ；CC0 1.0 | [BaoYuan Road July 2024](https://commons.wikimedia.org/wiki/File%3ASZ_%E6%B7%B1%E5%9C%B3_Shenzhen_%E5%AF%B6%E5%AE%89_BaoAn_%E5%AF%B6%E6%BA%90%E8%B7%AF_BaoYuan_Road_July_2024_R12S_06.jpg) | 未裁切，等比缩小至 1280×960 |
| 龙岗区 | 深圳大运中心；22.695508, 114.210808 | `longgang-universiade.jpg` | Stephen Woolverton；CC BY-SA 4.0 | [ShenZhen Universiade Sports Centre.jpg](https://commons.wikimedia.org/wiki/File%3AShenZhen_Universiade_Sports_Centre.jpg) | 未裁切，保留原始 1632×989 |
| 龙华区 | 深圳北站；22.615228, 114.027602 | `longhua-north-station.jpg` | Percival Kestreltail；CC BY-SA 4.0 | [Shenzhen North railway station by drone.jpg](https://commons.wikimedia.org/wiki/File%3AShenzhen_North_railway_station_by_drone.jpg) | 未裁切，等比缩小至 1920×1080 |
| 坪山区 | 深圳坪山站；22.709261, 114.323028 | `pingshan-railway-station.png` | Min Zi LRC；CC BY-SA 4.0 | [Shenzhen Pingshan Exterior](https://commons.wikimedia.org/wiki/File%3AShenzhen_Pingshan_%28%E6%B7%B1%E5%9C%B3%E5%9D%AA%E5%B1%B1%29_Exterior_G_S_%282023-03-04%29.webp) | 未裁切，使用 Wikimedia 1280px PNG 缩略图（1280×960）；Commons 标题后缀虽为 `.webp`，文件实际 MIME 为 PNG，故本地按 `.png` 保存 |
| 光明区 | 科学公园站周边；22.781083, 113.928350 | `guangming-science-park.jpg` | Minlsonga 663 Shaimz；CC BY-SA 4.0 | [Science Park Station nearby sidewalk](https://commons.wikimedia.org/wiki/File%3ASZ_%E6%B7%B1%E5%9C%B3_Shenzhen_%E5%85%89%E6%98%8E%E6%96%B0%E5%8D%80_Guangming_%E7%A7%91%E5%AD%A6%E5%85%AC%E5%9B%AD%E7%AB%99_Science_Park_Station_nearby_sidewalk_night_October_2023_R12S_01.jpg) | 未裁切，等比缩小至 1280×960 |
| 大鹏新区 | 大鹏所城；22.598845, 114.509750 | `dapeng-fortress.jpg` | Dinkun Chen；CC BY-SA 4.0 | [Dapeng Fortress, Shenzhen.jpg](https://commons.wikimedia.org/wiki/File%3ADapeng_Fortress%2C_Shenzhen.jpg) | 未裁切，等比缩小至 1280×854 |

许可说明：

- [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)：展示时保留作者、来源页和许可；若裁切、调色或做其他改作，应标明修改并按相同或兼容许可发布。
- [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)：不强制署名，但本项目仍显示作者和来源以便审计。
- 页面中的“辖区实景 · 非实时监控”用于明确这些照片是场景参考，不是摄像头直播，也不承载积水识别结果。

## Leaflet、OpenStreetMap 与备用底图

本项目使用 Leaflet 1.9.4，优先按官方标准瓦片地址加载 OpenStreetMap。连续瓦片错误达到阈值后切换到 CARTO Positron；两个在线源都失败时显示项目内置的 CSS 简化背景，风险点位和辖区实景仍可操作。

```js
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
});
```

必须持续遵守以下要求：

1. [Leaflet Quick Start](https://leafletjs.com/examples/quick-start/) 说明 Leaflet 与瓦片供应商解耦，使用 OSM 数据时署名是必需的。
2. [OSMF Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/) 要求使用准确的 HTTPS URL、展示可见署名、发送有效 User-Agent/Referer，并遵守服务端缓存头；不得批量抓取、预取整片区域或提供离线下载。
3. [OSMF Attribution Guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines) 要求署名清晰、可读且靠近地图；交互地图通常放在地图角落，并提供许可入口。
4. [OpenStreetMap Copyright](https://www.openstreetmap.org/copyright) 说明地图数据采用 ODbL，应显示 “© OpenStreetMap contributors” 并链接至许可页。

OSM 标准瓦片是社区维护的尽力服务，CARTO 公共底图也不作为本项目的生产 SLA。三级降级用于保证公开演示可理解、可操作，不等于生产地图保障。若进入正式生产、高并发或离线场景，应切换到符合业务容量、境内访问和离线条款的瓦片服务商，或自建瓦片服务。
