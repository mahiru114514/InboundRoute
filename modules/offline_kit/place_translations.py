"""本模块持久化确认译名；按城市、实体、名称隔离，原子落盘。"""
from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from modules.route_adapter.place_names import has_chinese
from modules.route_adapter.place_resolver import PlaceNameResolver, place_key

class PlaceTranslationStore:
    def __init__(self,path):
        self.path=Path(path)
        self.lock=threading.RLock()

    def records(self):
        try:
            rows=json.loads(self.path.read_text(encoding='utf-8'))
            return rows if isinstance(rows,dict) else {}
        except (OSError,ValueError): return {}

    def resolver(self):
        return PlaceNameResolver(self.records())

    def resolve(self,point):
        return self.resolver().resolve(point)

    def confirm(self,point,english):
        if not isinstance(point,dict) or not isinstance(point.get('name_zh'),str) or not point['name_zh'].strip() or len(point['name_zh'])>200:
            raise ValueError('请提供有效原地名')
        if not isinstance(english,str) or not english.strip() or len(english)>200 or has_chinese(english) or any(ord(c)<32 for c in english):
            raise ValueError('请输入不含中文的英文地名，最多 200 字符')
        # 不信任客户端提交的状态、来源或任意存储路径。
        selected={k:point[k] for k in ('city','type','place_id','station_id','poi_id','id','coordinate','name_zh') if k in point}
        with self.lock:
            rows=self.records()
            rows[place_key(selected)]={'name_en':english.strip(),'source':'user_confirmed','point':selected}
            self.path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(tmp,self.path)
        return self.resolve(selected)


def localize_payload(payload, resolver):
    """遍历本次包中实际出现的地名；报告与快照一起固化。"""
    import re
    issues={}
    def resolve(point):
        result=resolver.resolve(point)
        if result['status'] in ('candidate','missing') and result['name_zh']:
            issues[result['key']]={**result,'point':{k:v for k,v in point.items() if k in
                ('city','type','place_id','station_id','poi_id','id','coordinate','name_zh')}}
        return result
    def repair(text):
        if not isinstance(text,str): return text
        return re.sub(r'[\u3400-\u4dbf\u4e00-\u9fff0-9·]+',
            lambda m: resolve({'type':'place','name_zh':m.group()})['name_en'] or m.group(),text)
    def visit(node):
        if isinstance(node,list):
            for value in node: visit(value)
        elif isinstance(node,dict):
            for value in list(node.values()): visit(value)
            if node.get('name_zh'):
                if 'lines' in node and node.get('station_id'): kind='station'
                else: kind=node.get('type') or node.get('stop_type') or ('poi' if node.get('poi_id') else 'place')
                # 线路模板已翻译时，只处理其中尚缺译名的端点，保留 Line/Bus 及号码。
                if 'code' in node and node.get('name_en') and has_chinese(node['name_en']):
                    node['name_en']=repair(node['name_en'])
                point={**node,'type':kind}
                result=resolve(point)
                node['name_en']=repair(result['name_en'])
                if 'access_no' not in node:
                    node['name_translation_status']=result['status']
                    node['name_en_for_zh']=result['source_name_zh']
            for zhkey,enkey in [('direction_zh','direction_en'),('note_zh','note_en')]:
                if node.get(zhkey):
                    node[enkey]=repair(node.get(enkey))
                    if not node.get(enkey):
                        node[enkey]=resolve({'name_zh':node[zhkey]})['name_en']
            for zhkey in list(node):
                if zhkey.endswith('_zh') and zhkey not in ('name_zh','direction_zh','note_zh','poi_name_zh'):
                    enkey=zhkey[:-3]+'_en'
                    if enkey in node and node.get(zhkey):
                        if node.get(enkey): node[enkey]=repair(node[enkey])
                        else: node[enkey]=resolve({'name_zh':node[zhkey]})['name_en']
            if node.get('ask_cards') and node.get('name_zh'):
                for card in node['ask_cards']:
                    if card.get('template_key')=='poi_arrival':
                        card['args']['poi_name_zh']=node['name_zh']
                        card['args']['poi_name_en']=node['name_en']
    visit(payload)
    entries=list(issues.values())
    payload['translation_version']=resolver.version
    payload['translation_report']={'status':'missing' if any(r['status']=='missing' for r in entries) else 'needs_review' if entries else 'complete',
        'candidate_count':sum(r['status']=='candidate' for r in entries),
        'missing_count':sum(r['status']=='missing' for r in entries),'items':entries}
    return payload
