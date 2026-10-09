"use strict";
/* 共用 POI 文本内容；旧数据和外部景点保持明确的缺失提示。 */
function poiIntroduction(poi) {
  const text = typeof poi?.description_zh === 'string' ? poi.description_zh.trim() : '';
  return text || '简介待补充';
}
