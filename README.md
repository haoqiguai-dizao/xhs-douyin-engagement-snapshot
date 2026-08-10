# xhs-douyin-engagement-snapshot

面向 Codex 的小红书与抖音互动内容增量快照技能。

它从小红书点赞/收藏和抖音喜欢/收藏列表中做有边界的增量读取，按稳定内容 ID 去重，保存可追溯快照，并把新增内容整理为有证据边界的标题机制与候选方向。

## 主要能力

- 小红书点赞、收藏与抖音喜欢、收藏视频的增量扫描
- 按平台、列表类型和内容 ID 去重
- 保存历史、差异、覆盖状态与可选深读证据
- 从标题提取角度、场景、冲突、承诺、句式和措辞动作
- 可选生成飞书 Base 待定候选预览，写入前保留人工确认闸门

默认只读，不会自动点赞、收藏、关注、评论、私信或发布内容。飞书写入默认关闭。

## 安装

请查看 [INSTALL.md](INSTALL.md)。

## 使用与边界

完整参数、采集流程、持久化结构和安全边界请查看 [SKILL.md](SKILL.md)。

示例：

```text
运行 xhs-douyin-engagement-snapshot，平台 xhs,douyin，列表 liked,favorited,favorited_videos，前 5 屏增量扫描，不做详情深读，不写飞书。
```

## 辅助脚本

- `scripts/merge_snapshot.py`：合并本次快照、追加历史并生成保守差异。
- `scripts/analyze_titles.py`：提取标题机制特征，不自动判断爆款或选择 TOP。

两个脚本仅依赖 Python 标准库。
