# -*- coding: utf-8 -*-
"""wb_reward —— WorkBuddy 积分任务调度包装器。

被 Windows 计划任务拉起，调用 workbuddy-reward-helper 的 main.py 执行
签到 / 旅行 / 成长计划，并把结果写入 logs/wb_reward/。

入口：python -m tools.wb_reward <checkin|travel|all|growth|health|status>

ACTIONS 是动作的**唯一权威清单**：runner 写日志时直接取这里的短标签。
新增/改名动作只改这一处，不要在 runner 里再维护第二份映射
（详细说明看 README.md 的命令表，这里只保留日志里要用的短标签）。
"""

ACTIONS = {
    "all": "签到 + 旅行",       # 默认动作
    "checkin": "签到",
    "travel": "旅行",
    "growth": "成长计划",       # 子参数 status / auto / claim-all
    "health": "登录态检查",
    "status": "状态查询",
}

__all__ = ["ACTIONS"]
