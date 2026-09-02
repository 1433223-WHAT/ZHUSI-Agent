"""
ArchAI Master Works Registry — 经典建筑案例金字塔

这个文件是 ArchAI Knowledge Builder 的"知识命脉"。
它定义了哪些建筑案例值得被收录，以及为什么值得收录。

设计原则:
- 不是最大最全，而是对建筑学生最有教学价值
- 每个案例标注 design_topics（学生能在其中学到什么）
- keywords 用于 crawler 检索词扩展和 Dify 标签

数据来源（按优先级）:
1. 建筑师基本信息 → Wikidata API（QID, 出生, 国籍）
2. 经典案例列表 → 本文件（人工策划，基于建筑教育共识）
3. 案例详细资料 → crawler 自动抓取

VERSION: 1.0 — Phase 1: 5位大师 × 5案例 = 25件
"""

MASTER_WORKS = {
    # ── 安藤忠雄 ──────────────────────────────────────────────────
    "Tadao Ando": {
        "qid": "Q208220",
        "birth": 1941,
        "country": "日本",
        "style_keywords": ["清水混凝土", "自然光", "极简几何", "空间叙事", "精神性空间"],
        "works": [
            {
                "name": "Church of the Light",
                "name_cn": "光之教堂",
                "year": 1989,
                "location": "日本大阪茨木",
                "type": "宗教建筑",
                "keywords": ["自然光", "精神空间", "清水混凝土", "空间序列", "明暗对比", "十字光缝"],
                "design_topics": ["光环境设计", "宗教空间", "极简建筑", "小尺度精神空间"],
                "teaching_value": "如何用单一元素（光）组织整个空间体验",
            },
            {
                "name": "Church on the Water",
                "name_cn": "水之教堂",
                "year": 1988,
                "location": "日本北海道",
                "type": "宗教建筑",
                "keywords": ["自然元素", "水面反射", "四季变化", "开合空间", "自然融合"],
                "design_topics": ["自然与建筑关系", "宗教空间", "景观融合", "季节性设计"],
                "teaching_value": "如何将自然元素（水、风、四季）作为建筑的一部分",
            },
            {
                "name": "Row House in Sumiyoshi",
                "name_cn": "住吉的长屋",
                "year": 1976,
                "location": "日本大阪",
                "type": "住宅",
                "keywords": ["城市住宅", "中庭空间", "自然引入", "内向型空间", "小尺度"],
                "design_topics": ["城市住宅", "内向型空间", "光庭", "小尺度设计"],
                "teaching_value": "如何在密集城市中通过中庭引入自然而不牺牲私密性",
            },
            {
                "name": "Chichu Art Museum",
                "name_cn": "地中美术馆",
                "year": 2004,
                "location": "日本直岛",
                "type": "博物馆",
                "keywords": ["地下建筑", "自然采光", "路径体验", "艺术与空间", "顶级采光"],
                "design_topics": ["地下空间", "美术馆设计", "自然采光策略", "空间序列"],
                "teaching_value": "如何在地下空间中通过精确的顶部采光口创造丰富的空间体验",
            },
            {
                "name": "Rokko Housing",
                "name_cn": "六甲集合住宅",
                "year": 1983,
                "location": "日本神户",
                "type": "集合住宅",
                "keywords": ["坡地建筑", "集合住宅", "阶梯式布局", "景观视野", "地形回应"],
                "design_topics": ["坡地建筑", "集合住宅", "地形回应", "模数化设计"],
                "teaching_value": "如何在陡峭坡地上通过阶梯式布局创造户户有景的集合住宅",
            },
        ],
    },

    # ── 勒·柯布西耶 ──────────────────────────────────────────────
    "Le Corbusier": {
        "qid": "Q4724",
        "birth": 1887,
        "country": "瑞士/法国",
        "style_keywords": ["现代主义", "建筑五点", "粗野主义", "模度", "纯净形式"],
        "works": [
            {
                "name": "Villa Savoye",
                "name_cn": "萨伏伊别墅",
                "year": 1931,
                "location": "法国普瓦西",
                "type": "住宅",
                "keywords": ["建筑五点", "坡道体验", "屋顶花园", "水平长窗", "自由平面"],
                "design_topics": ["现代主义经典", "底层架空", "空间漫步", "几何纯粹性"],
                "teaching_value": "建筑五点的完美示范——底层架空、屋顶花园、自由平面、水平长窗、自由立面",
            },
            {
                "name": "Unite d'Habitation",
                "name_cn": "马赛公寓",
                "year": 1952,
                "location": "法国马赛",
                "type": "集合住宅",
                "keywords": ["粗野主义", "模度", "空中街道", "集合住宅", "社区空间"],
                "design_topics": ["集合住宅", "粗野主义", "模数化", "立体社区"],
                "teaching_value": "如何在一个建筑内创造完整的社区生态——从住宅到商业街道",
            },
            {
                "name": "Notre Dame du Haut",
                "name_cn": "朗香教堂",
                "year": 1954,
                "location": "法国朗香",
                "type": "宗教建筑",
                "keywords": ["有机形态", "光的戏剧性", "雕塑感", "神圣空间", "不规则开口"],
                "design_topics": ["宗教建筑", "有机建筑", "光环境", "形式自由"],
                "teaching_value": "如何从雕塑和光出发设计一个完全不同于传统教堂的神圣空间",
            },
            {
                "name": "La Tourette",
                "name_cn": "拉图雷特修道院",
                "year": 1960,
                "location": "法国埃沃",
                "type": "宗教建筑",
                "keywords": ["粗野混凝土", "光盒子", "韵律立面", "修道院", "音乐与空间"],
                "design_topics": ["宗教建筑", "光与韵律", "粗野主义", "模度应用"],
                "teaching_value": "如何通过混凝土与光的精密互动创造具有神圣韵律的修道空间",
            },
            {
                "name": "Carpenter Center",
                "name_cn": "卡朋特视觉艺术中心",
                "year": 1963,
                "location": "美国剑桥",
                "type": "教育建筑",
                "keywords": ["坡道穿越", "视觉艺术", "透明性", "校园建筑", "流线组织"],
                "design_topics": ["教育建筑", "建筑漫步", "空间透明性", "校园关系"],
                "teaching_value": "如何让建筑本身成为'被观看的艺术品'——坡道穿越建筑的戏剧性体验",
            },
        ],
    },

    # ── 路易斯·康 ────────────────────────────────────────────────
    "Louis Kahn": {
        "qid": "Q210134",
        "birth": 1901,
        "country": "美国",
        "style_keywords": ["服务与被服务空间", "光的物质性", "纪念性", "砖与混凝土", "秩序感"],
        "works": [
            {
                "name": "Kimbell Art Museum",
                "name_cn": "金贝尔艺术博物馆",
                "year": 1972,
                "location": "美国沃思堡",
                "type": "博物馆",
                "keywords": ["自然光", "拱顶采光", "光的物质性", "服务空间", "经典比例"],
                "design_topics": ["美术馆设计", "顶部采光", "服务与被服务", "材料与光"],
                "teaching_value": "如何用拱顶+光反射器创造均匀、柔和的自然光——美术馆采光的教科书级案例",
            },
            {
                "name": "Salk Institute",
                "name_cn": "索尔克生物研究所",
                "year": 1965,
                "location": "美国拉霍亚",
                "type": "研究建筑",
                "keywords": ["中轴空间", "水渠", "对称性", "实验室", "混凝土与柚木"],
                "design_topics": ["研究建筑", "轴线性空间", "材料对比", "海景关系"],
                "teaching_value": "如何用一条中轴水渠将建筑、天空和海洋连为一体——'没有屋顶的大教堂'",
            },
            {
                "name": "Phillips Exeter Academy Library",
                "name_cn": "埃克塞特图书馆",
                "year": 1972,
                "location": "美国埃克塞特",
                "type": "图书馆",
                "keywords": ["中央空间", "书的剧场", "光井", "环形开口", "砖砌"],
                "design_topics": ["图书馆设计", "中央空间", "光井", "砌筑工艺"],
                "teaching_value": "如何让图书馆成为'拿书的仪式'——中央大空间+环形书架+顶部采光",
            },
            {
                "name": "National Assembly of Bangladesh",
                "name_cn": "孟加拉国会大厦",
                "year": 1982,
                "location": "孟加拉达卡",
                "type": "政府建筑",
                "keywords": ["几何原型", "水与光", "纪念性", "砖与混凝土", "地域性"],
                "design_topics": ["纪念性建筑", "几何纯粹", "地域材料", "光与水的诗意"],
                "teaching_value": "如何用基本的几何形（圆、方、三角）创造具有国家象征的纪念性空间",
            },
            {
                "name": "Yale Center for British Art",
                "name_cn": "耶鲁英国艺术中心",
                "year": 1977,
                "location": "美国纽黑文",
                "type": "博物馆",
                "keywords": ["顶光系统", "结构秩序", "庭院空间", "混凝土框架", "画廊"],
                "design_topics": ["美术馆设计", "结构秩序", "顶部采光", "庭院空间"],
                "teaching_value": "路易斯·康最后建成的作品——成熟的顶光系统+严谨的结构秩序",
            },
        ],
    },

    # ── 密斯·凡德罗 ──────────────────────────────────────────────
    "Mies van der Rohe": {
        "qid": "Q41512",
        "birth": 1886,
        "country": "德国/美国",
        "style_keywords": ["少即是多", "流动空间", "钢与玻璃", "通用空间", "结构美学"],
        "works": [
            {
                "name": "Barcelona Pavilion",
                "name_cn": "巴塞罗那德国馆",
                "year": 1929,
                "location": "西班牙巴塞罗那",
                "type": "展览建筑",
                "keywords": ["流动空间", "独立墙体", "反射水面", "贵重材料", "水平延展"],
                "design_topics": ["流动空间", "材料对比", "展馆设计", "极简建筑"],
                "teaching_value": "流动空间的极致示范——墙体不再围合房间，而是引导和暗示空间方向",
            },
            {
                "name": "Farnsworth House",
                "name_cn": "范斯沃斯住宅",
                "year": 1951,
                "location": "美国普莱诺",
                "type": "住宅",
                "keywords": ["玻璃盒子", "抬升平台", "自然包围", "极简住宅", "透明性"],
                "design_topics": ["极简住宅", "透明与私密", "自然关系", "工业化建造"],
                "teaching_value": "玻璃盒子的终极实验——当所有墙体变成玻璃，如何定义居住的边界",
            },
            {
                "name": "Seagram Building",
                "name_cn": "西格拉姆大厦",
                "year": 1958,
                "location": "美国纽约",
                "type": "办公建筑",
                "keywords": ["高层建筑", "后退广场", "青铜立面", "结构表达", "城市关系"],
                "design_topics": ["高层建筑", "城市公共空间", "幕墙设计", "结构美学"],
                "teaching_value": "如何让摩天楼回馈城市——后退+架空创造城市公共广场",
            },
            {
                "name": "Crown Hall",
                "name_cn": "克朗楼",
                "year": 1956,
                "location": "美国芝加哥",
                "type": "教育建筑",
                "keywords": ["大跨结构", "通用空间", "屋顶悬挂", "无柱空间", "建筑学院"],
                "design_topics": ["教育建筑", "大跨结构", "通用空间", "钢与玻璃"],
                "teaching_value": "悬挂式屋顶创造的无柱大空间——服务空间下沉，主空间纯粹",
            },
            {
                "name": "Neue Nationalgalerie",
                "name_cn": "柏林新国家美术馆",
                "year": 1968,
                "location": "德国柏林",
                "type": "博物馆",
                "keywords": ["大跨屋顶", "下沉基座", "玻璃幕墙", "通用空间", "城市基座"],
                "design_topics": ["美术馆设计", "大跨结构", "下沉空间", "城市界面"],
                "teaching_value": "密斯的终极作品——一个屋顶加八根柱子，用最少的结构创造最纯粹的空间",
            },
        ],
    },

    # ── 彼得·卒姆托 ──────────────────────────────────────────────
    "Peter Zumthor": {
        "qid": "Q123195",
        "birth": 1943,
        "country": "瑞士",
        "style_keywords": ["材料质感", "氛围营造", "手工工艺", "静谧空间", "场所精神"],
        "works": [
            {
                "name": "Therme Vals",
                "name_cn": "瓦尔斯温泉浴场",
                "year": 1996,
                "location": "瑞士瓦尔斯",
                "type": "温泉浴场",
                "keywords": ["石材层叠", "光与水的仪式", "洞穴体验", "静谧氛围", "感官建筑"],
                "design_topics": ["感官建筑", "材料与触觉", "水空间设计", "光与氛围"],
                "teaching_value": "如何用本地石材的层叠砌筑创造光影、水汽、温度交织的感官沉浸体验",
            },
            {
                "name": "Kolumba Museum",
                "name_cn": "科伦巴博物馆",
                "year": 2007,
                "location": "德国科隆",
                "type": "博物馆",
                "keywords": ["废墟与新建", "砖的编织", "光的过滤", "历史层次", "静谧"],
                "design_topics": ["历史建筑更新", "砖砌工艺", "光的过滤", "遗址博物馆"],
                "teaching_value": "如何在废墟上建造——'穿孔'砖墙让光如针般穿过，在遗址上创造静谧的展示空间",
            },
            {
                "name": "Bruder Klaus Chapel",
                "name_cn": "布鲁德克劳斯教堂",
                "year": 2007,
                "location": "德国梅赫尼希",
                "type": "宗教建筑",
                "keywords": ["火烧内腔", "树干模板", "单一空间", "田野建筑", "手工建造"],
                "design_topics": ["小教堂", "建造工艺", "单一空间", "田野建筑"],
                "teaching_value": "用112根树干做模板浇筑混凝土后烧掉树干——极端的建造工艺创造神圣空间",
            },
            {
                "name": "Kunsthaus Bregenz",
                "name_cn": "布雷根茨美术馆",
                "year": 1997,
                "location": "奥地利布雷根茨",
                "type": "博物馆",
                "keywords": ["磨砂玻璃外层", "天花板采光", "四层方盒子", "光与雾", "简洁体量"],
                "design_topics": ["美术馆设计", "双层表皮", "光的层化", "简约体量"],
                "teaching_value": "双层磨砂玻璃表皮+天花板采光槽——光被层层过滤后如薄雾般弥漫整个展厅",
            },
            {
                "name": "Steilneset Memorial",
                "name_cn": "斯泰尔内塞特纪念碑",
                "year": 2011,
                "location": "挪威瓦尔德",
                "type": "纪念建筑",
                "keywords": ["记忆装置", "极地环境", "叙事空间", "纤维与光", "简陋材料"],
                "design_topics": ["纪念建筑", "叙事空间", "极限环境", "材料叙事"],
                "teaching_value": "在北极圈用木材和纤维创造纪念女巫审判受害者的'记忆装置'",
            },
        ],
    },
}

