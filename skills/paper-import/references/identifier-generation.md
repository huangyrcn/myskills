# Paper Identifier Generation

格式：`<venue><year>-<bibtex_key>`

其中 `<bibtex_key>` 参考 Google Scholar 格式：`<author><year><keyword>`

## 组成部分

| 部分 | 说明 | 示例 |
|------|------|------|
| venue | 期刊/会议简称 | neurips, iclr, arxiv |
| year | 发表年份 | 2017, 2018 |
| author | 第一作者姓氏（小写） | vaswani, devlin |
| keyword | 标题首词（跳过停用词） | attention, bert |

## 示例

```
Attention Is All You Need (NeurIPS 2017, Vaswani)
→ neurips2017-vaswani2017attention

BERT (NAACL 2019, Devlin)
→ naacl2019-devlin2019bert

Deep Residual Learning (CVPR 2016, He)
→ cvpr2016-he2016deep

arXiv 预印本 (无 venue)
→ arxiv2018-author2018keyword
```

## Venue 简称

```python
VENUE_MAP = {
    # ML/DL
    "neurips": "neurips", "nips": "neurips",
    "iclr": "iclr", "icml": "icml",
    # AI
    "aaai": "aaai", "ijcai": "ijcai",
    # CV
    "cvpr": "cvpr", "iccv": "iccv", "eccv": "eccv",
    # NLP
    "acl": "acl", "emnlp": "emnlp", "naacl": "naacl",
    # Journals
    "nature": "nature", "science": "science",
    # Default
    "arxiv": "arxiv",
}
# Fallback: venue 首词（最多5字符）
```

## 关键词提取

```python
STOPWORDS = {'a','an','the','of','for','in','on','at','to','with','from','and','or','but',
             'is','are','was','were','be','been','have','has','had'}

def extract_keyword(title):
    words = title.split()
    # 缩写词优先（全大写，如 BERT, GPT）
    for w in words:
        clean = w.rstrip(':,;.').lower()
        if w.isupper() and len(w) <= 10:
            return clean
    # 跳过停用词
    for w in words:
        clean = re.sub(r'[^a-z]', '', w.lower())
        if clean and clean not in STOPWORDS and len(clean) > 2:
            return clean
    # 兜底
    return words[0].lower()[:10] if words else "paper"
```