# 酒店商业价格来源调研（2026-10-06）

本次将“付费来源”按付费数据接口/商业供应商理解。仅核实公开官方文档，未注册、购买、联系供应商或使用生产接口。当前12家酒店的逐店覆盖未验证，不将供应商宣传的全球库存数当作这12家的覆盖证明。

## Nuitee Connect / LiteAPI

- [实时房价接口](https://docs.liteapi.travel/reference/post_hotels-rates)：按入住、退房、币种、国籍和每间入住人数查询价格、房型、餐食和取消政策，支持多家酒店。
- [酒店价格指数](https://docs.liteapi.travel/reference/getpriceindexhotels)：最多50个酒店ID一起查询，按日期返回聚合每晚平均价格；为Beta，属于观察价格聚合而非实时可订报价。接口页面写0.02美元/次。
- [缓存公开价格](https://docs.liteapi.travel/reference/getpublicprice)：按酒店ID、入住/退房及成人/儿童配置查询缓存的公开平台报价，返回来源、抓取时间、过期时间。当前只接受USD；没有缓存或没有价格会404，不等同售罄。Beta，接口页写0.02美元/次。
- [统一收费页](https://docs.liteapi.travel/reference/api-pricing-usage-costs)：价格指数类为0.05美元/次，与上述接口页存在矛盾，采购前须确认。若按统一收费页，1000次为50美元；接口页口径为20美元。该费用是请求费，不是房费。
- 核心Rates→Prebook→Book在合理查询/预订比例和条款范围内免费；不能推断“只查价、不产生订单”的预算工具可无限免费调用。[官方FAQ](https://docs.liteapi.travel/docs/faq)要求注册并取得生产凭证，启用条件需按账号当前规则确认。

判断：最值得先验证的候选，既有报价接口也有明确收费的数据端点。须先做12店ID映射和不同日期命中测试，再确认仅预算展示的许可、缓存、币种、税费和价格指数计费。

## Trip.com / 携程合作伙伴房态接口

[官方Hotel Availability Checking文档](https://apidoc.trip.com/apidoc)支持入住/退房、最多20家酒店、成人和儿童年龄、CNY，以及起价或各房型最低报价。返回含税每晚均价、全程总价、税费、早餐、退改和订房跳转链接。需要携程提供合作伙伴身份和密钥，公开文档未给固定按次采购价格；合作及收费条件需向平台申请确认。

判断：值得优先询问国内上海酒店覆盖，但并未核实12家全部可查。适合查询后导流订房的合作路径。不要误用[Connectivity平台](https://connect.trip.com/)作为查询消费者房价入口，它主要面向酒店/PMS/渠道管理系统上传房型、房价与库存。

## Expedia Rapid

[官方合作页](https://partner.expediagroup.com/en-us/solutions/build-your-travel-experience/rapid-api)提供住宿库存、房价及订房商业合作，需要申请成为合作伙伴。[开发者接口入口](https://developers.expediagroup.com/rapid/api/explorer?locale=en_US)可查看API结构。所查公开页面未给固定按次价格或保证纯预算工具获准，需要商务审核并确认只查价展示的用法。12家酒店覆盖须生产权限后逐店实测。

## Booking.com Demand API

[官方准入要求](https://developers.booking.com/demand/docs/getting-started/prerequisites)：Managed Affiliate Partner、签署合同、Partner Centre、API key和Affiliate ID。支持[查询与导流等不同集成](https://developers.booking.com/demand/docs)，但不是付款后立即获得任意数据的公开接口。当前没有查到固定按次付费方案；覆盖和用途授权需在合作中确认。

## 其他发现

- [Duffel Stays](https://duffel.com/docs/guides/getting-started-with-stays)提供实时住宿查询、房型价格和最终报价；[收费页](https://duffel.com/pricing)说明Stays采用完成住宿后的佣金分成。不要把页面Flights的每订单3美元或过量查询费误当酒店接口费用。纯预算查价用途需另行确认。
- [Hotelbeds](https://developer.hotelbeds.com/?level=1)可免费取得评估API key，随后完善商业资料、认证和上线。评估权限不等于当前酒店真实报价覆盖或已达成商业授权。
- Amadeus酒店文档仍可查询，但本次公开pricing入口未取得可靠当前价目表，因此不提供未经确认的每次价格。

## 对当前项目的建议

先验证LiteAPI价格数据端点，同时了解携程房态合作条件。验证清单：12店实体及地址精确匹配、正常日/周末/节假日房价、每间人数与儿童年龄、含税口径、早餐与取消条件、缓存有效期、只用于预算展示的授权、账户收费。宏安瑞士/海仑丽笙的现有实体冲突须先确定真实酒店，不能凭相似名称绑定供应商ID。

得到真实数据后才替换预算中的参考范围；无报价继续沿用标明来源的参考估算，用户手填值继续优先。