# ── 工具函数 ────────────────────────────────────────────────────────

def get_architect_keys() -> list[str]:
    """返回所有收录的建筑师英文名列表。"""
    return list(MASTER_WORKS.keys())


def get_architect_info(name: str) -> dict | None:
    """获取建筑师信息（不含作品列表）。"""
    entry = MASTER_WORKS.get(name)
    if not entry:
        return None
    return {
        "name": name,
        "qid": entry["qid"],
        "birth": entry["birth"],
        "country": entry["country"],
        "style_keywords": entry["style_keywords"],
        "work_count": len(entry["works"]),
    }


def get_works(name: str) -> list[dict] | None:
    """获取建筑师的作品列表。"""
    entry = MASTER_WORKS.get(name)
    if not entry:
        return None
    return entry["works"]


def get_all_works_count() -> int:
    """返回所有收录案例总数。"""
    return sum(len(e["works"]) for e in MASTER_WORKS.values())


def get_all_architects_count() -> int:
    """返回收录建筑师总数。"""
    return len(MASTER_WORKS)


# ── 测试 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"ArchAI Master Works Registry v1.0")
    print(f"建筑师: {get_all_architects_count()} 位")
    print(f"案例: {get_all_works_count()} 件")
    print()
    for name in MASTER_WORKS:
        info = get_architect_info(name)
        works = get_works(name)
        print(f"{name} ({info['birth']}, {info['country']})")
        for w in works:
            print(f"  • {w['name_cn']} ({w['name']}) — {w['year']}")
            print(f"    {w['teaching_value'][:70]}...")
        print()
