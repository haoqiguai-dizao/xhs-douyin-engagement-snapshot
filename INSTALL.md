# 安装 xhs-douyin-engagement-snapshot

适用于另一台 macOS 设备的 Codex 用户技能安装。

## 1. 解压

将压缩包解压后，确保目录中直接包含：

```text
xhs-douyin-engagement-snapshot/
  SKILL.md
  INSTALL.md
  scripts/merge_snapshot.py
  scripts/analyze_titles.py
  scripts/normalize_metrics.py
```

## 2. 安装到个人技能目录

长期安装建议直接从 GitHub 仓库获取：

```bash
mkdir -p "$HOME/.codex/skills"
git clone https://github.com/haoqiguai-dizao/xhs-douyin-engagement-snapshot.git \
  "$HOME/.codex/skills/xhs-douyin-engagement-snapshot"
```

如果目录已经是该仓库的 Git checkout，更新时执行：

```bash
git -C "$HOME/.codex/skills/xhs-douyin-engagement-snapshot" pull --ff-only origin main
```

每次运行技能前仍会再次检查 GitHub `main`；本地 `git pull` 不是替代检查。

如果使用压缩包安装：

在另一台设备的终端执行：

```bash
mkdir -p "$HOME/.codex/skills"
cp -R "xhs-douyin-engagement-snapshot" "$HOME/.codex/skills/"
```

如果目录已存在，先确认它对应上述 GitHub 仓库，再更新或备份旧版本，避免文件混用。

## 3. 项目数据目录

技能本身安装到个人技能目录；运行产生的数据应放在实际项目的：

```text
数据/平台互动快照/
```

该目录保存快照、历史去重、差异、深读结果、报告和飞书同步日志。不要把账号登录信息、Cookie 或访问令牌复制到包内。

## 4. 验证

重启或刷新 Codex 后，确认技能列表出现：

```text
xhs-douyin-engagement-snapshot
```

然后用类似以下请求试运行：

```text
运行 xhs-douyin-engagement-snapshot，平台 xhs,douyin，列表 liked,favorited,favorited_videos，前 3 屏增量扫描；理解小红书封面和抖音开场 3 秒，不做完整详情深读，不写飞书。
```

运行结果的主报告必须先给“建议标题”：每条证据先达到平台最低理解状态——小红书至少理解封面图与标题关系，抖音至少理解开场画面、屏幕文字及可见口播/字幕状态；只有列表标题的旧数据不能单独支撑候选。公开数据按同平台同指标百分位进入工作权重，不直接比较跨平台绝对值。随后附注意力机制、业务落点、平台原生证据、表现权重和下一步验证；辅助脚本不会自动选 TOP。

## 5. 配置另一台设备的飞书 Base

技能包不包含任何固定的 Base Token、Table ID、View ID 或字段 ID。

运行时传入目标 Base，例如：

```text
feishu_target.base_url=<另一台设备的 Base URL>
feishu_target.table_name=<目标数据表名>
feishu_target.view_name=<可选视图名>
```

技能会先解析真实资源并检查字段；如果字段名称或“待定”选项不匹配，会停止，不会猜测写入。

## 6. 飞书写入

默认关闭。启用前必须在目标设备重新确认飞书用户授权、Base 权限、目标表字段和待定选项；技能只允许把新候选写成 `人工决定=待定`，不会自动保留、进入 B 或发布。
