# ERPNext Tools

ERPNext Tools 是一个面向 Frappe v16 / ERPNext v16 的独立自定义应用，为企业内部工具提供统一入口。

本应用不修改 Frappe 或 ERPNext 核心代码，可以独立维护、升级和回滚。后续可用于集成现金流与财务辅助、报价与装柜、项目管理、OA 等内部工具。

## 核心功能

- 在 Frappe v16 应用桌面提供独立的 **Tools** 入口；
- 提供动态工具首页 `/app/tools`；
- 通过 **Tool Category** 管理工具分类；
- 通过 **Tool Definition** 注册和维护工具；
- 支持 ERPNext 内部页面和外部 HTTPS 工具；
- 支持启用、停用、排序、图标及颜色配置；
- 支持根据用户角色显示不同工具；
- 安装和迁移时自动创建基础角色及默认分类。

## 权限设计

应用包含两个专用角色：

| 角色 | 权限 |
| --- | --- |
| Tools User | 进入 Tools 首页并使用有权访问的工具 |
| Tools Manager | 管理工具分类和工具注册信息 |
| System Manager | 管理并访问全部 Tools 功能 |

每个工具还可以设置额外的 **Required Role**。普通用户只有拥有相应角色时才会看到该工具。权限检查在服务端执行，不能通过修改浏览器页面绕过。

## 工具注册方式

工具分为两类：

1. **Desk Route**：ERPNext/Frappe 内部页面，例如 `/app/quotation`；
2. **External URL**：独立的外部工具，必须使用有效的 `https://` 地址。

轻量工具只需新增一条 Tool Definition，无需修改首页源码。规模较大的业务工具可以作为本应用的新模块开发，也可以拆分为独立 Frappe App，再从 Tools 首页统一进入。

## 版本兼容

当前版本：`0.1.0`

```text
Frappe  >= 16.0.0, < 17.0.0
ERPNext >= 16.0.0, < 17.0.0
Python  >= 3.14
```

升级 ERPNext 小版本前应先备份站点并运行测试。跨大版本升级，例如 v16 升级到 v17，需要建立独立兼容分支并完成迁移验证。

## 安全说明

- 仓库不应保存数据库密码、API Secret、Access Token、SSH 私钥或站点备份；
- 外部工具地址仅允许 HTTPS；
- Tools 不会把 ERPNext Session、密码或 API Token 传递给外部工具；
- 外部系统需要独立登录，或另行实施 OAuth/OIDC 单点登录；
- 生产环境应部署固定版本标签，不建议直接追踪持续变化的 `main` 分支。

## 后续规划

- 现金流和财务分析工具；
- 报价、装柜及物流辅助工具；
- 项目管理与进度看板；
- OA、审批和内部协作工具；
- 工具使用日志与审计；
- 独立工具的 OAuth/OIDC 单点登录。

## 开源许可

本项目使用 MIT License。


## Exchange Rate Tool (NowAPI)

The Tools app includes an optional Exchange Rate module:

- **Exchange Rate Settings**: configure the NowAPI HTTPS endpoint, AppKey/Sign (Password fields), currency pairs, timeout, standard ERPNext sync, and daily scheduler.
- **Exchange Rate Record**: stores one record per currency pair and date, including numeric rate, fetch status, timestamp, and error details.
- **Manual sync**: open **Tools → Exchange Rates** and choose **Fetch Latest Rates**.
- **Automatic sync**: enable **Enable API Sync** and **Enable Daily Automatic Sync** in Exchange Rate Settings. The Frappe daily scheduler then fetches the configured pairs.
- **ERPNext integration**: when enabled, successful rates are written to the standard **Currency Exchange** DocType for both buying and selling.

Default currency pairs are USD/CNY, THB/CNY, and USD/INR. The USD/INR pair is included because ERPNext v16 validates its Custom Currency Exchange Settings using USD→INR. Remove or replace pairs only after confirming the API supports the pair required by your ERPNext configuration.

### Setup

1. Back up the site and the existing tools app before upgrading.
2. Deploy this branch/version of the app to the bench.
3. Run `bench --site <site> migrate`, then restart the bench workers/web services.
4. Open **Exchange Rate Settings**, enter your own NowAPI AppKey and Sign, save, and first run a manual sync.
5. Confirm the Exchange Rate Record list and standard Currency Exchange records. Only then enable the daily scheduler.

Secrets are stored in Frappe Password fields and are not committed to this repository. Do not put API credentials in source code or share them in screenshots. The NowAPI account's signature requirements must be followed; a static Sign only works if the provider says it is valid for these requests. Rates are current quotes from `finance.rate`, not historical-date rates. The daily job records the date fetched; it does not backfill historical exchange rates.
