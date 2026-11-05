# -*- coding: utf-8 -*-
"""wb_reward —— WorkBuddy 积分任务调度包装器。

被 Windows 计划任务拉起，调用 workbuddy-reward-helper 的 main.py 执行
签到 / 旅行 / 成长计划，并把结果写入 tools/wb_reward/logs/。

入口：python -m tools.wb_reward <checkin|travel|all|growth|health|status>
"""

ACTIONS = {
    "checkin": "每日签到",
    "travel": "旅行计划",
    "all": "签到 + 旅行（默认）",
    "growth": "成长计划：status 查状态 / auto 有可领才领 / claim-all 全领",
    "health": "健康检查：token 剩余有效期 + 一次只读探活",
    "status": "只读探活（等价 skill 的 status 子命令）",
}

__all__ = ["ACTIONS"]
